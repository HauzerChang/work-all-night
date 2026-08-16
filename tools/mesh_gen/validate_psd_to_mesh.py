#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh → 對照真實生產 mesh」驗收(對 Award 機器人 mesh 件)。

背景(見 knowledge/s4-psd-to-spine-real.md、STATE 下一步):
  robot_parts.psd 的 5 圖層 ⇄ Award spine slot `機器人拆件/<圖層名>` 一對一;其中會 warp 的
  3 件(光暈/身體/左手)在 Award 中是 **mesh**(剛體件右手/頭是 region)。本工具把「PSD 切件」
  跑 S3 `generate_mesh_v2`,與 Award 的**真實藝術家 mesh**做量化對照,做端到端驗收。

座標對齊(關鍵):
  Award mesh 的 uvs 是 **region-local(0..1)**(已實測:光暈/身體/左手 uv 皆近乎鋪滿 0..1);
  attachment 的 width/height = PSD 件尺寸 + 2px(atlas padding,1px 對稱邊)。
  因此把 PSD 件 alpha **置中貼進 (attW × attH) 的畫布**,藝術家 mesh(uv×attW,attH)與
  在該畫布上生成的 mesh 就落在**同一像素座標系** → IoU / 拓樸可公平對照。

deform 韌性探針(誠實標註):
  這 3 件在 Award **無 deform timeline**(靠骨骼動,見 log 2026-06-26-005)→ 原生位移場為零、
  無鑑別力。故改用 main_draw `curtain_left` 的**真實最大位移場**經 UV 轉移施加(RULES:用真實
  位移場轉移、不可用未校準 stress_field),同時施於「生成 mesh」與「藝術家 mesh」,比較兩者
  在同一真實壓力下的拓樸乾淨度。這是**韌性對照**,非該件的動畫保真度主張。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image
from psd_tools import PSDImage
import deform_eval as de
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2

# Award slot/attachment == PSD 圖層名(一對一);3 個 mesh 件
MESH_PARTS = ["光暈", "身體", "左手"]


