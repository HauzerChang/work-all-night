#!/usr/bin/env python3
"""S5 骨架草案產生器 — 件鄰接/重疊分析 → 骨階層 + pivot 建議(可被骨架閘自驗)。

輸入:psd_slice 的 manifest + 件 PNG。輸出:draft JSON(角色/樹/pivot),供
`skel_to_json.py --draft` 組出帶階層的 Spine skeleton。

啟發式(對照 Award 藝術家真實骨架歸納;見 knowledge/s5-skeleton-draft.md):
  1. **角色分類**:
     - effect/backdrop:bbox 覆蓋畫布 ≥85% 且與過半件重疊(光暈、背景光)→ 掛 root 層,
       不進身體鏈(藝術家把光暈綁在全域錨 4_LEG)。
     - trunk:非 effect 中 alpha 面積最大者(身體)。
     - limb:其餘,依重疊掛進樹。
  2. **階層(trunk 優先)**:與 trunk 有重疊的件**直接掛 trunk**(slot rig 慣例是淺樹:
     頭/雙手直掛身體,與藝術家 4_LEG3→4/5/6 一致);不接觸 trunk 的件(如前臂)才以
     最大重疊掛到已入樹的件(鏈式)。單純用最大重疊會被「z 交叉假邊」騙(劍從臉前
     橫過 → 頭↔右手重疊 > 頸部,頭被誤掛到手上)。不重疊的孤島掛 trunk 並警告。
  3. **pivot**:
     - limb:與 parent 的**重疊區質心**(關節就在兩件相接處;頭↔身體重疊=頸部)。
     - trunk:自身 alpha 質心(藝術家放腰部;質心是無資訊下最穩的近似)。
     - effect:自身 alpha 質心(藝術家用場景錨 — 全域擺位決策,無法從單件推斷,列 A 類)。

pivot 的「放哪一點」美術手感仍留人審(PLAN 標記的卡死環節);本工具產生**可過閘的草案**,
把人的工作從「從零擺骨」降為「微調 pivot」。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2

EFFECT_BBOX_FRAC = 0.85
DILATE_PX = 3


def load_alphas(manifest_path, pieces_dir):
    man = json.load(open(manifest_path))
    W, H = man["size"]
    out = {}
    for e in man["parts"]:
        im = cv2.imread(os.path.join(pieces_dir, e["file"]), cv2.IMREAD_UNCHANGED)
        a = np.zeros((H, W), bool)
        l, t = e["offset"]; w, h = e["size"]
        a[t:t + h, l:l + w] = im[..., 3] > 8
        out[e["name"]] = {"entry": e, "alpha": a}
    return man, out


def draft(manifest_path, pieces_dir):
    man, pieces = load_alphas(manifest_path, pieces_dir)
    W, H = man["size"]
    names = list(pieces)
    k = np.ones((DILATE_PX * 2 + 1,) * 2, np.uint8)
    dil = {n: cv2.dilate(pieces[n]["alpha"].astype(np.uint8), k).astype(bool) for n in names}

    # 重疊矩陣(膨脹後,抓「相接」與「互蓋」);key 一律 sorted,避免查詢序不一致
    ov = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ov[tuple(sorted((a, b)))] = int((dil[a] & dil[b]).sum())

    def overlap(a, b):
        return ov.get(tuple(sorted((a, b))), 0)

    # 角色分類
    roles = {}
    for n in names:
        e = pieces[n]["entry"]
        bbox_frac = (e["size"][0] * e["size"][1]) / (W * H)
        touches = sum(1 for m in names if m != n and overlap(n, m) > 0)
        roles[n] = ("effect" if bbox_frac >= EFFECT_BBOX_FRAC and touches >= (len(names) - 1) / 2
                    else "part")
    parts = [n for n in names if roles[n] == "part"]
    trunk = max(parts, key=lambda n: int(pieces[n]["alpha"].sum()))
    roles[trunk] = "trunk"

    # 階層:①與 trunk 重疊者直掛 trunk(淺樹,免疫 z 交叉假邊);②其餘以最大重疊鏈式入樹
    tree = {}      # child -> parent
    in_tree = {trunk}
    warnings = []
    for c in parts:
        if c != trunk and overlap(c, trunk) > 0:
            tree[c] = trunk
            in_tree.add(c)
    while len(in_tree) < len(parts):
        best = None
        for c in parts:
            if c in in_tree:
                continue
            for p in in_tree:
                w = overlap(c, p)
                if w > 0 and (best is None or w > best[0]):
                    best = (w, c, p)
        if best is None:                     # 孤島:掛 trunk
            for c in parts:
                if c not in in_tree:
                    tree[c] = trunk
                    in_tree.add(c)
                    warnings.append(f"'{c}' 與任何件不重疊,掛 trunk(pivot 用自身質心,需人審)")
            break
        _, c, p = best
        tree[c] = p
        in_tree.add(c)

    # pivot
    def centroid(mask):
        ys, xs = np.nonzero(mask)
        return [round(float(xs.mean()), 1), round(float(ys.mean()), 1)]

    pivots = {}
    evidence = {}
    for n in names:
        if roles[n] in ("effect", "trunk") or n not in tree:
            pivots[n] = centroid(pieces[n]["alpha"])
            evidence[n] = {"pivot_from": "self_centroid"}
        else:
            p = tree[n]
            joint = dil[n] & dil[p]
            if joint.any():
                pivots[n] = centroid(joint)
                evidence[n] = {"pivot_from": f"overlap_centroid({p})",
                               "overlap_px": int(joint.sum())}
            else:
                pivots[n] = centroid(pieces[n]["alpha"])
                evidence[n] = {"pivot_from": "self_centroid(no overlap)"}

    return {"source": man["source"], "size": [W, H],
            "roles": roles, "trunk": trunk,
            "tree": tree,                     # child -> parent(effect 件不在其中 = root 層)
            "pivots_px": pivots,              # 畫布像素座標(y-down)
            "evidence": evidence, "warnings": warnings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="/tmp/robot_parts/manifest.json")
    ap.add_argument("--pieces", default="/tmp/robot_parts")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    d = draft(a.manifest, a.pieces)
    if a.out:
        json.dump(d, open(a.out, "w"), ensure_ascii=False, indent=2)
    print(json.dumps(d, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
