#!/usr/bin/env python3
"""S4 chunk 308:把 SAM 切出的「兩靴聯集」(同材質相觸,SAM 無法分開;v3 兩件重疊 90%)
用「前方靴多邊形」切成兩件:boot_left(前靴,左上→右下)= 聯集 ∩ 多邊形;boot_right(後靴)= 聯集 − 多邊形。
多邊形頂點由 3x 細格放大圖目視定(見 log/s4-2026-11-06-308.md),是幾何近似;驗收看重疊率 + 蒙太奇。
用法:python s4_boot_split.py <cut_dir>(就地改 16_boot_left.png / 17_boot_right.png 的 alpha,manifest 加註)"""
import json, os, sys
import numpy as np, cv2

cut = sys.argv[1]
man = json.load(open(os.path.join(cut, "manifest.json")))
H, W = man["size"][1], man["size"][0]
# 前靴輪廓(全圖座標):左緣由上到下,再右緣由下到上
LEFT = [(213, 545), (220, 575), (230, 600), (240, 640), (250, 680), (257, 720), (263, 760), (268, 800), (272, 840), (278, 870), (285, 897)]
RIGHT = [(330, 897), (325, 870), (318, 840), (312, 800), (308, 760), (305, 720), (302, 680), (298, 640), (295, 600), (292, 575), (290, 545)]
poly = np.array(LEFT + RIGHT, np.int32)
front = np.zeros((H, W), np.uint8); cv2.fillPoly(front, [poly], 1); front = front.astype(bool)

def full_alpha(p):
    im = cv2.imread(os.path.join(cut, p["file"]), cv2.IMREAD_UNCHANGED); f = np.zeros((H, W), np.uint8)
    ox, oy = p["offset"]; h, w = im.shape[:2]; f[oy:oy+h, ox:ox+w] = im[..., 3]; return im, f
parts = {p["id"]: p for p in man["parts"]}
imL, aL = full_alpha(parts["boot_left"]); imR, aR = full_alpha(parts["boot_right"])
union = np.maximum(aL, aR)
newL = np.where(front, union, 0); newR = np.where(front, 0, union)
# 後靴在前靴多邊形外的碎片(多邊形邊緣誤差)→ 只留最大連通元件 + 次大(後靴被前靴切成上下兩段是正常的)
n, lab, st, _ = cv2.connectedComponentsWithStats((newR > 128).astype(np.uint8))
keep = sorted(range(1, n), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:2]
newR = np.where(np.isin(lab, keep), newR, 0)
def write(p, im, full):
    ox, oy = p["offset"]; h, w = im.shape[:2]; im = im.copy(); im[..., 3] = full[oy:oy+h, ox:ox+w]
    cv2.imwrite(os.path.join(cut, p["file"]), im)
write(parts["boot_left"], imL, newL); write(parts["boot_right"], imR, newR)
for pid in ("boot_left", "boot_right"):
    parts[pid]["notes"] = (parts[pid].get("notes") or "") + " [s4_boot_split: SAM 聯集 ∩/− 前靴多邊形]"
    parts[pid]["split_method"] = "front_boot_polygon"
json.dump(man, open(os.path.join(cut, "manifest.json"), "w"), ensure_ascii=False, indent=2)
L, R = newL > 128, newR > 128
print(f"boot_left {L.sum()} px, boot_right {R.sum()} px, overlap {(L & R).sum()} px, union {(union > 128).sum()} px, dropped {( (union>128) & ~L & ~R).sum()} px")
