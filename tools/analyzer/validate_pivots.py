#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5 pivot 推斷器的真值閘：對 Award 生產 spine 的真實骨架驗證 infer_pivots。

真值來源:Award 機器人（4_LEG* 骨鏈）——在 Spine 中，**子骨的世界原點就是它相對父件的關節 pivot**。
  身體=4_LEG3(root)、頭=4_LEG4、左手=4_LEG5、右手=4_LEG6，皆為 4_LEG3 之子。
  故真值關節：身體↔頭 = world(4_LEG4)、身體↔左手 = world(4_LEG5)、身體↔右手 = world(4_LEG6)。

件 silhouette 全部在**同一 Spine 世界座標系**取得（免跨座標對齊）:
  - mesh 件(身體/左手/光暈):setup pose weighted skinning 後的世界頂點三角面。
  - region 件(頭/右手):atlas 真實 alpha 輪廓，經 region attachment(x,y,w,h,rot)+骨變換置入世界。

AC:
  AC1 階層正確   : 推斷樹 == 真值(root=身體;頭/左手/右手 皆為身體之子;無假邊如 頭-右手)。
  AC2 pivot 精度 : 每關節誤差 ≤ acc_frac × 軀幹對角線(預設 10%)。
  AC3 勝過 baseline: overlap-形心中位誤差 明顯 < 子件形心(baseline)中位誤差。
  AC4 特效剔除   : 光暈 被標 effect,不獲關節。
