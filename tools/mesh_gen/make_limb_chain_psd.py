#!/usr/bin/env python3
"""造一個合成「多跳肢體鏈」PSD 當測試 fixture(S5 (d') 端到端閘用)。

動機:真實資產 `robot_parts` 的可拆肢體(頭/左手/右手)都是 **region** 件、且都直掛 body
(星形,單跳);它的 weighted mesh 只有 body(rig 根)+ 光暈(effect)。因此
「**weighted mesh 當作鏈中段肢體(既是某件的子、又是另一件的父)**」這個案例
在 robot_parts 上**無真實樣本**(見 `knowledge/s5-rig-weighted-combo.md` honest boundary)。

本 fixture 造一條清楚的運動學鏈:
    身體(trunk, root) → 上臂(arm) → 前臂(forearm) → 手(hand)
其中 **上臂 / 前臂**尺寸夠大(coverage ≥ 0.15)→ 分析器判為 mesh → `--weighted` 時成 weighted mesh,
且各在鏈中段(上臂:父=身體、子=前臂;前臂:父=上臂、子=手)。手為小 region 葉件。

幾何刻意安排:**只有相鄰件重疊(接觸距離 0)、非相鄰件分離**,使 `infer_tree` 的接觸距離
Dijkstra 樹 recover 出鏈(而非星形);且各肢體為實心銳邊純色塊(soft≈0、無特效關鍵字)
→ 分析器判為結構件(非 effect)。命名含部位關鍵字(身/臂/手)→ struct_role 正確。

圖層命名遵循 S4 PSD 契約(`knowledge/s4-psd-contract.md`)。
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage


# 各件:name, left, top, w, h, RGB。座標為 PSD/影像座標(top-left 原點,y 向下)。
# 佈局(見檔頭):對角鏈,只有相鄰件重疊。canvas 360x320。
# 註:psd_tools 寫檔用 mac_roman 編碼 pascal string,CJK 圖層名會失敗,故 fixture 用 ASCII 名
# (分析器 struct_role 關鍵字亦吃英文:body→body、arm/hand→limb、forearm 含 arm→limb)。
PARTS = [
    # body:最大面積 → infer_tree 取為 root;下方
    ("char/body", 20, 170, 180, 140, (200, 90, 90)),
    # arm(上臂):與 body 右上角重疊,往右上延伸;coverage≥0.15 → mesh
    ("char/arm", 160, 80, 150, 120, (90, 170, 200)),
    # forearm(前臂):與 arm 左上重疊、折回左上遠離 body;coverage≥0.15 → mesh
    ("char/forearm", 30, 15, 160, 110, (120, 200, 120)),
    # hand(手):與 forearm 左端重疊、更遠;小 region 葉件
    ("char/hand", 0, 60, 60, 60, (230, 200, 80)),
]
CANVAS = (360, 320)  # W, H


def _solid(w, h, rgb):
    """實心銳邊純色塊(alpha=255,無羽化)→ soft≈0、結構件。"""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([0, 0, w - 1, h - 1], fill=(*rgb, 255))
    return im


def build(path, parts=PARTS, canvas=CANVAS):
    W, H = canvas
    psd = PSDImage.new("RGBA", (W, H))
    # 由下而上(z 由 PSD 圖層順序決定;先建的在下)。身體最底。
    for name, left, top, w, h, rgb in parts:
        psd.create_pixel_layer(_solid(w, h, rgb), name=name, top=top, left=left)
    psd.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="assets/limb_chain.psd")
    a = ap.parse_args()
    p = build(a.out)
    psd = PSDImage.open(p)
    print(f"寫出 {p}: {psd.width}x{psd.height}, 圖層: "
          f"{[l.name for l in psd.descendants() if l.is_visible()]}")


if __name__ == "__main__":
    main()
