#!/usr/bin/env python3
"""權重驗證器 — weighted skeleton 的變形品質閘 + pose 渲染(視覺證據)。

AC(對每個 weighted mesh):
  AC1_format :權重和=1、影響骨 ≤2(v1)、索引合法(組裝時已查,這裡複核)。
  AC2_deform :own bone 旋轉掃描(±15/±25/±40°)→ LBS 變形 → 幾何乾淨
               (0 自交/0 翻面/0 退化;用 deform_eval.check,同 S3 變形閘)。
  AC3_anchor :**權重的存在意義** — 高 parent 權重(≥0.5)的關節側頂點在旋轉下
               位移應遠小於剛性綁定(位移比 ≤0.6)。剛性綁定(全 own)= 天然負對照(比=1)。
  AC4_pattern:與 Award 藝術家權重 pattern 對照(混合頂點比例/稀疏度)— 報告 + 部分閘。

Pose 渲染(--render-pose):給骨旋轉 → 全件重繪(weighted=LBS、unweighted mesh=剛性、
region=剛性),逐三角 affine warp 貼圖 → 動畫幀(視覺驗證資產「能動」)。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from weights import parse_weighted, lbs_world
from skel_to_json import _bones_xy
import deform_eval as de

SWEEP_DEG = [15, -15, 25, -25, 40, -40]


def load(skel_path):
    sk = json.load(open(skel_path))
    bones_xy = _bones_xy(sk)
    bones_by_idx = [bones_xy[b["name"]] for b in sk["bones"]]
    name_to_idx = {b["name"]: i for i, b in enumerate(sk["bones"])}
    slot_bone = {s["name"]: s["bone"] for s in sk["slots"]}
    atts = sk["skins"][0]["attachments"]
    return sk, bones_xy, bones_by_idx, name_to_idx, slot_bone, atts


def deform_and_anchor(att, own_idx, bones_by_idx):
    """回傳 (deform 全乾淨?, sweep 明細, anchor 位移比)。"""
    pw = parse_weighted(att["vertices"])
    bw = {i: p for i, p in enumerate(bones_by_idx)}
    setup = lbs_world(pw, bw)
    tris = np.array(att["triangles"], np.int32).reshape(-1, 3)
    signs = [de.signed_area(setup, t) > 0 for t in tris]
    area = sum(abs(de.signed_area(setup, t)) for t in tris)
    px, py = bones_by_idx[own_idx]

    # 錨定側頂點(parent 權重 ≥0.5)與剛性對照
    w_parent = np.array([sum(w for bi, _, _, w in infl if bi != own_idx) for infl in pw])
    anchored = w_parent >= 0.5
    rigid = [[(own_idx, x - px, y - py, 1.0)] for (x, y) in setup]   # 全 own 綁定(負對照)

    all_clean, sweep, ratios = True, [], []
    for deg in SWEEP_DEG:
        rot = {own_idx: (px, py, math.radians(deg))}
        d = lbs_world(pw, bw, rot)
        r = de.eval_pose(d, tris, signs, area)
        sweep.append({"deg": deg, "clean": r["clean"],
                      "si": r["self_intersections"], "flips": r["triangle_flips"]})
        all_clean = all_clean and r["clean"]
        if anchored.any():
            dr = lbs_world(rigid, bw, rot)
            disp_w = float(np.hypot(*(d[anchored] - setup[anchored]).T).mean())
            disp_r = float(np.hypot(*(dr[anchored] - setup[anchored]).T).mean())
            ratios.append(disp_w / max(disp_r, 1e-9))
    anchor_ratio = float(np.mean(ratios)) if ratios else None
    return all_clean, sweep, anchor_ratio, int(anchored.sum()), len(pw)


# Award 藝術家 pattern(機器人 3 weighted mesh,見 knowledge/s5-weights.md)
ARTIST_PATTERN = {"blended_frac": [0.49, 0.61], "max_influences": 3}


def validate(skel_path, anchor_tol=0.6):
    sk, bones_xy, bones_by_idx, name_to_idx, slot_bone, atts = load(skel_path)
    rows, overall = [], True
    for slot, d in atts.items():
        att = list(d.values())[0]
        if att.get("type") != "mesh" or len(att["vertices"]) == len(att["uvs"]):
            continue
        own_idx = name_to_idx[slot_bone[slot]]
        pw = parse_weighted(att["vertices"])
        sums = [sum(w for _, _, _, w in infl) for infl in pw]
        ninf = [len(infl) for infl in pw]
        fmt_ok = all(abs(s - 1) < 1e-3 for s in sums) and max(ninf) <= 2 and \
                 all(0 <= bi < len(bones_by_idx) for infl in pw for bi, *_ in infl)
        clean, sweep, anchor_ratio, n_anchor, nv = deform_and_anchor(att, own_idx, bones_by_idx)
        blended = sum(1 for n in ninf if n > 1) / nv
        anchor_ok = anchor_ratio is not None and anchor_ratio <= anchor_tol
        row_pass = fmt_ok and clean and anchor_ok
        overall = overall and row_pass
        rows.append({"slot": slot, "nv": nv,
                     "AC1_format": {"pass": fmt_ok, "sum_range": [round(min(sums), 5), round(max(sums), 5)],
                                    "max_influences": max(ninf)},
                     "AC2_deform": {"pass": clean, "sweep": sweep},
                     "AC3_anchor": {"pass": anchor_ok, "disp_ratio_vs_rigid": round(anchor_ratio, 3),
                                    "tol": anchor_tol, "anchored_verts": n_anchor,
                                    "note": "剛性綁定(負對照)比值=1.0"},
                     "AC4_pattern": {"blended_frac": round(blended, 3),
                                     "artist_range": ARTIST_PATTERN["blended_frac"],
                                     "note": "藝術家混的是件內子骨(前臂),我們混 parent — 語義不同,僅報告"},
                     "overall_pass": row_pass})
    return {"overall_pass": overall and len(rows) > 0, "weighted_meshes": len(rows), "rows": rows}


# ---------- pose 渲染(視覺證據) ----------
def render_pose(skel_path, manifest_path, pieces_dir, rot_spec, out_png):
    """rot_spec: {piece_name: deg}(繞該件 bone 世界位置旋轉;會連動子骨)。"""
    sk, bones_xy, bones_by_idx, name_to_idx, slot_bone, atts = load(skel_path)
    man = json.load(open(manifest_path))
    W, H = man["size"]
    ns = sk["slots"][0]["name"].rsplit("/", 1)[0]
    entries = {e["name"]: e for e in man["parts"]}

    # 骨旋轉傳遞:對每骨求「最近的被旋轉祖先」(含自身)→ 繞該祖先 pivot 轉
    parent = {b["name"]: b.get("parent") for b in sk["bones"]}
    def eff_rot(bname):
        n = bname
        while n is not None:
            pc = n[2:] if n.startswith("b_") else n
            if pc in rot_spec:
                px, py = bones_xy[n]
                return (px, py, math.radians(rot_spec[pc]))
            n = parent[n]
        return None

    def w2px(p):
        return np.array([p[0] + W / 2.0, H / 2.0 - p[1]])

    canvas = np.zeros((H, W, 4), np.uint8)
    for e in sorted(man["parts"], key=lambda x: x["z"]):
        name = e["name"]
        slot = f"{ns}/{name}"
        att = list(atts[slot].values())[0]
        bname = slot_bone[slot]
        img = cv2.imread(os.path.join(pieces_dir, e["file"]), cv2.IMREAD_UNCHANGED)
        ih, iw = img.shape[:2]
        rot = eff_rot(bname)
        if att.get("type") == "mesh":
            uv = np.asarray(att["uvs"], float)
            src = np.column_stack([uv[0::2] * iw, uv[1::2] * ih])
            if len(att["vertices"]) != len(att["uvs"]):
                pw = parse_weighted(att["vertices"])
                bw = {i: p for i, p in enumerate(bones_by_idx)}
                bone_rot = {}
                for i2, bn2 in enumerate(sk["bones"]):
                    r2 = eff_rot(bn2["name"])
                    if r2:
                        bone_rot[i2] = r2
                world = lbs_world(pw, bw, bone_rot)
            else:
                bx, by = bones_xy[bname]
                v = np.asarray(att["vertices"], float)
                world = np.column_stack([v[0::2] + bx, v[1::2] + by])
                if rot:
                    px, py, th = rot
                    c, s = math.cos(th), math.sin(th)
                    dx, dy = world[:, 0] - px, world[:, 1] - py
                    world = np.column_stack([px + c * dx - s * dy, py + s * dx + c * dy])
            dst = np.array([w2px(p) for p in world])
            tris = np.array(att["triangles"], np.int32).reshape(-1, 3)
            for t in tris:
                s3 = src[t].astype(np.float32); d3 = dst[t].astype(np.float32)
                if abs(cv2.contourArea(d3.astype(np.float32))) < 0.5:
                    continue
                M = cv2.getAffineTransform(s3, d3)
                warped = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR,
                                        borderValue=(0, 0, 0, 0))
                mask = np.zeros((H, W), np.uint8)
                cv2.fillConvexPoly(mask, np.round(d3).astype(np.int32), 1)
                m = mask.astype(bool) & (warped[..., 3] > 8)
                canvas[m] = warped[m]
        else:  # region:剛性(bone + att x/y/rotation=0)
            bx, by = bones_xy[bname]
            cx, cy = bx + att.get("x", 0), by + att.get("y", 0)
            world = np.array([[cx - iw/2, cy + ih/2], [cx + iw/2, cy + ih/2], [cx - iw/2, cy - ih/2]])
            if rot:
                px, py, th = rot
                c, s = math.cos(th), math.sin(th)
                dx, dy = world[:, 0] - px, world[:, 1] - py
                world = np.column_stack([px + c * dx - s * dy, py + s * dx + c * dy])
            src3 = np.array([[0, 0], [iw, 0], [0, ih]], np.float32)
            dst3 = np.array([w2px(p) for p in world], dtype=np.float32)
            M = cv2.getAffineTransform(src3, dst3)
            warped = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR,
                                    borderValue=(0, 0, 0, 0))
            m = warped[..., 3] > 8
            canvas[m] = warped[m]
    cv2.imwrite(out_png, canvas)
    return out_png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="/tmp/robot_asset/robot_weighted.json")
    ap.add_argument("--manifest", default="/tmp/robot_parts/manifest.json")
    ap.add_argument("--pieces", default="/tmp/robot_parts")
    ap.add_argument("--render-pose", default=None,
                    help='JSON 如 {"左手":-20,"右手":15} → 渲染到 --pose-out')
    ap.add_argument("--pose-out", default="/tmp/pose.png")
    a = ap.parse_args()
    if a.render_pose:
        out = render_pose(a.skeleton, a.manifest, a.pieces, json.loads(a.render_pose), a.pose_out)
        print(f"rendered → {out}")
        return
    rep = validate(a.skeleton)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
