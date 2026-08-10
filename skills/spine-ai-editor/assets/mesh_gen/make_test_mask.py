#!/usr/bin/env python3
"""產生合成測試遮罩(無真實 main_draw.png 時驗證 pipeline 端到端)。

預設做一個窗簾狀形體:外緣帶波浪下襬 + 內部直紋(製造 Canny 內部邊界,
測試生成器是否會沿內部視覺邊界放點)。尺寸對齊 curtain_left(346×535)。
"""
import argparse
import numpy as np
import cv2


def make_curtain(W=346, H=535):
    img = np.zeros((H, W, 4), np.uint8)
    # 主體:左右直邊,底部波浪
    poly = []
    for y in range(0, H, 4):
        poly.append((int(0.06 * W), y))
    bottom_y = int(0.92 * H)
    for x in range(0, W + 1, 6):
        wave = 18 * np.sin(x / W * np.pi * 4)
        poly.append((x, int(bottom_y + wave)))
    for y in range(H, 0, -4):
        poly.append((int(0.94 * W), y))
    pts = np.array(poly, np.int32)
    cv2.fillPoly(img, [pts], (40, 30, 200, 255))  # 紅色窗簾, 不透明
    # 內部直紋(布料褶痕)→ 製造 Canny 內部邊界
    for k in range(1, 6):
        x = int(W * k / 6)
        cv2.line(img, (x, 6), (x, bottom_y), (20, 15, 120, 255), 2)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="test_curtain.png")
    ap.add_argument("-W", type=int, default=346)
    ap.add_argument("-H", type=int, default=535)
    args = ap.parse_args()
    cv2.imwrite(args.out, make_curtain(args.W, args.H))
    print(f"寫出測試遮罩 {args.out} ({args.W}x{args.H})")


if __name__ == "__main__":
    main()
