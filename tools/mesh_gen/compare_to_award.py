#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh」對照『真實生產 mesh』(Award spine)。

這是 S3 的最強驗收:不再拿合成資料或藝術家的『同一份』mesh 當基準,而是——
  真實 PSD 拆件(robot_parts.psd)→ psd_slice 切件 alpha → S3 generate_mesh_v2 生成 mesh
  ↔ 對照 Award.json 裡對應 slot 的『藝術家手做 mesh』(ground truth)。

對照的三件 mesh(Award 中為 mesh 型 attachment;右手/頭為 region 故排除):
  機器人拆件/光暈 (78v/76t/hull78) · 機器人拆件/身體 (98v/154t/hull40) · 機器人拆件/左手 (80v/116t/hull42)

★ 對齊依據(已實測):Spine 3.8 mesh 的 `uvs` 是『region 局部正規化座標』(件的正立邏輯座標),
  直接 (u*W, v*H) 即映到 PSD 切件像素空間。光暈實測 mesh-vs-alpha IoU=0.943(flip=False)確認。

量化指標(全部有 ground truth 可比):
  ① coverage:gen mesh vs 件 alpha 的 IoU,和『藝術家 mesh vs 同 alpha』基準比 → S3 覆蓋率是否 ≥ 藝術家。
  ② hull-shape:gen 外周多邊形 vs 藝術家外周多邊形的 IoU → 兩份輪廓幾何是否吻合。
  ③ budget:gen 頂點/三角數 vs 藝術家 → 是否精簡度相當(不過度細分)。
  ④ deform:把 main_draw 真實窗簾位移場(校準過)轉移到 gen mesh → 0 自交 / 0 翻面(耐變形)。

注意:光暈/身體/左手長寬比 < 1.2 → auto 模式回退 v1 Delaunay(strip 只適高瘦件)。
故本測同時跑 auto 與 forced-strip,誠實呈現兩種拓樸對非長條件的表現。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
import deform_eval as de
from generate_mesh_v2 import generate as gen_v2

# Award slot -> PSD 切件檔(psd_slice 對 robot_parts.psd 的輸出)
PARTS = [
    ("機器人拆件/光暈", "00_光暈.png"),
    ("機器人拆件/身體", "03_身體.png"),
    ("機器人拆件/左手", "04_左手.png"),
]


def load_award_mesh(award, slot):
    skin = award["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    a = next(iter(att.values()))
    uvs = np.array(a["uvs"], float).reshape(-1, 2)
    tris = np.array(a["triangles"], int).reshape(-1, 3)
    return uvs, tris, int(a["hull"])


def piece_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    H, W = img.shape[:2]
    alpha = (img[:, :, 3] > 8).astype(np.uint8) if img.ndim == 3 and img.shape[2] == 4 \
        else (img > 8).astype(np.uint8)
    return alpha, W, H


def fill_tris(pts_px, tris, W, H):
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(pts_px[t]).astype(np.int32), 1)
    return m


def poly_mask(hull_px, W, H):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(hull_px).astype(np.int32)], 1)
    return m


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def mesh_from_v2(alpha_path, mode):
    m = gen_v2(alpha_path, mode=mode)
    uvs = np.array(m["uvs"], float).reshape(-1, 2)
    tris = np.array(m["triangles"], int).reshape(-1, 3)
    return m, uvs, tris, int(m["hull"])


CURTAIN_DIAG = (346.0 ** 2 + 535.0 ** 2) ** 0.5  # main_draw curtain_left 邏輯尺寸對角線


def deform_clean(mesh, field_src, W, H):
    """把真實(校準)位移場轉移到 gen mesh,回傳自交/翻面統計。

    ★ scale 正規化:窗簾位移場是『絕對像素』(max 313px),直接套到不同大小的件會造成
    相對形變量嚴重不一致(313px 對 706px 的光暈是 44%、對 257px 的左手是 >100%)。
    依 part_diag / curtain_diag 縮放位移量,讓每件承受『與窗簾閘相同的相對極端拉伸』
    (area_ratio 回到校準過的 ~1.13 水準)→ 跨件公平比較。"""
    uvs_src, field, frame = field_src
    scale = (W ** 2 + H ** 2) ** 0.5 / CURTAIN_DIAG
    return de.transfer_deform_check(mesh, uvs_src, field * scale)


