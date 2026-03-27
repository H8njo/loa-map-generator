"""
맵 창 크롭 좌표 테스트 스크립트.
좌표를 조정하면서 크롭 결과를 확인할 수 있습니다.

사용법:
    python test_crop.py input/Screenshot_260328_060033.jpg
    python test_crop.py input/Screenshot_260328_060033.jpg --x1 60 --y1 80 --x2 3600 --y2 1750
"""

import argparse
import cv2
import os


# 기본 크롭 좌표 (3840x2160 기준)
DEFAULT_CROP = {"x1": 52, "y1": 46, "x2": 3610, "y2": 1765}


def main():
    parser = argparse.ArgumentParser(description="맵 창 크롭 좌표 테스트")
    parser.add_argument("input", help="입력 이미지 파일")
    parser.add_argument("--x1", type=int, default=DEFAULT_CROP["x1"], help=f"좌측 (기본: {DEFAULT_CROP['x1']})")
    parser.add_argument("--y1", type=int, default=DEFAULT_CROP["y1"], help=f"상단 (기본: {DEFAULT_CROP['y1']})")
    parser.add_argument("--x2", type=int, default=DEFAULT_CROP["x2"], help=f"우측 (기본: {DEFAULT_CROP['x2']})")
    parser.add_argument("--y2", type=int, default=DEFAULT_CROP["y2"], help=f"하단 (기본: {DEFAULT_CROP['y2']})")
    args = parser.parse_args()

    img = cv2.imread(args.input)
    if img is None:
        print(f"오류: 이미지를 읽을 수 없습니다 - {args.input}")
        return

    h, w = img.shape[:2]
    print(f"원본: {w}x{h}")

    crop = img[args.y1:args.y2, args.x1:args.x2]
    ch, cw = crop.shape[:2]
    print(f"크롭: ({args.x1}, {args.y1}) → ({args.x2}, {args.y2}) = {cw}x{ch}")

    base = os.path.splitext(os.path.basename(args.input))[0]
    out = f"output/crop_test_{base}.png"
    os.makedirs("output", exist_ok=True)
    cv2.imwrite(out, crop)
    print(f"저장: {out}")
    print(f"\nextract_map.py에 적용하려면 27번째 줄 수정:")
    print(f'MAP_WINDOW = {{"x1": {args.x1}, "y1": {args.y1}, "x2": {args.x2}, "y2": {args.y2}}}')


if __name__ == "__main__":
    main()
