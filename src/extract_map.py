"""
로스트아크 월드맵 스크린샷에서 맵 지형만 추출하는 스크립트.

접근법:
  1. 맵 창을 정적 좌표로 크롭
  2. V > 80 밝은 외곽선을 barrier로 사용
  3. 외부에서 flood fill → barrier 안쪽은 보존
  4. 내부 구멍 채우기
  5. 배경색(#25272C) 큰 덩어리 제거
  6. 노이즈/UI 제거 + 투명 여백 트림

사용법:
    python extract_map.py input/screenshot.jpg
    python extract_map.py input/screenshot.jpg --debug
    python extract_map.py input/
"""

import argparse
import glob
import os
import sys

import cv2
import numpy as np

# 3840x2160 해상도 기준 맵 창 좌표 (고정)
MAP_WINDOW = {"x1": 500, "y1": 250, "x2": 3300, "y2": 1750}

# 배경색 #25272C = RGB(37, 39, 44)
BG_COLOR_RGB = (37, 39, 44)
BG_COLOR_DIST = 20      # 색상 거리 허용 범위
BG_MIN_AREA = 10000      # 이 면적 이상이면 배경 덩어리로 판정


def extract_map_terrain(img_path, output_path=None, debug=False):
    img = cv2.imread(img_path)
    if img is None:
        print(f"오류: 이미지를 읽을 수 없습니다 - {img_path}")
        return False

    h, w = img.shape[:2]
    mw = MAP_WINDOW
    if w == 3840 and h == 2160:
        x1, y1, x2, y2 = mw["x1"], mw["y1"], mw["x2"], mw["y2"]
    else:
        sx, sy = w / 3840, h / 2160
        x1, y1 = int(mw["x1"] * sx), int(mw["y1"] * sy)
        x2, y2 = int(mw["x2"] * sx), int(mw["y2"] * sy)

    crop = img[y1:y2, x1:x2]
    ch, cw = crop.shape[:2]
    v = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2]
    b_ch, g_ch, r_ch = cv2.split(crop)

    if debug:
        cv2.imwrite(output_path.replace(".png", "_01_crop.png"), crop)

    # === Step 1: 외곽선 barrier (V > 80) ===
    outline = (v > 80).astype(np.uint8) * 255
    k_d = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    outline = cv2.dilate(outline, k_d, iterations=2)
    k_c = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    outline = cv2.morphologyEx(outline, cv2.MORPH_CLOSE, k_c)

    if debug:
        cv2.imwrite(output_path.replace(".png", "_02_barrier.png"), outline)

    # === Step 2: 외부 flood fill ===
    passable = cv2.bitwise_not(outline)
    passable[0, :] = 255
    passable[-1, :] = 255
    passable[:, 0] = 255
    passable[:, -1] = 255

    flood = passable.copy()
    mask = np.zeros((ch + 2, cw + 2), dtype=np.uint8)
    for x in range(0, cw, 3):
        if flood[0, x] == 255 and mask[1, x + 1] == 0:
            cv2.floodFill(flood, mask, (x, 0), 128)
        if flood[ch - 1, x] == 255 and mask[ch, x + 1] == 0:
            cv2.floodFill(flood, mask, (x, ch - 1), 128)
    for y in range(0, ch, 3):
        if flood[y, 0] == 255 and mask[y + 1, 1] == 0:
            cv2.floodFill(flood, mask, (0, y), 128)
        if flood[y, cw - 1] == 255 and mask[y + 1, cw] == 0:
            cv2.floodFill(flood, mask, (cw - 1, y), 128)

    alpha = np.full((ch, cw), 255, dtype=np.uint8)
    alpha[flood == 128] = 0

    # === Step 3: 내부 구멍 채우기 ===
    holes = (alpha == 0).astype(np.uint8) * 255
    flood_h = holes.copy()
    hm = np.zeros((ch + 2, cw + 2), dtype=np.uint8)
    for x in range(0, cw, 3):
        if flood_h[0, x] == 255:
            cv2.floodFill(flood_h, hm, (x, 0), 0)
        if flood_h[ch - 1, x] == 255:
            cv2.floodFill(flood_h, hm, (x, ch - 1), 0)
    for y in range(0, ch, 3):
        if flood_h[y, 0] == 255:
            cv2.floodFill(flood_h, hm, (0, y), 0)
        if flood_h[y, cw - 1] == 255:
            cv2.floodFill(flood_h, hm, (cw - 1, y), 0)
    alpha[flood_h > 0] = 255

    # === Step 3.5: 고정 UI 영역 강제 투명 ===
    alpha[:80, :] = 0
    alpha[:200, cw - 700:] = 0
    alpha[ch - 200:, cw - 300:] = 0

    # === Step 4: 배경색(#25272C) 큰 덩어리 제거 ===
    tr, tg, tb = BG_COLOR_RGB
    dist = np.sqrt(
        (r_ch.astype(float) - tr) ** 2
        + (g_ch.astype(float) - tg) ** 2
        + (b_ch.astype(float) - tb) ** 2
    )
    bg_in_alpha = cv2.bitwise_and(
        (dist <= BG_COLOR_DIST).astype(np.uint8) * 255, alpha
    )
    nl_bg, la_bg, st_bg, _ = cv2.connectedComponentsWithStats(
        bg_in_alpha, connectivity=8
    )
    for i in range(1, nl_bg):
        if st_bg[i, cv2.CC_STAT_AREA] > BG_MIN_AREA:
            alpha[la_bg == i] = 0

    if debug:
        cv2.imwrite(output_path.replace(".png", "_03_after_bg.png"), alpha)

    # === Step 5: 노이즈 + UI 잔재 제거 ===
    nl, la, st, _ = cv2.connectedComponentsWithStats(alpha, connectivity=8)
    max_a = max(st[i, cv2.CC_STAT_AREA] for i in range(1, nl)) if nl > 1 else 0
    clean = np.zeros_like(alpha)
    margin = 80
    for i in range(1, nl):
        area = st[i, cv2.CC_STAT_AREA]
        if area < max(5000, max_a * 0.05):
            continue
        cx = st[i, cv2.CC_STAT_LEFT] + st[i, cv2.CC_STAT_WIDTH] // 2
        cy = st[i, cv2.CC_STAT_TOP] + st[i, cv2.CC_STAT_HEIGHT] // 2
        at_corner = (
            (cx < margin or cx > cw - margin or cy < margin or cy > ch - margin)
            and area < max_a * 0.3
        )
        if not at_corner:
            clean[la == i] = 255

    alpha = cv2.GaussianBlur(clean, (3, 3), 0)

    if debug:
        cv2.imwrite(output_path.replace(".png", "_04_alpha.png"), alpha)
        white = np.full_like(crop, 255)
        a3 = np.stack([alpha.astype(float) / 255] * 3, axis=-1)
        comp = (crop.astype(float) * a3 + white.astype(float) * (1 - a3)).astype(
            np.uint8
        )
        cv2.imwrite(output_path.replace(".png", "_white.png"), comp)

    # === Step 6: 투명 여백 제거 (맵에 맞춰 크롭) ===
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if rows.any() and cols.any():
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        crop = crop[y_min : y_max + 1, x_min : x_max + 1]
        alpha = alpha[y_min : y_max + 1, x_min : x_max + 1]

    b, g, r = cv2.split(crop)
    result = cv2.merge([b, g, r, alpha])

    if output_path is None:
        base = os.path.splitext(os.path.basename(img_path))[0]
        output_path = os.path.join("output", f"{base}_map.png")

    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else "output",
        exist_ok=True,
    )
    cv2.imwrite(output_path, result)

    pct = (alpha > 0).sum() / (ch * cw) * 100
    print(f"출력: {output_path} (불투명 {pct:.1f}%)")
    return True


