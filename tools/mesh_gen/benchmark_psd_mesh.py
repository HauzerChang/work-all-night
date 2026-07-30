#!/usr/bin/env python3
"""S3×S4 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(ground truth)。

背景(knowledge/s4-psd-to-spine-real.md):`robot_parts.psd`(「機器人拆件」)的
光暈/身體/左手 3 件,在生產 spine `Award.json` 中是**藝術家手做 mesh**(有真值可比)。
右手/頭是 region(剛體),不在此列。

本工具把兩條能力串起來做真實標的驗收:
  psd_slice 切件 PNG → generate_mesh_v2 生成 mesh → 對「同一件 alpha」比
  ①覆蓋率 IoU(vs 藝術家 mesh 的覆蓋率)②頂點經濟度 ③setup 幾何合法(含 0 自交)
  ④真實位移場轉移下的拓樸穩健(vs 藝術家 mesh)。

★ 座標基準(踩過的雷,務必記住):
  - Award mesh 的 local `vertices` **不是**以中心原點、跨滿 width×height —— 有 attachment
    層級的偏移/縮放(光暈 local 跨 803×781,wh 只有 708×685,且不對稱)。**不可**用
    `v/wh+0.5` 映射到件像素框(初版此 bug 使藝術家 IoU 假性掉到 0.47~0.62)。
  - **正確基準 = `uvs`**(region-normalized [0,1],即紋理座標),與 generate 的 uv 慣例
    (u=x/W, v=y/H)同一空間 → 兩者都用 uv 映到件像素框比覆蓋率,apples-to-apples。
    校正後藝術家 IoU = 0.949 / 0.948 / 0.977(合理,藝術家理應蓋好自己的紋理)。

★ deform 閘(scale-normalized 真實場轉移):這 3 件在 Award **無 deform timeline**(靠骨骼/
  權重變形,非逐頂點 deform),無自身真實位移場。改**轉移 main_draw curtain_left 的真實
  位移場**(run.md 守則:用真實位移場,不用未校準 stress_field)。為公平且校準:
    - 把 curtain 場正規化成「佔 curtain 自身 bbox 對角線的比例」→ 消除絕對 px 尺度;
    - 生成 mesh 與藝術家 mesh 都放進同一單位框(geometry = uv×S,S=256),受同一正規化場。
  → 探針幅度 = curtain 最猛真實幀(315px ≈ 自身 49%)等比套到本件(單位框中最大位移 ~126/256)。
  這是「跟 curtain 最硬的真實幀一樣猛、等比縮到本件」的外來場穩健度探針(標為外來場,honest)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate as static_eval, mesh_pixel_coords
import generate_mesh_v2 as gv2
import deform_eval as de

UNIT = 256.0
IOU_MARGIN = 0.02

# PSD 圖層名 → Award slot/attachment(僅 mesh 件;右手/頭為 region 不列)
MESH_MAP = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def award_attachment(sk, key):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[key][key]


def uv_fill_iou(uvs, tris, mask):
    """把三角形(uv→件像素)填滿與 mask 比 IoU。uv 為 region-normalized [0,1](v top-down)。"""
    H, W = mask.shape
    px = np.column_stack([np.asarray(uvs)[:, 0] * W, np.asarray(uvs)[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(px[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return inter / union if union else 0.0


def unit_frame_mesh(uvs, tris, hull):
    """把 mesh 放進單位框:geometry = uv×UNIT,uvs 保留供場內插。消除絕對尺度 → 公平比較。"""
    uv = np.asarray(uvs, dtype=np.float64).reshape(-1, 2)
    return {"vertices": [float(x) for p in uv * UNIT for x in p],
            "uvs": [float(x) for p in uv for x in p],
            "triangles": [int(i) for t in tris for i in t], "hull": int(hull)}


def normalized_field(fsk, slot):
    """curtain 真實最大位移場,正規化成『佔自身 bbox 對角線比例』(消 px 尺度)。"""
    uvs_src, field, frame = de.real_deform_field(fsk, slot, slot)
    skin = fsk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    ca = skin.get("attachments", skin)[slot][slot]
    cv_ = np.array(ca["vertices"], dtype=np.float64).reshape(-1, 2)
    diag = float(np.hypot(*(cv_.max(0) - cv_.min(0)))) or 1.0
    return uvs_src, field / diag * UNIT, frame, float(np.hypot(field[:, 0], field[:, 1]).max())


def setup_self_intersections(mesh):
    """generate 輸出在 setup pose 的自交數(calibration-free 合法性)。"""
    pts, _, _ = mesh_pixel_coords(mesh)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    return de.check(pts, tris, None)["self_intersections"]


def bench_piece(name, piece_img, att, field_src):
    arr = np.array(piece_img)
    alpha = arr[:, :, 3] if arr.ndim == 3 and arr.shape[2] == 4 else arr
    mask = (alpha > 8).astype(np.uint8)
    tmp = os.path.join("/tmp", f"_piece_{MESH_MAP[name].replace('/', '_')}.png")
    cv2.imwrite(tmp, cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA))

    # ── 生成 mesh ──
    mesh = gv2.generate(tmp, mode="auto")
    gen_uv = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    gen_tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    gen_nv = len(gen_uv)

    st = static_eval(mesh, mask, vertex_budget=64, iou_thresh=0.0)
    gen_iou = st["criteria"]["AC1_iou"]["value"]
    gen_setup_si = setup_self_intersections(mesh)

    # ── 藝術家 mesh(ground truth)──
    art_uv = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)
    art_tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    art_iou = uv_fill_iou(art_uv, art_tris, mask)
    art_nv = len(art_uv)

    # ── deform 穩健(scale-normalized 外來真實場,單位框)──
    uvs_src, field_n, frame, field_px = field_src
    gen_d = de.transfer_deform_check(unit_frame_mesh(gen_uv, gen_tris, mesh["hull"]), uvs_src, field_n)
    art_d = de.transfer_deform_check(unit_frame_mesh(art_uv, art_tris, att["hull"]), uvs_src, field_n)

    ac_cover = gen_iou >= art_iou - IOU_MARGIN
    ac_econ = gen_nv <= art_nv
    ac_setup = (st["criteria"]["AC4_format"]["pass"]
                and st["criteria"]["AC2b_degenerate"]["pass"]
                and st["criteria"]["AC2c_orphans"]["pass"]
                and st["criteria"]["AC2a_centroid_in_mask"]["pass"]
                and gen_setup_si == 0)
    ac_deform = gen_d["self_intersections"] <= art_d["self_intersections"] and gen_d["triangle_flips"] == 0
    return {
        "piece": name, "slot": MESH_MAP[name], "gen_mode": mesh.get("_mode"),
        "AC_cover": {"gen_iou": round(gen_iou, 4), "artist_iou": round(art_iou, 4),
                     "margin": IOU_MARGIN, "pass": bool(ac_cover)},
        "AC_economy": {"gen_verts": gen_nv, "artist_verts": art_nv,
                       "saved": f"{100 * (art_nv - gen_nv) / art_nv:.0f}%", "pass": bool(ac_econ)},
        "AC_setup_valid": {"format": st["criteria"]["AC4_format"]["pass"],
                           "degenerate": st["criteria"]["AC2b_degenerate"]["value"],
                           "orphans": st["criteria"]["AC2c_orphans"]["value"],
                           "centroid_in_mask": st["criteria"]["AC2a_centroid_in_mask"]["value"],
                           "setup_self_intersections": gen_setup_si, "pass": bool(ac_setup)},
        "AC_deform_robust": {"probe": f"{frame} real field, scale-normalized (unit-frame max ~{field_n_max(field_n):.0f}/{int(UNIT)})",
                             "gen": {"si": gen_d["self_intersections"], "flips": gen_d["triangle_flips"],
                                     "area_ratio": gen_d["area_ratio"]},
                             "artist": {"si": art_d["self_intersections"], "flips": art_d["triangle_flips"],
                                        "area_ratio": art_d["area_ratio"]},
                             "note": "foreign-field probe (件在 Award 無自身 deform)", "pass": bool(ac_deform)},
        "overall_pass": bool(ac_cover and ac_econ and ac_setup and ac_deform),
    }


def field_n_max(field_n):
    return float(np.hypot(field_n[:, 0], field_n[:, 1]).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--field-skeleton", default="assets/main_draw.json")
    ap.add_argument("--field-slot", default="image/curtain_left")
    a = ap.parse_args()

    sk = json.load(open(a.award))
    fsk = json.load(open(a.field_skeleton))
    field_src = normalized_field(fsk, a.field_slot)  # (uvs, field_n, frame, field_px)

    _, _, parts = slice_psd(a.psd)  # [(entry, PIL_img)]
    by_name = {e["name"]: im for e, im in parts}

    reports = []
    for name in MESH_MAP:
        if name not in by_name:
            reports.append({"piece": name, "error": "PSD 無此圖層", "overall_pass": False})
            continue
        att = award_attachment(sk, MESH_MAP[name])
        reports.append(bench_piece(name, by_name[name], att, field_src))

    out = {"source": os.path.basename(a.psd),
           "field": f"{a.field_slot}@{os.path.basename(a.field_skeleton)} (max real {field_src[3]:.0f}px)",
           "pieces": reports,
           "overall_pass": all(r.get("overall_pass") for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