def get_attachment(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def award_attachment(sk, layer):
    slot = name = f"機器人拆件/{layer}"
    return get_attachment(sk, slot, name), slot, name


def award_attachment_like(sk, name):
    return get_attachment(sk, name, name), name, name


def psd_part_alpha(psd_path, layer):
    """回傳該圖層 bbox-cropped 的 alpha (H,W uint8 0/255) 與 (W,H)。"""
    psd = PSDImage.open(psd_path)
    for l in psd.descendants():
        if (not l.is_group()) and l.is_visible() and l.name == layer:
            im = l.topil()
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            a = np.array(im.split()[-1], dtype=np.uint8)
            return a, im.width, im.height
    raise SystemExit(f"PSD 找不到可見圖層: {layer}")


def pad_to_attachment(alpha, attW, attH):
    """把 bbox alpha 置中貼進 (attH,attW) 畫布(吸收 atlas 對稱 padding)。"""
    H, W = alpha.shape
    canvas = np.zeros((attH, attW), np.uint8)
    ox, oy = (attW - W) // 2, (attH - H) // 2
    canvas[oy:oy + H, ox:ox + W] = alpha
    return canvas


def mesh_iou(uvs, tris, mask):
    """任一 (region-local uvs, triangles) 在 mask 尺寸上填滿的 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / max(np.logical_or(recon, m).sum(), 1))


def artist_mesh_obj(att, W, H):
    """把 Award 藝術家 mesh 包成 evaluate/transfer 可吃的物件(region-local uvs → 像素頂點)。
    vertices 用 generate 慣例:x-中心、y 上翻。"""
    uvs = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = att["triangles"]
    verts = []
    for (u, v) in uvs:
        px, py = u * W, v * H
        verts += [px - W / 2.0, H / 2.0 - py]
    return {"type": "mesh", "vertices": verts, "uvs": uvs.reshape(-1).tolist(),
            "triangles": [int(i) for i in tris], "hull": int(att["hull"]),
            "width": int(W), "height": int(H)}


def run(psd_path, award_json, curtain_json, tmp_dir, iou_margin=0.02):
    os.makedirs(tmp_dir, exist_ok=True)
    sk = json.load(open(award_json))
    csk = json.load(open(curtain_json))
    uvs_src, field, ffrm = de.real_deform_field(csk, "image/curtain_left", "image/curtain_left")
    # 來源件尺寸:用來把位移場「正規化成佔件寬高的比例」→ 可等比轉移到任一尺寸的目標件。
    catt, _, _ = award_attachment_like(csk, "image/curtain_left")
    curtainW, curtainH = int(catt["width"]), int(catt["height"])
    frac = np.hypot(field[:, 0] / curtainW, field[:, 1] / curtainH).max()

    out = {"_stress_field": {"source": f"{curtain_json}:image/curtain_left @ {ffrm}",
                             "src_size": [curtainW, curtainH],
                             "max_disp_px": round(float(np.hypot(field[:, 0], field[:, 1]).max()), 2),
                             "max_disp_frac_of_part": round(float(frac), 3),
                             "note": "field 依目標件寬高等比縮放(相對 warp 不變)後再轉移"},
           "parts": {}}
    all_pass = True

    for layer in MESH_PARTS:
        att, slot, name = award_attachment(sk, layer)
        attW, attH = int(att["width"]), int(att["height"])
        alpha, pw, ph = psd_part_alpha(psd_path, layer)
        mask = pad_to_attachment(alpha, attW, attH)
        crop_png = os.path.join(tmp_dir, f"{layer}_padded.png")
        cv2.imwrite(crop_png, mask)  # 單通道當 alpha 來源(load_mask 走 gray>0)

        gen = gen_v2(crop_png, mode="auto")
        ev = evaluate(gen, mask, vertex_budget=64)

        gen_uvs = np.array(gen["uvs"], dtype=np.float64).reshape(-1, 2)
        gen_tris = np.array(gen["triangles"], dtype=np.int32).reshape(-1, 3)
        gen_iou = mesh_iou(gen_uvs, gen_tris, mask)

        art = artist_mesh_obj(att, attW, attH)
        art_uvs = np.array(art["uvs"], dtype=np.float64).reshape(-1, 2)
        art_tris = np.array(art["triangles"], dtype=np.int32).reshape(-1, 3)
        art_iou = mesh_iou(art_uvs, art_tris, mask)

        # 把 curtain 真實位移場等比縮放到本件尺寸(相對 warp 不變)→ 公平的耐變形壓力
        field_t = np.column_stack([field[:, 0] * attW / curtainW, field[:, 1] * attH / curtainH])
        gen_def = de.transfer_deform_check(gen, uvs_src, field_t)
        art_def = de.transfer_deform_check(art, uvs_src, field_t)

        iou_pass = gen_iou >= art_iou - iou_margin
        fmt_pass = ev["criteria"]["AC4_format"]["pass"] and \
            ev["criteria"]["AC2b_degenerate"]["pass"] and ev["criteria"]["AC2c_orphans"]["pass"]
        def_pass = gen_def["clean"]
        # production-critical(這些件在 Award 靠骨骼動、無 deform)= 覆蓋率 + 格式;
        # deform 韌性為額外壓力探針(out-of-envelope),單列不併入 milestone 判定。
        prod_pass = iou_pass and fmt_pass
        all_pass = all_pass and prod_pass

        out["parts"][layer] = {
            "psd_part_size": [pw, ph], "attachment_size": [attW, attH],
            "generated": {"mode": gen.get("_mode"), "vertices": len(gen_uvs),
                          "triangles": len(gen_tris), "hull": gen["hull"], "iou": round(gen_iou, 4)},
            "artist_truth": {"vertices": len(art_uvs), "triangles": len(art_tris),
                             "hull": int(att["hull"]), "iou": round(art_iou, 4)},
            "AC_iou_vs_artist": {"gen": round(gen_iou, 4), "artist": round(art_iou, 4),
                                 "margin": iou_margin, "pass": iou_pass},
            "AC_format": {"pass": fmt_pass, "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                          "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                          "centroid_in_mask": ev["criteria"]["AC2a_centroid_in_mask"]["value"]},
            "deform_robustness_probe": {
                "gen": {k: gen_def[k] for k in ("self_intersections", "triangle_flips",
                                                "degenerate", "area_ratio", "clean")},
                "artist_truth": {k: art_def[k] for k in ("self_intersections", "triangle_flips",
                                                         "degenerate", "area_ratio", "clean")},
                "gen_clean": def_pass, "artist_clean": art_def["clean"]},
            "production_pass": prod_pass,
        }

    out["overall_pass"] = all_pass  # production-critical:覆蓋率 + 格式
    out["_deform_robustness_summary"] = {
        "note": "額外探針(這3件實際無 deform);gate 已對藝術家真值校準(全 clean 才可信)",
        "artist_all_clean": all(out["parts"][l]["deform_robustness_probe"]["artist_clean"]
                                for l in out["parts"]),
        "gen_clean": [l for l in out["parts"] if out["parts"][l]["deform_robustness_probe"]["gen_clean"]],
        "gen_gap": [l for l in out["parts"] if not out["parts"][l]["deform_robustness_probe"]["gen_clean"]],
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--curtain", default="assets/main_draw.json")
    ap.add_argument("--tmp", default="/tmp/psd2mesh")
    a = ap.parse_args()
    rep = run(a.psd, a.award, a.curtain, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