def main():
    parser = argparse.ArgumentParser(description="로스트아크 맵 지형 추출기")
    parser.add_argument("input", help="입력 이미지 파일 또는 폴더 경로")
    parser.add_argument("-o", "--output", help="출력 파일 경로")
    parser.add_argument("--debug", action="store_true", help="디버그 이미지 저장")
    args = parser.parse_args()

    if os.path.isdir(args.input):
        files = []
        for p in ["*.jpg", "*.jpeg", "*.png", "*.bmp"]:
            files.extend(
                f
                for f in glob.glob(os.path.join(args.input, p))
                if not f.endswith(".md")
            )
        if not files:
            print(f"오류: {args.input} 폴더에 이미지가 없습니다")
            sys.exit(1)
        print(f"{len(files)}개 파일 처리 중...")
        success = sum(
            1
            for f in sorted(files)
            if extract_map_terrain(
                f,
                os.path.join(
                    "output",
                    os.path.splitext(os.path.basename(f))[0] + "_map.png",
                ),
                debug=args.debug,
            )
        )
        print(f"\n완료: {success}/{len(files)}개 처리됨")
    else:
        if not os.path.isfile(args.input):
            print(f"오류: 파일을 찾을 수 없습니다 - {args.input}")
            sys.exit(1)
        extract_map_terrain(args.input, args.output, debug=args.debug)


if __name__ == "__main__":
    main()
