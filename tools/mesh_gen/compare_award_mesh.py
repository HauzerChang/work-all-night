#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(knowledge/s4-psd-to-spine-real.md):`robot_parts.psd`(機器人拆件)5 圖層
對應真實 spine `Award` 的 slot `機器人拆件/<圖層名>`;其中 光暈/身體/左手 是 **mesh**
(且為 **weighted**、無 deform timeline → 靠骨骼權重變形,非逐頂點 deform)。

本工具把 S3(generate_mesh_v2)產的 mesh,與藝術家在 Award 裡手做的 mesh,
在「同一件的 alpha 形狀」上做**覆蓋率 IoU 對照** + 頂點預算對照。

⚠️ 藝術家 mesh 的 uvs 是 **atlas 頁 UV**(件在 atlas 中可能旋轉)。與其手推 uv→局部
座標(專案踩過 derotate 方向 bug,被 round-trip 自洽掩蓋),這裡用**方位窮舉**:
把件 alpha 以 8 種二面體變換(4 旋轉 × 2 翻轉)對齊藝術家 mesh 的正規化 uv 框,取
IoU 最大者。correct 方位會壓倒性勝出(>0.9 vs 亂序),既得基準又**自我校驗對應正確**。

deform 閘:這 3 件在 Award **無 deform timeline** → 逐頂點 deform 轉移不適用(N/A),
不是失敗。(對照 main_draw 窗簾有 deform,故走 deform_eval;此處刻意不套未校準壓力場。)
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh
import psd_slice

MESH_PIECES = ["光暈", "左手", "身體"]  # Award 中為 mesh 的 3 件(右手/頭為 region)
SLOT_PREFIX = "機器人拆件/"


def award_mesh(award_json, name):
    sk = json.load(open(award_json))
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin["attachments"] if "attachments" in skin else skin
    slot = SLOT_PREFIX + name
    a = att[slot][slot]
    return {"uvs": np.array(a["uvs"], float).reshape(-1, 2),
            "triangles": np.array(a["triangles"], int).reshape(-1, 3),
            "hull": a.get("hull"), "nverts": len(a["uvs"]) // 2}


def rasterize(uvn, tris, out_h, out_w):
    """把已正規化到 [0,1] 的 uvn → 填三角 → 二值填充圖(out_h×out_w)。
    ⚠️ 不在此處做 bbox 正規化(那會把未填滿框的形狀拉伸致錯位)。呼叫端負責
    正確地把座標映到目標框(我方 mesh:直接 x/W,y/H;藝術家:對 atlas footprint 正規化)。"""
    px = np.column_stack([uvn[:, 0] * (out_w - 1), uvn[:, 1] * (out_h - 1)])
    canvas = np.zeros((out_h, out_w), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(canvas, np.round(px[t]).astype(np.int32), 1)
    return canvas


DIHEDRAL = {  # name -> function on binary mask
    "id":    lambda m: m,
    "rot90": lambda m: cv2.rotate(m, cv2.ROTATE_90_CLOCKWISE),
    "rot180":lambda m: cv2.rotate(m, cv2.ROTATE_180),
    "rot270":lambda m: cv2.rotate(m, cv2.ROTATE_90_COUNTERCLOCKWISE),
    "flipH": lambda m: cv2.flip(m, 1),
    "flipV": lambda m: cv2.flip(m, 0),
    "transp":lambda m: m.T.copy(),
    "anti":  lambda m: cv2.flip(m.T.copy(), -1),
}


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def best_coverage(mesh_fill, alpha):
    """把 alpha 以 8 方位對齊 mesh_fill(resize 到同尺寸),取最佳 IoU。
    回傳 (best_iou, best_orient, all_ious)。"""
    H, W = mesh_fill.shape
    results = {}
    for nm, fn in DIHEDRAL.items():
        m = fn(alpha)
        m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
        results[nm] = round(iou(mesh_fill, m > 0), 4)
    best = max(results, key=results.get)
    return results[best], best, results


def piece_alpha_from_psd(psd_path, layer_name):
    _, _, parts = psd_slice.slice_psd(psd_path)
    for entry, im in parts:
        if entry["name"] == layer_name:
            a = np.array(im.split()[-1])
            return (a > 8).astype(np.uint8), im.width, im.height
    raise SystemExit(f"PSD 找不到圖層: {layer_name}")


def run(award_json, atlas_path, psd_path, out_json=None):
    report = {"pieces": []}
    for name in MESH_PIECES:
        alpha, W, H = piece_alpha_from_psd(psd_path, name)
        # my mesh (S3) from the PSD piece alpha
        tmp = f"/tmp/_piece_{name}.png"
        cv2.imwrite(tmp, np.dstack([np.zeros((H, W), np.uint8)] * 3 + [alpha * 255]))
        my = gen_v2(tmp, mode="auto")
        my_ev = eval_mesh(my, alpha)
        my_iou = my_ev["criteria"]["AC1_iou"]["value"]   # 像素框直接覆蓋率(evaluate_mesh AC1)
        my_nv = len(my["uvs"]) // 2

        # sanity:用同一 rasterize 在像素框直接畫我方 mesh(uv=x/W,y/H,免搜尋),應 ≈ AC1
        my_uv = np.array(my["uvs"], float).reshape(-1, 2)
        my_fill = rasterize(my_uv, np.array(my["triangles"], int).reshape(-1, 3), H, W)
        my_iou_direct = round(iou(my_fill, alpha > 0), 4)

        # artist mesh (Award):實測其 uvs **已是 region 局部 [0,1] 正規化**(非 atlas 頁 UV;
        # 身體 u 僅達 0.759 == 內容右緣 286/379,證實為邏輯方向的 region 座標)。
        # 故直接以原始 uvs 畫進件框 → 8 方位窮舉對齊 alpha(吸收 v 軸慣例 / 任何殘餘方位)。
        art = award_mesh(award_json, name)
        art_fill = rasterize(art["uvs"], art["triangles"], H, W)
        art_iou, art_or, art_all = best_coverage(art_fill, alpha)

        report["pieces"].append({
            "piece": name, "slot": SLOT_PREFIX + name,
            "psd_size": [W, H],
            "my_mesh": {"mode": my.get("_mode"), "verts": my_nv,
                        "hull": my["hull"], "tris": len(my["triangles"]) // 3,
                        "iou_vs_alpha": my_iou,
                        "format_pass": my_ev["criteria"]["AC4_format"]["pass"],
                        "iou_direct_check": my_iou_direct},
            "artist_mesh": {"verts": art["nverts"], "hull": art["hull"],
                            "tris": len(art["triangles"]),
                            "coverage_iou": art_iou, "best_orient": art_or,
                            "orient_ious": art_all},
            "verdict": {
                "my_covers_as_well": my_iou >= art_iou - 0.03,
                "vert_economy": round(art["nverts"] / max(my_nv, 1), 2),
                "orient_decisive": art_iou - sorted(art_all.values())[-2] > 0.05,
            },
        })
    report["deform_gate"] = "N/A — 3 件在 Award 為 weighted mesh、無 deform timeline"
    if out_json:
        json.dump(report, open(out_json, "w"), ensure_ascii=False, indent=2)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    rep = run(a.award, a.atlas, a.psd, a.out)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    ok = all(p["verdict"]["my_covers_as_well"] for p in rep["pieces"])
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