def run(slice_dir, award_path, out_json):
    award = json.load(open(award_path))
    # 真實(校準)位移場:main_draw 窗簾在全動畫的最大位移幀(y-up local)
    md = json.load(open(os.path.join(os.path.dirname(award_path), "main_draw.json")))
    field_src = de.real_deform_field(md, "image/curtain_left", "image/curtain_left")

    results = []
    for slot, fname in PARTS:
        path = os.path.join(slice_dir, fname)
        alpha, W, H = piece_alpha(path)
        a_uvs, a_tris, a_hull = load_award_mesh(award, slot)
        a_px = a_uvs * [W, H]
        a_cover = fill_tris(a_px, a_tris, W, H)
        a_hullm = poly_mask(a_px[:a_hull], W, H)
        artist_cov = iou(a_cover, alpha)

        row = {"slot": slot, "piece": [W, H], "alpha_px": int(alpha.sum()),
               "artist": {"verts": len(a_uvs), "tris": len(a_tris), "hull": a_hull,
                          "cover_iou": round(artist_cov, 4)},
               "gen": {}}
        for mode in ("auto", "strip"):
            m, g_uvs, g_tris, g_hull = mesh_from_v2(path, mode)
            g_px = g_uvs * [W, H]
            g_cover = fill_tris(g_px, g_tris, W, H)
            g_hullm = poly_mask(g_px[:g_hull], W, H)
            d = deform_clean(m, field_src, W, H)
            row["gen"][mode] = {
                "mode": m.get("_mode"),
                "verts": len(g_uvs), "tris": len(g_tris), "hull": g_hull,
                "cover_iou": round(iou(g_cover, alpha), 4),
                "cover_vs_artist": round(iou(g_cover, alpha) - artist_cov, 4),
                "hull_shape_iou": round(iou(g_hullm, a_hullm), 4),
                "verts_ratio": round(len(g_uvs) / len(a_uvs), 2),
                "deform_self_intersections": int(d["self_intersections"]),
                "deform_flipped_tris": int(d["triangle_flips"]),
                "deform_area_ratio": round(d["area_ratio"], 3),
            }
        results.append(row)

    json.dump(results, open(out_json, "w"), ensure_ascii=False, indent=2)
    return results


def verdict(results):
    """逐件 pass/fail:coverage ≥ 藝術家 −2% 且 hull_iou ≥ 0.80 且 deform 0 自交/0 翻面。"""
    print(f"{'slot':<18}{'mode':<12}{'v(g/a)':<10}{'cover':<16}{'hull_iou':<10}{'deform':<14}{'PASS'}")
    allpass = True
    for r in results:
        for mode in ("auto", "strip"):
            g = r["gen"][mode]
            cov_ok = g["cover_vs_artist"] >= -0.02
            hull_ok = g["hull_shape_iou"] >= 0.80
            def_ok = g["deform_self_intersections"] == 0 and g["deform_flipped_tris"] == 0
            p = cov_ok and hull_ok and def_ok
            if mode == "auto":
                allpass = allpass and p
            cov = f"{g['cover_iou']:.3f}/{r['artist']['cover_iou']:.3f}"
            dfm = f"si{g['deform_self_intersections']}/fl{g['deform_flipped_tris']}"
            print(f"{r['slot']:<18}{g['mode']:<12}{g['verts']}/{r['artist']['verts']:<7}"
                  f"{cov:<16}{g['hull_shape_iou']:<10.3f}{dfm:<14}{'✅' if p else '❌'}")
    return allpass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice-dir", default="/tmp/robot_slice")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--out", default="/tmp/compare_award.json")
    a = ap.parse_args()
    res = run(a.slice_dir, a.award, a.out)
    print("=== PSD件 → S3 mesh vs Award 真實 mesh ===")
    ok = verdict(res)
    print(f"\nauto 模式整體 verdict: {'PASS ✅' if ok else 'FAIL ❌'}  (詳見 {a.out})")


if __name__ == "__main__":
    main()
