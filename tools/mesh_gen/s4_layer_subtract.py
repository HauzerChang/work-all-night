#!/usr/bin/env python3
"""S4 chunk 308:SAM 對「淺色相鄰物件」(長髮/紗袖/尾尖)會合併成一個物件,負點救不回(v3/v4 實測)。
改用圖層減法:hair_main −= sleeve_left ∪ hand_left ∪ (tails_mass ∩ 尾尖框)。前者是明確前後關係(袖/手在髮前);
尾尖框是幾何近似(髮絲與尾巴在左下大面積交疊,只排除明顯的粉色尾尖區)。
用法:python s4_layer_subtract.py <cut_dir>"""
import json, os, sys
import numpy as np, cv2
cut = sys.argv[1]
man = json.load(open(os.path.join(cut, "manifest.json"))); W, H = man["size"]
P = {p["id"]: p for p in man["parts"]}
def full(pid):
    p = P[pid]; im = cv2.imread(os.path.join(cut, p["file"]), cv2.IMREAD_UNCHANGED); f = np.zeros((H, W), np.uint8)
    ox, oy = p["offset"]; h, w = im.shape[:2]; f[oy:oy+h, ox:ox+w] = im[..., 3]; return im, f
TAIL_TIP_BOX = (0, 330, 125, 445)   # x0,y0,x1,y1 全圖座標
PINK_RB_DIFF = 18
im, hair = full("hair_main")
sub = np.zeros((H, W), bool)
for pid in ("sleeve_left", "hand_left"): sub |= full(pid)[1] > 128
tails = full("tails_mass")[1] > 128; box = np.zeros((H, W), bool); x0, y0, x1, y1 = TAIL_TIP_BOX; box[y0:y1, x0:x1] = True
# 尾尖框內只減「粉色毛」(R−B 偏大),保留藍銀髮絲;閾值以框內 tails 像素色彩實測(見 log 308)
rgb = cv2.imread(os.path.join(cut, "composite.png"))[..., ::-1].astype(int)
pinkish = (rgb[..., 0] - rgb[..., 2]) > PINK_RB_DIFF
pk = cv2.morphologyEx((tails & box & pinkish).astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
sub |= pk
sub = cv2.dilate(sub.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))).astype(bool)
before = (hair > 128).sum(); hair[sub] = 0
# 去除減法後殘留的小碎片(<80px)
n, lab, st, _ = cv2.connectedComponentsWithStats((hair > 128).astype(np.uint8))
for i in range(1, n):
    if st[i, cv2.CC_STAT_AREA] < 80: hair[lab == i] = 0
p = P["hair_main"]; ox, oy = p["offset"]; h, w = im.shape[:2]; im[..., 3] = hair[oy:oy+h, ox:ox+w]
cv2.imwrite(os.path.join(cut, p["file"]), im)
p["notes"] = (p.get("notes") or "") + f" [s4_layer_subtract: −sleeve_left −hand_left −(tails_mass∩{TAIL_TIP_BOX})]"
json.dump(man, open(os.path.join(cut, "manifest.json"), "w"), ensure_ascii=False, indent=2)
print(f"hair_main {before} → {(hair > 128).sum()} px")