負對照(--selftest):把「推斷 pivot」換成子件形心 → AC2/AC3 應 fail(證明閘有鑑別力)。
"""
import sys
import os
import math
import argparse
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import weighted_deform_eval as W  # noqa: E402
import atlas_crop as A            # noqa: E402
import infer_pivots as IP         # noqa: E402

ASSETS = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
PART_SLOT = {"光暈": "機器人拆件/光暈", "右手": "機器人拆件/右手", "頭": "機器人拆件/頭",
             "身體": "機器人拆件/身體", "左手": "機器人拆件/左手"}
# 件 → 控制骨（真值 pivot = 該骨世界原點）
PART_BONE = {"光暈": "4_LEG", "右手": "4_LEG6", "頭": "4_LEG4", "身體": "4_LEG3", "左手": "4_LEG5"}


def load_award():
    sk, bones, byname, order = W.load_skeleton(os.path.join(ASSETS, "Award.json"))
    world = W.bone_world_transforms(bones, byname, order, {})
    skin = W.get_skin_attachments(sk)
    slots = {s["name"]: s for s in sk["slots"]}
    bidx = [b["name"] for b in bones]
    regs = A.parse_atlas(os.path.join(ASSETS, "Award.atlas"))
    return world, skin, slots, bidx, regs


def _att(skin, slotname):
    for a in skin.get(slotname, {}).values():
        return a
    return None


def part_polys(part, world, skin, slots, bidx, regs):
    """回傳該件在世界座標的多邊形列表（mesh=三角面;region=alpha 輪廓）。"""
    sn = PART_SLOT[part]
    a = _att(skin, sn)
    wb = world[slots[sn]["bone"]]
    if a.get("type") == "mesh":
        pv, tris, hull, uvs, wgt = W.parse_weighted(a)
        wv = W.skin_vertices(pv, world, bidx)
        return [[tuple(wv[i]) for i in t] for t in tris]
    # region → atlas alpha 輪廓
    page = os.path.join(ASSETS, regs[sn]["page"])
    img = A.extract(os.path.join(ASSETS, "Award.atlas"), page, sn)
    alpha = img[:, :, 3]
    H, Wd = alpha.shape
    cnts, _ = cv2.findContours((alpha > 16).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    w = a["width"]; h = a["height"]; x = a.get("x", 0); y = a.get("y", 0)
    rot = math.radians(a.get("rotation", 0))
    poly = []
    for col, row in c:
        sxk = col / Wd - 0.5
        syk = 0.5 - row / H
        lx = x + sxk * w * math.cos(rot) - syk * h * math.sin(rot)
        ly = y + sxk * w * math.sin(rot) + syk * h * math.cos(rot)
        poly.append(W.transform_point(wb, lx, ly))
    return [poly]


def gt_pivots(world):
    """真值關節 pivot（世界座標）= 子骨世界原點。"""
    def wpos(bn):
        a, b, c, d, x, y = world[bn]
        return (x, y)
    return {"頭": wpos("4_LEG4"), "左手": wpos("4_LEG5"), "右手": wpos("4_LEG6")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="負對照:用子件形心當推斷(應 fail)")
    ap.add_argument("--acc-frac", type=float, default=0.10, help="AC2 誤差門檻(軀幹對角線比例)")
    ap.add_argument("--figure", default=None, help="輸出視覺化 png 路徑")
    args = ap.parse_args()

    world, skin, slots, bidx, regs = load_award()
    parts = {p: part_polys(p, world, skin, slots, bidx, regs) for p in PART_SLOT}
    gt = gt_pivots(world)

    res = IP.infer(parts)
    masks, origin = res["masks"], res["origin"]

    # 軀幹對角線（尺度歸一）
    bm = masks["身體"]
    ys, xs = np.where(bm > 0)
    body_diag = math.hypot(xs.max() - xs.min(), ys.max() - ys.min())
    acc_thresh = args.acc_frac * body_diag

    def child_centroid(child):
        m = masks[child] > 0
        yy, xx = np.where(m)
        return (float(xx.mean()) + origin[0], float(yy.mean()) + origin[1])

    # 推斷 pivot（或負對照:子件形心）
    infer_piv = {}
    for child in gt:
        if args.selftest:
            infer_piv[child] = child_centroid(child)
        else:
            infer_piv[child] = res["pivots"].get(child)

    # 誤差
    def err(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    infer_errs, base_errs = {}, {}
    for child in gt:
        ip = infer_piv[child]
        infer_errs[child] = err(ip, gt[child]) if ip else float("inf")
        base_errs[child] = err(child_centroid(child), gt[child])

    # ---- AC1 階層 ----
    exp_children = {"頭", "左手", "右手"}
    got_children = set(res["hierarchy"].keys()) & exp_children
    hier_ok = (res["root"] == "身體"
               and got_children == exp_children
               and all(res["hierarchy"][c] == "身體" for c in exp_children if c in res["hierarchy"]))
    # 無假邊:所有結構邊的 child 都掛在身體
    no_false = all(p == "身體" for (p, c, _, _) in res["edges"])
    ac1 = hier_ok and no_false

    # ---- AC2 精度 ----
    ac2 = all(infer_errs[c] <= acc_thresh for c in gt)

    # ---- AC3 勝過 baseline ----
    med_i = float(np.median([infer_errs[c] for c in gt]))
    med_b = float(np.median([base_errs[c] for c in gt]))
    ac3 = med_i < med_b

    # ---- AC4 特效剔除 ----
    ac4 = ("光暈" in res["effects"]) and ("光暈" not in res["pivots"])

    print("=" * 62)
    print("S5 pivot 推斷器 vs Award 真值" + ("  [負對照:子件形心]" if args.selftest else ""))
    print("=" * 62)
    print(f"root={res['root']}  effects={sorted(res['effects'])}  structural={sorted(res['structural'])}")
    print(f"軀幹對角線={body_diag:.0f}px  AC2 門檻={acc_thresh:.1f}px ({args.acc_frac*100:.0f}%)")
    print(f"{'關節':<6}{'推斷 pivot':<22}{'真值':<22}{'誤差':>8}{'baseline':>10}")
    for child in ["頭", "左手", "右手"]:
        ip = infer_piv[child]
        ips = f"({ip[0]:7.1f},{ip[1]:7.1f})" if ip else "None"
        g = gt[child]
        print(f"{child:<6}{ips:<22}({g[0]:7.1f},{g[1]:7.1f})   {infer_errs[child]:7.1f} {base_errs[child]:9.1f}")
    print(f"中位誤差 推斷={med_i:.1f}  baseline={med_b:.1f}")
    print("-" * 62)
    print(f"AC1 階層正確      : {'PASS' if ac1 else 'FAIL'}  (hierarchy={res['hierarchy']})")
    print(f"AC2 pivot 精度    : {'PASS' if ac2 else 'FAIL'}  (max 誤差={max(infer_errs.values()):.1f} ≤ {acc_thresh:.1f})")
    print(f"AC3 勝過 baseline : {'PASS' if ac3 else 'FAIL'}  (中位 {med_i:.1f} < {med_b:.1f})")
    print(f"AC4 特效剔除      : {'PASS' if ac4 else 'FAIL'}")
    overall = ac1 and ac2 and ac3 and ac4
    if args.selftest:
        expect_fail = not (ac2 and ac3)
        print("-" * 62)
        print(f"負對照結果(應 AC2/AC3 FAIL)  : {'PASS 有鑑別力' if expect_fail else 'FAIL 閘無鑑別力!'}")
        overall = expect_fail
    print("=" * 62)
    print("OVERALL:", "PASS" if overall else "FAIL")

    if args.figure:
        _draw(args.figure, parts, res, gt, infer_piv, origin, masks)
        print("figure ->", args.figure)
    return 0 if overall else 1


def _draw(path, parts, res, gt, infer_piv, origin, masks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 8))
    colors = {"身體": "#4C78A8", "頭": "#F58518", "左手": "#54A24B", "右手": "#E45756", "光暈": "#BAB0AC"}
    for name, polys in parts.items():
        for poly in polys:
            xs = [p[0] for p in poly] + [poly[0][0]]
            ys = [p[1] for p in poly] + [poly[0][1]]
            ax.plot(xs, ys, color=colors.get(name, "#888"), lw=0.4, alpha=0.5)
    for child in gt:
        g = gt[child]
        ax.plot(g[0], g[1], "k*", ms=16, mfc="none", mew=1.5)
        ip = infer_piv[child]
        if ip:
            ax.plot(ip[0], ip[1], "o", color=colors.get(child), ms=9)
            ax.plot([g[0], ip[0]], [g[1], ip[1]], "k-", lw=0.8)
    ax.plot([], [], "k*", ms=14, mfc="none", label="ground-truth pivot (bone)")
    ax.plot([], [], "ko", ms=8, label="inferred pivot (overlap centroid)")
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("S5 rig pivot inference vs Award ground truth")
    plt.tight_layout()
    plt.savefig(path, dpi=110)


if __name__ == "__main__":
    sys.exit(main())
