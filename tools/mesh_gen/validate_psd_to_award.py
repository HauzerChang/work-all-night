#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh(靜態覆蓋率)。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 光暈/身體/左手 三件在生產
spine `Award` 中是 mesh。本工具把「PSD→件→mesh」整條接到真實標的上驗收:
  psd_slice 切件 alpha → generate_mesh_v2 → ① 覆蓋率 IoU(vs 件 alpha)不劣於藝術家
  mesh、② 生成 mesh 與藝術家 mesh 覆蓋區重疊高、③ 頂點預算不超過藝術家。

⚠️ 校正既有假設:Award mesh 的 `uvs` 是 **region-local 0..1**(Spine JSON 慣例),
   *不是* atlas-global UV(s4 doc 早期假設有誤)。經驗證:PSD 件像素框與藝術家 UV 框
   直接對齊(無需 flip),artist_cover vs 件 alpha IoU=0.95/0.95/0.98。

⚠️ 這些 Award mesh 是 **weighted、無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)。
   故本閘只驗**靜態覆蓋率/拓樸**;deform 穩健(v1 散點的弱點)對 bone-driven 件不適用,
   需 S5 權重才談,超出本 chunk 範圍。

負對照:交叉件(A 的生成 mesh vs B 的藝術家覆蓋)IoU 應明顯下降 → 確認閘有鑑別力。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import load_mask

# robot_parts.psd 中為 mesh 的三件(對應 Award slot/attachment 同名)
MESH_PARTS = ["光暈", "身體", "左手"]
IOU_MARGIN = 0.02  # 生成覆蓋率允許略低於藝術家的裕度


def load_skin(skeleton_path):
    d = json.load(open(skeleton_path))
    sk = d["skins"]
    sk = sk[0] if isinstance(sk, list) else sk["default"]
    return sk.get("attachments", sk)


def cover_from_uv(uv, tris, H, W):
    """region-local uv(0..1)+ triangles → 覆蓋 mask。"""
    rp = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    cov = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(cov, np.round(rp[t]).astype(np.int32), 1)
    return cov


def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1))


def part_data(skin, slot, part_png):
    """回傳 (件 alpha mask, 藝術家覆蓋, 藝術家 mesh 統計)。"""
    a = skin[slot][slot]
    auv = np.array(a["uvs"]).reshape(-1, 2)
    atris = np.array(a["triangles"]).reshape(-1, 3)
    mask = load_mask(part_png)
    H, W = mask.shape
    acov = cover_from_uv(auv, atris, H, W)
    stats = {"verts": len(auv), "tris": len(atris), "hull": a["hull"],
             "weighted": len(a["vertices"]) != len(a["uvs"])}
    return mask, acov, stats


def validate(skeleton_path, parts_dir, prefix="機器人拆件"):
    skin = load_skin(skeleton_path)
    manifest = json.load(open(os.path.join(parts_dir, "manifest.json")))
    file_by_name = {p["name"]: p["file"] for p in manifest["parts"]}

    covers = {}       # 供負對照重用
    report = {"parts": {}}
    for nm in MESH_PARTS:
        slot = f"{prefix}/{nm}"
        png = os.path.join(parts_dir, file_by_name[nm])
        mask, acov, astats = part_data(skin, slot, png)
        H, W = mask.shape

        m = gen_v2(png, mode="auto")
        guv = np.array(m["uvs"]).reshape(-1, 2)
        gtris = np.array(m["triangles"]).reshape(-1, 3)
        gcov = cover_from_uv(guv, gtris, H, W)

        iou_a = iou(acov, mask)
        iou_g = iou(gcov, mask)
        covers[nm] = {"artist": acov, "gen": gcov, "mask": mask}
        report["parts"][nm] = {
            "part_size": [int(W), int(H)],
            "artist": astats,
            "generated": {"verts": len(guv), "tris": len(gtris),
                          "hull": m["hull"], "mode": m.get("_mode")},
            "IoU_artist_vs_alpha": round(iou_a, 4),
            "IoU_gen_vs_alpha": round(iou_g, 4),
            "IoU_gen_vs_artist": round(iou(gcov, acov), 4),
            "AC_cover_ge_artist": bool(iou_g >= iou_a - IOU_MARGIN),
            "AC_verts_le_artist": bool(len(guv) <= astats["verts"]),
        }

    # 負對照:每件生成 mesh 對「其他件」藝術家覆蓋 → 應遠低於同件。
    # 各件尺寸不同,先把「其他件」覆蓋 resize 到當前件框(nearest,只比形狀重疊)。
    neg = {}
    names = list(covers)
    for nm in names:
        gh, gw = covers[nm]["gen"].shape
        same = iou(covers[nm]["gen"], covers[nm]["artist"])
        cross = {}
        for o in names:
            if o == nm:
                continue
            other = cv2.resize(covers[o]["artist"], (gw, gh), interpolation=cv2.INTER_NEAREST)
            cross[o] = round(iou(covers[nm]["gen"], other), 4)
        worst_cross = max(cross.values())
        neg[nm] = {"same_part": round(same, 4), "cross_part": cross,
                   "discriminates": bool(same - worst_cross > 0.3)}
    report["negative_control"] = neg

    ac_pass = all(p["AC_cover_ge_artist"] and p["AC_verts_le_artist"]
                  for p in report["parts"].values())
    disc_ok = all(v["discriminates"] for v in neg.values())
    report["overall_pass"] = bool(ac_pass and disc_ok)
    return report, covers


def save_figure(covers, out_path):
    """每件一列:件 alpha | 藝術家覆蓋 | 生成覆蓋 | 疊圖(綠=交、紅=藝術家獨有、藍=生成獨有)。"""
    rows = []
    for nm, c in covers.items():
        mask, acov, gcov = c["mask"], c["artist"], c["gen"]
        H, W = mask.shape
        def tile(m):
            return cv2.cvtColor((m * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        overlay = np.zeros((H, W, 3), np.uint8)
        inter = np.logical_and(acov, gcov)
        overlay[np.logical_and(acov, ~gcov.astype(bool))] = (0, 0, 200)   # 藝術家獨有 紅
        overlay[np.logical_and(gcov, ~acov.astype(bool))] = (200, 0, 0)   # 生成獨有 藍
        overlay[inter] = (0, 180, 0)                                       # 交集 綠
        strip = np.hstack([tile(mask), tile(acov), tile(gcov), overlay])
        rows.append(strip)
    maxw = max(r.shape[1] for r in rows)
    rows = [cv2.copyMakeBorder(r, 4, 4, 0, maxw - r.shape[1], cv2.BORDER_CONSTANT, value=(40, 40, 40)) for r in rows]
    cv2.imwrite(out_path, np.vstack(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts", default="/tmp/robot_parts",
                    help="psd_slice 切出的件目錄(含 manifest.json)")
    ap.add_argument("--prefix", default="機器人拆件")
    ap.add_argument("--figure", default=None, help="輸出對照圖 PNG 路徑")
    a = ap.parse_args()
    rep, covers = validate(a.skeleton, a.parts, a.prefix)
    if a.figure:
        save_figure(covers, a.figure)
        rep["figure"] = a.figure
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
