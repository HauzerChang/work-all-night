#!/usr/bin/env python3
"""端到端「PSD 件 → S3 mesh」對真實生產標的(Award spine)驗收。

背景(STATE 下一步 #1):Award 機器人拆件有 3 個 **mesh** 件(光暈/身體/左手,皆 weighted),
與 robot_parts.psd 的 3 個圖層一一對應。此腳本對每件:
  1. 從 Award atlas 切出 region alpha(atlas_crop,已校正 CW derotate)。
  2. 用 S3 `generate_mesh_v2(mode=auto)` 自動生成 mesh。
  3. 量 IoU(生成 mesh 覆蓋 vs region alpha),對照「藝術家 mesh 覆蓋率」基準。
  4. rest-pose 幾何閘:生成 mesh 0 自交 / 0 翻面 / 三角形索引合法。
  5. (交叉)對 PSD 全解析度件也跑一次生成,確認自動路由與覆蓋率不因來源而崩。

⚠️ 這 3 件在 Award **無 deform**(靠骨骼剛體/權重移動,session 005 確認),
   故不做 deform 轉移閘(無藝術家真值可轉),改以 rest-pose 幾何 + IoU 覆蓋率為 AC。

判定(L2 自主、客觀項):
  - AC_iou: 生成 mesh IoU >= 藝術家基準 - margin(margin=0.03,對照 curtain 慣例)。
  - AC_geom: rest-pose 0 自交 / 0 翻面 / 索引合法。
  - AC_route: mode 記錄(strip / delaunay-v1);非硬 pass,供分析。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
import deform_eval as de

PARTS = ["光暈", "身體", "左手"]


def has_deform(sk, slot, name):
    for anim in sk.get("animations", {}).values():
        d = anim.get("deform", {})
        for skin_v in d.values():
            if slot in skin_v and name in skin_v[slot]:
                return True
    return False


def rest_geom(mesh):
    """rest-pose 幾何品質:自交/翻面/索引。用 deform_eval 的檢查(零位移場)。"""
    pts, W, H = de_mesh_pixels(mesh)
    tris = np.array(mesh["triangles"], np.int32).reshape(-1, 3)
    signs = [de.signed_area(pts, t) > 0 for t in tris]  # 每三角形 setup 朝向
    res = de.check(pts, tris, signs)
    idx_ok = bool(tris.size) and int(tris.max()) < len(pts) and int(tris.min()) >= 0
    return {"self_intersections": res["self_intersections"],
            "triangle_flips": res["triangle_flips"],
            "index_valid": idx_ok,
            "clean": res["self_intersections"] == 0 and res["triangle_flips"] == 0 and idx_ok}


def de_mesh_pixels(mesh):
    """mesh vertices(center-origin, y-up) → 像素座標(y-down)。"""
    W, H = mesh["width"], mesh["height"]
    v = np.array(mesh["vertices"], float).reshape(-1, 2)
    x = v[:, 0] + W / 2.0
    y = H / 2.0 - v[:, 1]
    return np.column_stack([x, y]), W, H


def run_part(sk, atlas, png, part, tmp, psd_alpha_dir, margin):
    slot = name = f"機器人拆件/{part}"
    # 1. atlas region alpha(原始朝向)
    sub = extract(atlas, png, name)
    if sub.ndim == 3 and sub.shape[2] == 4:
        alpha = sub[:, :, 3]
    else:
        alpha = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) if sub.ndim == 3 else sub
    region_png = os.path.join(tmp, f"_region_{part}.png")
    cv2.imwrite(region_png, sub)
    mask = load_mask(region_png)

    base = artist_iou(sk, slot, name, mask)

    # 2. 生成 + 量測(atlas region 來源)
    mesh = gen_v2(region_png, mode="auto")
    ev = evaluate(mesh, mask)
    iou = ev["criteria"]["AC1_iou"]["value"]
    geom = rest_geom(mesh)

    # 3. 交叉:PSD 全解析度件(若已切出)
    cross = None
    psd_png = os.path.join(psd_alpha_dir, f"{part}.png")
    if os.path.exists(psd_png):
        pmask = load_mask(psd_png)
        pmesh = gen_v2(psd_png, mode="auto")
        pev = evaluate(pmesh, pmask)
        cross = {"iou": pev["criteria"]["AC1_iou"]["value"],
                 "mode": pmesh.get("_mode"),
                 "vertices": len(pmesh["uvs"]) // 2}

    ac_iou = iou >= base - margin
    return {
        "part": part, "slot": slot,
        "region_alpha": f"{mask.shape[1]}x{mask.shape[0]}",
        "artist": {"has_deform": has_deform(sk, slot, name),
                   "mesh_verts": len(sk_att(sk, slot, name)["uvs"]) // 2,
                   "iou_baseline": round(base, 4)},
        "generated": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                      "triangles": len(mesh["triangles"]) // 3, "hull": mesh["hull"],
                      "iou": round(iou, 4)},
        "cross_psd_fullres": cross,
        "AC_iou": {"pass": ac_iou, "value": round(iou, 4),
                   "baseline": round(base, 4), "margin": margin},
        "AC_geom": geom,
        "overall_pass": ac_iou and geom["clean"],
    }


def sk_att(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--psd-alpha-dir", default="/tmp/robot_psd_parts")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [run_part(sk, a.atlas, a.png, p, a.tmp, a.psd_alpha_dir, a.margin) for p in PARTS]
    summary = {"parts": len(reports),
               "all_pass": all(r["overall_pass"] for r in reports),
               "reports": reports}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["all_pass"] else 1)


if __name__ == "__main__":
    main()
