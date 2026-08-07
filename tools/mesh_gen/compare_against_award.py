#!/usr/bin/env python3
"""S3+S4 端到端驗收:PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(STATE.md next-action #1):robot_parts.psd 的 光暈/左手/身體 三件,在真實生產
spine `Award` 中是 weighted mesh(藝術家手做)。本工具把「PSD→件→自動生成 mesh」對這三
個真實標的做量化對照,是 S3(mesh 生成)+ S4(PSD 切圖)串成端到端、且對**真實藝術家真值**
的驗收。純 CPU、無需 Award.png 對位(在正規化 UV 空間比對)。

**為何比得動(關鍵幾何洞察)**:Spine mesh 的 `uvs` 是 [0,1] 正規化紋理座標,`width/height`
是**原始藝術尺寸**(非 atlas 縮小後)。實測 Award mesh W,H(708×685 / 259×217 / 381×427)
≈ PSD 件 bbox(706×683 / 257×215 / 379×425,±2px)⇒ 藝術家 mesh 的 uvs 與生成 mesh 的
uvs 落在**同一件原生藝術的正規化空間**。故可直接在 UV 空間疊合比對,不需 atlas 反旋轉/縮放
對位(那條路已在 s4-psd-to-spine-real 用 alpha-IoU 確認同素材)。

比對指標(每件):
  1. cover_iou_gen  = 生成 mesh 三角覆蓋 vs 件 alpha(正規化網格) — 生成品質。
  2. cover_iou_real = 藝術家 mesh 三角覆蓋 vs 件 alpha — 真值品質基準。
  3. footprint_iou  = 生成 mesh 覆蓋 ∩ 藝術家 mesh 覆蓋 / ∪ — 兩者輪廓一致度。
  4. verts_gen / verts_real — 精簡度(生成應 ≤ 藝術家)。

AC(逐件):
  E1 生成 mesh 格式合法(evaluate_mesh 全過)。
  E2 cover_iou_gen ≥ 0.90(覆蓋件本體)。
  E3 cover_iou_gen ≥ 0.95 × cover_iou_real(覆蓋不遜於藝術家)且 footprint_iou ≥ 0.80。
  E4 verts_gen ≤ verts_real(更精簡或相當)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_mesh_v2 as gmv2
import evaluate_mesh as em


GRID = 512  # 正規化比對網格邊長


def load_alpha_norm(png_path, grid=GRID):
    """讀件 PNG → alpha → 正規化到 grid×grid(以件的緊湊 bbox 為 [0,1]²)。"""
    img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到: {png_path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = (img[:, :, 3] > 8).astype(np.uint8)
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = (g > 8).astype(np.uint8)
    a = cv2.resize(a, (grid, grid), interpolation=cv2.INTER_NEAREST)
    return a


def raster_from_uv(uvs, triangles, grid=GRID):
    """以 uvs([0,1] 紋理座標)+ triangles 在 grid×grid 上填三角 → 覆蓋遮罩。"""
    uv = np.asarray(uvs, np.float64).reshape(-1, 2)
    pts = np.column_stack([uv[:, 0] * (grid - 1), uv[:, 1] * (grid - 1)])
    tris = np.asarray(triangles, np.int32).reshape(-1, 3)
    canvas = np.zeros((grid, grid), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(canvas, poly, 1)
    return canvas


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def award_mesh(award_json, slot_name):
    d = json.load(open(award_json))
    sk = d["skins"]
    it = sk if isinstance(sk, list) else [{"name": n, "attachments": a} for n, a in sk.items()]
    for s in it:
        for slot, atts in s.get("attachments", {}).items():
            if slot == slot_name:
                for an, a in atts.items():
                    if a.get("type") == "mesh":
                        return a
    raise SystemExit(f"Award 找不到 mesh: {slot_name}")


def compare_part(png_path, award_json, slot_name, rows=10, cols=3):
    # --- 生成 mesh(S3 v2)---
    gen = gmv2.generate(png_path, rows=rows, cols=cols, mode="auto")
    # 格式閘(evaluate_mesh 需要 source mask)
    mask = em.load_mask(png_path)
    fmt = em.evaluate(gen, mask)
    # --- 藝術家真值 mesh ---
    real = award_mesh(award_json, slot_name)

    part_alpha = load_alpha_norm(png_path)
    gen_cov = raster_from_uv(gen["uvs"], gen["triangles"])
    real_cov = raster_from_uv(real["uvs"], real["triangles"])

    cover_iou_gen = iou(gen_cov, part_alpha)
    cover_iou_real = iou(real_cov, part_alpha)
    footprint_iou = iou(gen_cov, real_cov)

    verts_gen = len(gen["uvs"]) // 2
    verts_real = len(real["uvs"]) // 2

    # E1 = 格式/拓樸合法性(孤兒/退化/索引/預算/重心)。**不含** evaluate_mesh 的 AC1_iou:
    # 覆蓋率是 E2/E3 的職責(且需 parity-aware),絕對 0.95 對羽化件(如光暈)不適用
    # — 藝術家 78 頂點手做 mesh 對光暈也只到 0.945。故 E1 只看拓樸,避免重複計分。
    fmt_topo = {k: v["pass"] for k, v in fmt["criteria"].items() if k != "AC1_iou"}
    e1 = all(fmt_topo.values())
    e2 = cover_iou_gen >= 0.90
    e3 = (cover_iou_gen >= 0.95 * cover_iou_real) and (footprint_iou >= 0.80)
    e4 = verts_gen <= verts_real

    return {
        "slot": slot_name, "mode": gen.get("_mode"),
        "cover_iou_gen": round(cover_iou_gen, 4),
        "cover_iou_real": round(cover_iou_real, 4),
        "footprint_iou": round(footprint_iou, 4),
        "verts_gen": verts_gen, "verts_real": verts_real,
        "tris_gen": len(gen["triangles"]) // 3, "tris_real": len(real["triangles"]) // 3,
        "AC": {
            "E1_format": {"pass": bool(e1), "topo_detail": fmt_topo,
                          "cover_iou_note": fmt["criteria"]["AC1_iou"]},
            "E2_cover_self": {"pass": bool(e2), "value": round(cover_iou_gen, 4), "thresh": 0.90},
            "E3_parity": {"pass": bool(e3), "cover_ratio": round(cover_iou_gen / max(cover_iou_real, 1e-9), 3),
                          "footprint_iou": round(footprint_iou, 4)},
            "E4_compact": {"pass": bool(e4), "verts_gen": verts_gen, "verts_real": verts_real},
        },
        "overall_pass": bool(e1 and e2 and e3 and e4),
        "_gen_mesh": gen,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parts_dir", help="psd_slice 輸出目錄(含 NN_名.png)")
    ap.add_argument("award_json", help="assets/Award.json")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--dump-mesh", default=None, help="把生成 mesh 寫出的目錄")
    a = ap.parse_args()

    # PSD 圖層名 → Award slot 名(三個真實 mesh 標的)
    targets = {
        "光暈": "機器人拆件/光暈",
        "左手": "機器人拆件/左手",
        "身體": "機器人拆件/身體",
    }
    files = {f.split("_", 1)[1].rsplit(".", 1)[0]: os.path.join(a.parts_dir, f)
             for f in os.listdir(a.parts_dir) if f.endswith(".png")}

    reports = []
    for layer, slot in targets.items():
        if layer not in files:
            print(f"⚠️ 件缺: {layer}", file=sys.stderr); continue
        rep = compare_part(files[layer], a.award_json, slot, a.rows, a.cols)
        if a.dump_mesh:
            os.makedirs(a.dump_mesh, exist_ok=True)
            gm = rep.pop("_gen_mesh")
            json.dump(gm, open(os.path.join(a.dump_mesh, f"{layer}_gen_mesh.json"), "w"), ensure_ascii=False)
        else:
            rep.pop("_gen_mesh", None)
        reports.append(rep)

    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "parts": reports}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
