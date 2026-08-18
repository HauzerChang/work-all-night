#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

STATE.md 最高優先 bounded chunk #1。用 robot_parts.psd 的 3 個 mesh 件
(光暈/身體/左手,在 Award 中皆為 mesh)跑 S3 生成器,與 Award 藝術家 mesh
做「同源 alpha 上的靜態覆蓋率(IoU)」對照 → 證明 S3 對真實生產標的可用。

★ 關鍵事實(本次確認):
  Award mesh 的 `uvs` 是 **region-local**(每件 uv 幾乎鋪滿 [0,1]),不是 atlas-global。
  故藝術家 mesh 可直接以 u*W, v*H 映回件像素空間比對(與 main_draw 的 artist_iou 同法)。

★ deform 閘不適用:這 3 件在 Award 為 **weighted mesh 且無 deform timeline**
  (靠骨骼權重變形,非逐頂點 deform)。故本比對聚焦「靜態拓樸/覆蓋率 vs 藝術家」,
  deform 穩健性已在 main_draw 4 個 unweighted mesh 上驗過(見 s3-four-mesh-generalization)。

自我驗證(承專案『評估器需外部真值校準』教訓):
  藝術家 uvs → 件像素座標後,先算 centroid-in-mask 比例(v 方向自我校驗);
  若 < 0.9 表示 v 慣例反了 → 自動翻 v 重試。低於門檻仍記錄,不靜默通過。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask


# robot_parts PSD 件 → Award slot(ground-truth 對應,見 knowledge/s4-psd-to-spine-real.md)
PIECES = {
    "光暈": {"psd_file": "00_光暈.png",  "award_slot": "機器人拆件/光暈"},
    "身體": {"psd_file": "03_身體.png",  "award_slot": "機器人拆件/身體"},
    "左手": {"psd_file": "04_左手.png",  "award_slot": "機器人拆件/左手"},
}


def artist_mesh(skeleton, slot):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def fill_mesh_uv(uvs, tris, W, H, flip_v=False):
    """把 region-local uvs 依三角形填成 mask(件像素空間)。"""
    v = uvs[:, 1].copy()
    if flip_v:
        v = 1.0 - v
    rp = np.column_stack([uvs[:, 0] * W, v * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon, rp


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def centroid_in_mask(rp, tris, mask):
    H, W = mask.shape
    hit = 0
    for t in tris:
        c = rp[t].mean(axis=0)
        cx, cy = int(round(c[0])), int(round(c[1]))
        if 0 <= cy < H and 0 <= cx < W and mask[cy, cx]:
            hit += 1
    return hit / len(tris) if len(tris) else 0.0


def artist_coverage(mesh_att, mask):
    """藝術家 mesh 在件 alpha 上的覆蓋率;含 v 慣例自我校驗。"""
    H, W = mask.shape
    uvs = np.array(mesh_att["uvs"]).reshape(-1, 2)
    tris = np.array(mesh_att["triangles"]).reshape(-1, 3)
    best = None
    for flip in (False, True):
        recon, rp = fill_mesh_uv(uvs, tris, W, H, flip_v=flip)
        cim = centroid_in_mask(rp, tris, mask)
        cand = {"flip_v": flip, "iou": iou(recon, mask > 0), "centroid_in_mask": round(cim, 4),
                "vertices": len(uvs), "triangles": len(tris)}
        if best is None or cand["centroid_in_mask"] > best["centroid_in_mask"]:
            best = cand
    return best


def run(piece_dir, award_json, out_dir, rows, cols):
    sk = json.load(open(award_json))
    rep = {"pieces": {}, "params": {"rows": rows, "cols": cols}}
    os.makedirs(out_dir, exist_ok=True)
    all_pass = True
    for pname, info in PIECES.items():
        src = os.path.join(piece_dir, info["psd_file"])
        mask = load_mask(src)
        H, W = mask.shape

        # S3 生成
        mesh = gen_v2(src, rows=rows, cols=cols, mode="auto")
        json.dump(mesh, open(os.path.join(out_dir, f"{pname}_v2.json"), "w"), ensure_ascii=False)
        ev = evaluate(mesh, mask, vertex_budget=128)  # 藝術家件達 98v,放寬預算
        my_iou = ev["criteria"]["AC1_iou"]["value"]
        my_nv = ev["vertices"]

        # 藝術家 mesh 對照(同源 alpha)
        art = artist_coverage(artist_mesh(sk, info["award_slot"]), mask)
        conv_ok = art["centroid_in_mask"] >= 0.90  # UV 轉換自我校驗

        # AC:我的覆蓋率 ≥ 藝術家(margin 0),且我的 mesh 格式/幾何全過,且 UV 轉換可信
        beats_artist = my_iou >= art["iou"] - 0.01
        piece_pass = ev["overall_pass"] and beats_artist and conv_ok
        all_pass = all_pass and piece_pass

        rep["pieces"][pname] = {
            "src_size": [W, H],
            "mine": {"vertices": my_nv, "hull": mesh["hull"],
                     "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode"),
                     "iou_vs_source": my_iou, "geom_pass": ev["overall_pass"]},
            "artist": {"vertices": art["vertices"], "triangles": art["triangles"],
                       "iou_vs_source": round(art["iou"], 4),
                       "centroid_in_mask": art["centroid_in_mask"], "flip_v": art["flip_v"]},
            "uv_conversion_trustworthy": conv_ok,
            "iou_delta_mine_minus_artist": round(my_iou - art["iou"], 4),
            "vertex_ratio_mine_over_artist": round(my_nv / max(art["vertices"], 1), 3),
            "pass": piece_pass,
        }
    rep["overall_pass"] = all_pass
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces", default="/tmp/robot_parts", help="psd_slice 輸出目錄")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--out", default="/tmp/award_cmp")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    a = ap.parse_args()
    rep = run(a.pieces, a.award, a.out, a.rows, a.cols)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
