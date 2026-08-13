#!/usr/bin/env python3
"""端到端驗收:PSD 拆件 → S3 生成 mesh → 對照 Award 真實生產 mesh(靜態覆蓋率)。

背景(見 knowledge/s3-robot-mesh-vs-award.md):
  `robot_parts.psd` 的 光暈/身體/左手 三件在生產 spine `Award.json` 中是 **mesh**;
  另兩件(右手/頭)是 region。這三件 **無 deform timeline** → 靠骨骼權重變形,不做逐頂點
  deform,故此處 AC = 「生成 mesh 對切件 alpha 的覆蓋率 IoU」對照「藝術家 mesh 自身覆蓋率」。

流程:
  1. `psd_slice` 切 robot_parts.psd → 各件 alpha PNG。
  2. Award mesh uvs 為 **region-local 0..1(原始未旋轉方向)** → 直接 *W,*H 重建覆蓋(藝術家基準)。
     (經驗證:rotate=true 的件其 uvs 仍在原始方向,無需旋轉換算;三件 rot0 IoU 0.949/0.948/0.977
      遠高於 ±90°,證明方向正確。)
  3. `generate_mesh_v2`(auto → 非 strip 走 Delaunay 分支)生成 mesh → 覆蓋率 IoU。
  4. AC:生成 IoU ≥ 藝術家基準 − margin。

純 CPU、可自驅;不需 Award.png(用 PSD 切件的 alpha 當真值)。
"""
import argparse, json, os, sys, subprocess
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask

# PSD 圖層檔名 → (Award slot 後綴, 切件 PNG 檔名)
PIECES = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def award_attachment(sk, slot):
    skins = sk["skins"]
    d = skins[0]["attachments"] if isinstance(skins, list) else skins["default"]
    return d[slot][slot]


def artist_iou(att, mask):
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())


def piece_mask(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim != 3 or img.shape[2] != 4:
        raise SystemExit(f"切件需含 alpha: {path}")
    return (img[:, :, 3] > 8).astype(np.uint8)


def validate(psd, award_json, slices_dir, margin=0.005):
    if not os.path.isdir(slices_dir) or not os.path.exists(os.path.join(slices_dir, "manifest.json")):
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "psd_slice.py"),
                        psd, "-o", slices_dir], check=True, stdout=subprocess.DEVNULL)
    sk = json.load(open(award_json))
    rows, all_pass = [], True
    for layer, fname in PIECES.items():
        path = os.path.join(slices_dir, fname)
        mask = piece_mask(path)
        att = award_attachment(sk, "機器人拆件/" + layer)
        base = artist_iou(att, mask)
        mesh = gen_v2(path, mode="auto")
        gen_iou = evaluate(mesh, load_mask(path))["criteria"]["AC1_iou"]["value"]
        ok = gen_iou >= base - margin
        all_pass &= ok
        rows.append({
            "piece": layer,
            "mask": list(mask.shape[::-1]),
            "artist": {"verts": len(att["uvs"]) // 2, "iou": round(base, 4)},
            "generated": {"mode": mesh.get("_mode"), "verts": len(mesh["uvs"]) // 2,
                          "iou": round(gen_iou, 4)},
            "pass": ok,
        })
    return {"pieces": rows, "overall_pass": all_pass}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--slices", default="/tmp/robot_slices")
    ap.add_argument("--margin", type=float, default=0.005)
    a = ap.parse_args()
    rep = validate(a.psd, a.award, a.slices, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
