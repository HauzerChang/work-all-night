#!/usr/bin/env python3
"""端到端 S4→S3:分層 PSD 的件 → 生成 mesh → 對照「真實生產 spine 的藝術家 mesh」。

這是 S3 mesh 生成器**跨資產推廣**的第一個驗收:先前只在 main_draw 的 4 個
unweighted 窗簾/陰影 mesh 收斂;本工具把它接到 S4(psd_slice)前段,對第二份生產
資產 Award(機器人 big win)裡真正是 mesh 的件跑一遍,並以「藝術家自己的 mesh 對
自身輪廓的覆蓋率」為基準判定 pass/fail。

流程(每件):
  PSD 圖層 → 緊湊 PNG(件 alpha) → generate_mesh(v1/v2 auto) → 靜態品質閘
  → 生成 mesh 的輪廓覆蓋率 IoU(對件 alpha) vs 藝術家 mesh 覆蓋率(對 Award atlas
    切出的同 region alpha)基準 → 頂點精簡度對照。

⚠️ 範圍界定(誠實):Award 機器人 mesh 為 **weighted(骨骼驅動)**,其變形靠 bone
   skinning 而非 deform timeline,故本閘**只驗靜態輪廓覆蓋 + mesh 合法性 + 精簡度**,
   不主張 deform 穩健性(weighted deform 重現屬後續能力,見 STATE 下一步)。
   PSD 件(全解析度)與 atlas region(Award 打包 ~0.70 縮小)是同素材的兩個尺度
   (先前 alpha-IoU 0.92~0.99 已證同素材);兩邊各自「mesh 覆蓋自身輪廓」故可比。

自我驗證迴圈(RULES:5 輪預算):delaunay 模式下若 IoU 未達基準,自動把輪廓簡化
   epsilon 減半(細化邊界取樣)重試,最多 5 輪 —— 對「軟邊/圓形」件(如光暈)必要。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from psd_tools import PSDImage
from evaluate_mesh import evaluate as eval_mesh
from atlas_crop import extract

EPS_START, EPS_FLOOR, MAX_ROUNDS = 0.008, 0.002, 5


def piece_png(psd_path, layer_name, out_dir):
    psd = PSDImage.open(psd_path)
    layers = {l.name: l for l in psd.descendants() if not l.is_group()}
    if layer_name not in layers:
        raise SystemExit(f"PSD 無此圖層: {layer_name}(有 {list(layers)})")
    im = layers[layer_name].topil()
    if im is None:
        raise SystemExit(f"圖層無像素: {layer_name}")
    im = im.convert("RGBA")
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, layer_name.replace("/", "__") + ".png")
    im.save(p)
    return p


def artist_baseline(skeleton, slot, name, atlas, png):
    """藝術家 mesh 對其自身 region alpha 的覆蓋率(基準線)。回傳 (iou, n_vertices)。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    a = atts[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    sub = extract(atlas, png, name)
    if sub is None or sub.ndim != 3 or sub.shape[2] != 4:
        return None, len(uvs)
    mask = (sub[:, :, 3] > 8).astype(np.uint8)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    iou = float(np.logical_and(recon, mask).sum() / max(np.logical_or(recon, mask).sum(), 1))
    return iou, len(uvs)


def gen_with_refine(png, target_iou, budget):
    """生成 mesh;delaunay 模式下 IoU 未達 target 時,細化 epsilon 重試(≤5 輪)。
    回傳 (mesh, gen_iou, gate_pass, rounds, mask)。"""
    from generate_mesh_v2 import generate as gv2, load_mask
    from generate_mesh import generate as gv1
    mask, W, H = load_mask(png); mask = (mask > 0).astype(np.uint8)

    mesh = gv2(png, mode="auto")
    rep = eval_mesh(mesh, mask, vertex_budget=budget)
    iou = rep["criteria"]["AC1_iou"]["value"]
    rounds = 1
    # 只有 delaunay 路徑吃 epsilon;strip 已由 rows 決定覆蓋率(另有其驗收)
    if mesh.get("_mode") == "delaunay-v1":
        eps = EPS_START
        while iou < target_iou and eps > EPS_FLOOR and rounds < MAX_ROUNDS:
            eps = max(EPS_FLOOR, eps / 2.0)
            rounds += 1
            m, _ = gv1(png, epsilon_frac=eps, min_dist=8)
            m["_mode"] = f"delaunay-v1-refined(eps={eps:.3f})"
            r = eval_mesh(m, mask, vertex_budget=budget)
            i = r["criteria"]["AC1_iou"]["value"]
            if i > iou:
                mesh, rep, iou = m, r, i
            if iou >= target_iou:
                break
    return mesh, iou, rep, rounds, mask


def validate(psd, skeleton_path, atlas, png, mapping, margin, budget, tmp):
    sk = json.load(open(skeleton_path))
    report = {"psd": os.path.basename(psd), "skeleton": os.path.basename(skeleton_path),
              "margin": margin, "pieces": []}
    for layer, slot in mapping.items():
        p = piece_png(psd, layer, tmp)
        base_iou, base_nv = artist_baseline(sk, slot, slot, atlas, png)
        target = (base_iou - margin) if base_iou is not None else 0.95
        mesh, gen_iou, rep, rounds, _ = gen_with_refine(p, target, budget)
        gen_nv = len(mesh["uvs"]) // 2
        iou_pass = base_iou is None or gen_iou >= base_iou - margin
        piece = {
            "layer": layer, "slot": slot, "mode": mesh.get("_mode"),
            "gen_vertices": gen_nv, "gen_iou": round(gen_iou, 4),
            "artist_vertices": base_nv,
            "artist_baseline_iou": round(base_iou, 4) if base_iou is not None else None,
            "refine_rounds": rounds,
            "AC1_coverage_vs_artist": {"pass": bool(iou_pass),
                                       "gap": round((gen_iou - base_iou), 4) if base_iou is not None else None},
            "AC2_mesh_gate": {"pass": bool(rep["overall_pass"]),
                              "fails": [k for k, v in rep["criteria"].items() if not v["pass"]]},
            "AC3_parsimony": {"pass": base_nv is None or gen_nv <= base_nv,
                              "detail": f"gen {gen_nv} vs artist {base_nv}"},
        }
        piece["pass"] = all(piece[k]["pass"] for k in
                            ("AC1_coverage_vs_artist", "AC2_mesh_gate", "AC3_parsimony"))
        report["pieces"].append(piece)
    report["overall_pass"] = all(p["pass"] for p in report["pieces"])
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    # PSD 圖層 → Award slot(機器人拆件裡真正是 mesh 的 3 件)
    ap.add_argument("--pieces", default="光暈=機器人拆件/光暈,左手=機器人拆件/左手,身體=機器人拆件/身體")
    ap.add_argument("--margin", type=float, default=0.015,
                    help="容許生成 IoU 低於藝術家基準的幅度")
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--tmp", default="/tmp/psd2mesh")
    a = ap.parse_args()
    mapping = dict(kv.split("=", 1) for kv in a.pieces.split(","))
    rep = validate(a.psd, a.skeleton, a.atlas, a.png, mapping, a.margin, a.budget, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
