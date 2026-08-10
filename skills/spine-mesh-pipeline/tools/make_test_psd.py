#!/usr/bin/env python3
"""造一個合成多圖層 PSD 當測試 fixture(repo 無真實 PSD 前用它驗 pipeline)。

模擬美術交檔:數個命名圖層、各在不同位置、含 alpha、彼此重疊(PSD 典型),
並用群組模擬「部位歸類」。圖層命名遵循 S4 PSD 契約(見 knowledge/s4-psd-contract.md)。
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage


def _rgba(size, draw_fn):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im))
    return im


def build(path, W=256, H=256):
    psd = PSDImage.new("RGBA", (W, H))

    # bg:全幅不透明漸層底(放 0,0)
    bg = Image.new("RGBA", (W, H))
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 0] = np.linspace(40, 120, W)[None, :]
    arr[..., 2] = np.linspace(120, 40, H)[:, None]
    arr[..., 3] = 255
    bg = Image.fromarray(arr, "RGBA")
    psd.create_pixel_layer(bg, name="bg", top=0, left=0)

    # body:中央橢圓(裁切件 + offset,測 bbox/offset 還原)
    body = _rgba((120, 150), lambda d: d.ellipse([0, 0, 119, 149], fill=(220, 80, 80, 255)))
    psd.create_pixel_layer(body, name="char/body", top=60, left=70)

    # arm:與 body 重疊的小塊(測 alpha-over 順序)
    arm = _rgba((60, 40), lambda d: d.rectangle([0, 0, 59, 39], fill=(80, 200, 120, 200)))
    psd.create_pixel_layer(arm, name="char/arm", top=110, left=150)

    # deco:角落帶透明圖案
    deco = _rgba((50, 50), lambda d: d.polygon([(25, 0), (50, 50), (0, 50)], fill=(240, 220, 60, 230)))
    psd.create_pixel_layer(deco, name="fx/deco", top=8, left=8)

    psd.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="assets/test_layered.psd")
    a = ap.parse_args()
    p = build(a.out)
    psd = PSDImage.open(p)
    print(f"寫出 {p}: {psd.width}x{psd.height}, 圖層: {[l.name for l in psd.descendants() if l.is_visible()]}")


if __name__ == "__main__":
    main()
