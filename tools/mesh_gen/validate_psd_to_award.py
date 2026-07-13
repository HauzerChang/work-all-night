#!/usr/bin/env python3
"""端到端整合 AC:分層 PSD 件 → S3 generate_mesh_v2 → 對照真實生產 spine(Award)的藝術家 mesh。

情境:`robot_parts.psd` 的三件(光暈/身體/左手)在生產 spine `Award` 中被美術做成 mesh。
用 PSD 切件的**全解析度 alpha**(無旋轉、無 0.70 atlas 縮放)當來源生成 mesh,
與 Award 藝術家 mesh 做**靜態輪廓 IoU** 與拓樸品質對照。

⚠️ 這五件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
故真實位移場轉移閘(main_draw 用的硬約束)在此**不適用** —— 本工具只驗靜態輪廓+拓樸,
不對這些件宣稱 deform 穩健(見 knowledge/s3-s4-end-to-end-robot.md)。

Award mesh uvs 座標系先以「藝術家 mesh vs 件 alpha」自一致性經驗校準(挑最佳朝向變體),
再據以計算藝術家基準 IoU —— 避免座標系假設錯誤污染結論。

用法:python3 tools/mesh_gen/validate_psd_to_award.py [--psd assets/robot_parts.psd]
       [--skeleton assets/Award.json] [--prefix 機器人拆件] [--out /tmp/robot_pieces]
"""
import argparse, json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate

MESH_PIECES = ["光暈", "身體", "左手"]  # Award 中為 mesh 的三件(右手/頭為 region)

VARIANTS = {
    "identity": lambda u: u,
    "flipY":    lambda u: np.column_stack([u[:, 0], 1 - u[:, 1]]),
    "flipX":    lambda u: np.column_stack([1 - u[:, 0], u[:, 1]]),
    "flipXY":   lambda u: np.column_stack([1 - u[:, 0], 1 - u[:, 1]]),
}


def mask_from(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    a = img[:, :, 3] if img.ndim == 3 and img.shape[2] == 4 else img
    return (a > 8).astype(np.uint8)


def render_mesh(uvs, tris, W, H):
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(rp[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def run(psd_path, skeleton_path, prefix, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    _, manifest, _ = slice_psd(psd_path, out_dir)
    name2file = {p["name"]: os.path.join(out_dir, p["file"]) for p in manifest["parts"]}

    sk = json.load(open(skeleton_path))
    skins = sk["skins"]; skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)

    report = {}
    for layer in MESH_PIECES:
        slot = f"{prefix}/{layer}"
        a = att[slot][slot]
        uvs = np.array(a["uvs"]).reshape(-1, 2)
        tris = np.array(a["triangles"]).reshape(-1, 3)
        mask = mask_from(name2file[layer]); H, W = mask.shape

        # 校準藝術家 mesh 朝向(對齊件 alpha)
        best = max(VARIANTS.items(),
                   key=lambda kv: iou(render_mesh(kv[1](uvs), tris, W, H), mask))
        art_iou = iou(render_mesh(best[1](uvs), tris, W, H), mask)

        mesh = gen_v2(name2file[layer], mode="auto")
        ev = evaluate(mesh, mask); c = ev["criteria"]
        gen_iou = c["AC1_iou"]["value"]

        report[layer] = {
            "piece_size": [int(W), int(H)],
            "artist": {"verts": len(uvs), "tris": len(tris), "hull": a.get("hull"),
                       "orient": best[0], "iou_vs_alpha": round(art_iou, 4)},
            "generated_v2": {"mode": mesh.get("_mode"), "verts": len(mesh["uvs"]) // 2,
                             "tris": len(mesh["triangles"]) // 3, "hull": mesh["hull"],
                             "iou_vs_alpha": round(gen_iou, 4)},
            "gen_meets_artist_baseline": bool(gen_iou >= art_iou),
            "topology_clean": bool(c["AC2a_centroid_in_mask"]["pass"]
                                   and c["AC2b_degenerate"]["pass"]
                                   and c["AC2c_orphans"]["pass"]),
            "AC1_iou_pass": bool(c["AC1_iou"]["pass"]),  # 對齊固定 0.9 門檻
        }
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--prefix", default="機器人拆件")
    ap.add_argument("--out", default="/tmp/robot_pieces")
    a = ap.parse_args()
    rep = run(a.psd, a.skeleton, a.prefix, a.out)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    # 收斂條件:每件 AC1(0.9)過 + 拓樸乾淨 + 座標校準為 identity(座標系一致)
    ok = all(v["AC1_iou_pass"] and v["topology_clean"]
             and v["artist"]["orient"] == "identity" for v in rep.values())
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
