#!/usr/bin/env python3
"""S5 整合 AC:骨架草案 vs Award 藝術家真實骨架(拓樸 + pivot 位置)。

比較基準:pivot 換算到**各件自身影像的像素座標**(仿射反解;與 Award 場景擺姿/縮放無關的不變量):
  - region:world = boneW ∘ T(att.x,y) R(att.rot) → bone origin 的影像座標閉式解。
  - weighted mesh:以「uv像素 → setup 世界」的仿射最小平方擬合反解(實測殘差 0 — setup 下剛性)。

AC:
  1. **拓樸吻合**:trunk 判定、每件的 parent、effect 件掛 root 層 — 與藝術家一致。
  2. **pivot 距離**:草案 pivot 與藝術家 pivot 的距離 / 件對角線 ≤ 閾值(可比件:limb+trunk)。
     effect 件(光暈)藝術家綁**場景錨**(pivot 在件影像外,y_norm=1.07)— 全域擺位決策,
     無法從單件幾何推斷 → 列「不可比,A 類需人決」,只報告不計分。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from evaluate_skeleton import world_transforms, attachment_world_pts

# Award 真實骨架的拓樸真值(由 assets/Award.json 讀出,見 knowledge/s5-skeleton-draft.md)
AWARD_TRUNK = "身體"
AWARD_PARENT = {"頭": "身體", "左手": "身體", "右手": "身體"}   # limb -> parent
AWARD_ROOT_LEVEL = {"光暈"}                                       # effect 掛全域錨


def artist_pivots_image_px(award_json, slot_prefix="機器人拆件/"):
    sk = json.load(open(award_json))
    mats = world_transforms(sk["bones"])
    att_map = sk["skins"][0]["attachments"]
    slot_bone = {s["name"]: s["bone"] for s in sk["slots"]}
    bone_names = [b["name"] for b in sk["bones"]]
    out = {}
    for slot in att_map:
        if not slot.startswith(slot_prefix):
            continue
        part = slot[len(slot_prefix):]
        a = att_map[slot][slot]
        bn = slot_bone[slot]
        bx, by = mats[bn][:, 2]
        W, H = a["width"], a["height"]
        if a.get("type", "region") == "region":
            r = math.radians(a.get("rotation", 0.0))
            c, s = math.cos(r), math.sin(r)
            v = np.array([-a.get("x", 0.0), -a.get("y", 0.0)])
            p = np.array([c * v[0] + s * v[1], -s * v[0] + c * v[1]])
            px, py = p[0] + W / 2.0, H / 2.0 - p[1]
            resid = 0.0
        else:
            pts = attachment_world_pts(mats, bone_names, bn, a)
            uvs = np.array(a["uvs"]).reshape(-1, 2)
            img = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
            A = np.column_stack([img, np.ones(len(img))])
            sol, _, _, _ = np.linalg.lstsq(A, pts, rcond=None)
            resid = float(np.abs(A @ sol - pts).mean())
            M = sol[:2].T
            p = np.linalg.solve(M, np.array([bx, by]) - sol[2])
            px, py = float(p[0]), float(p[1])
        out[part] = {"px": [round(px, 1), round(py, 1)], "size": [W, H],
                     "affine_resid": round(resid, 2)}
    return out


def validate(draft_path, manifest_path, award_json, pivot_tol=0.15):
    d = json.load(open(draft_path))
    man = json.load(open(manifest_path))
    offsets = {e["name"]: e["offset"] for e in man["parts"]}
    artist = artist_pivots_image_px(award_json)

    # AC1 拓樸
    topo = {
        "trunk": {"draft": d["trunk"], "artist": AWARD_TRUNK,
                  "match": d["trunk"] == AWARD_TRUNK},
        "parents": {}, "root_level": {},
    }
    for part, gt_parent in AWARD_PARENT.items():
        got = d["tree"].get(part)
        topo["parents"][part] = {"draft": got, "artist": gt_parent, "match": got == gt_parent}
    for part in AWARD_ROOT_LEVEL:
        got_root = (d["roles"].get(part) == "effect") and (part not in d["tree"])
        topo["root_level"][part] = {"draft_role": d["roles"].get(part), "match": got_root}
    topo_pass = (topo["trunk"]["match"]
                 and all(v["match"] for v in topo["parents"].values())
                 and all(v["match"] for v in topo["root_level"].values()))

    # AC2 pivot 距離(可比件:limb + trunk;effect 不可比)
    rows, worst = [], 0.0
    for part, gt in artist.items():
        if part in AWARD_ROOT_LEVEL:
            rows.append({"part": part, "comparable": False,
                         "note": "藝術家綁場景錨(pivot 在件外)— 全域擺位決策,A 類留人",
                         "artist_norm": [round(gt["px"][0] / gt["size"][0], 3),
                                         round(gt["px"][1] / gt["size"][1], 3)]})
            continue
        cv = d["pivots_px"][part]
        ox, oy = offsets[part]
        draft_px = [cv[0] - ox, cv[1] - oy]           # 畫布 px → 件影像 px
        # Award attachment 的 width/height 比 PSD 件大 2px(atlas padding)→ 座標系一致取件中心對齊
        dxy = math.hypot(draft_px[0] - gt["px"][0] + 1, draft_px[1] - gt["px"][1] + 1)
        diag = math.hypot(*gt["size"])
        dn = dxy / diag
        worst = max(worst, dn)
        rows.append({"part": part, "comparable": True,
                     "draft_px": [round(v, 1) for v in draft_px],
                     "artist_px": gt["px"], "dist_px": round(dxy, 1),
                     "dist_norm": round(dn, 3), "pass": dn <= pivot_tol})
    pivot_pass = all(r["pass"] for r in rows if r.get("comparable"))

    return {"overall_pass": topo_pass and pivot_pass,
            "AC1_topology": {"pass": topo_pass, **topo},
            "AC2_pivot_distance": {"pass": pivot_pass, "tol_norm": pivot_tol,
                                   "worst_norm": round(worst, 3), "rows": rows}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", default="/tmp/robot_draft.json")
    ap.add_argument("--manifest", default="/tmp/robot_parts/manifest.json")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tol", type=float, default=0.15)
    a = ap.parse_args()
    rep = validate(a.draft, a.manifest, a.award, a.tol)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
