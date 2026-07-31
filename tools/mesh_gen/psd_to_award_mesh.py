#!/usr/bin/env python3
"""端到端整合 AC:分層 PSD → 切件 → S3 生成 mesh → 對照『真實生產 spine』的藝術家 mesh。

這是把 S4(PSD 切圖)與 S3(mesh 生成)串成 pipeline,並用**真實生產標的**(機器人
big-win 的 `robot_parts.psd` ⇄ 生產 spine `Award.json`)當 ground truth 驗收。

對每個「PSD 圖層 == Award mesh slot」的部位:
  1. psd_slice 切出緊湊件 PNG(+2px 由 Award 對齊,見 s4-psd-to-spine-real.md)。
  2. generate_mesh_v2(auto)由件 alpha 生成 mesh。
  3. 覆蓋率 IoU:生成 mesh vs 藝術家 mesh,兩者都對『同一件 alpha』量測 → 可比。
  4. setup-pose 幾何閘:0 自交 / 0 翻面 / 0 退化(此資產無 deform timeline,見下)。
  5. 判定:gen_iou >= artist_iou - margin(生成品至少和藝術家一樣貼)。

⚠️ 為何沒有 deform 閘:Award 的機器人 mesh 是 **weighted**(骨骼蒙皮驅動),
   9→12 支動畫**沒有任何 deform timeline**(已枚舉確認)。deform 轉移閘(真實位移場)
   對此資產 N/A;此處的真值是「靜態覆蓋率對照藝術家生產 mesh」。deform 幾何仍以
   setup-pose 檢查把關(生成器產物本應零缺陷)。

座標對齊:Award region `orig==size`、`offset 0,0`(僅 ~0.70 打包縮放,無 trim);
   mesh `width/height` = 件尺寸 +2px padding。藝術家 UV 為 region 正規化 0..1,
   故 `uv*(件寬,件高)` 對齊件 alpha,誤差僅 +2px(<0.5%,IoU 噪音內)。

用法:
  python tools/mesh_gen/psd_to_award_mesh.py \
      --psd assets/robot_parts.psd --skeleton assets/Award.json
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
import deform_eval as de


def mesh_slots(skeleton):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    out = {}
    for slot, names in atts.items():
        for nm, a in names.items():
            if a.get("type") == "mesh":
                out.setdefault(slot, nm)
    return out


def has_deform(skeleton, slot, name):
    for anim, ad in skeleton.get("animations", {}).items():
        for _, slots in (ad.get("deform") or {}).items():
            if slot in slots and name in slots[slot]:
                return True
    return False


def setup_clean(mesh):
    v = np.array(mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(v, x) > 0 for x in t]
    return de.check(v, t, signs)


def shrink_mesh(mesh, factor=0.85):
    """負對照:把生成 mesh 對中心等比縮小 → 覆蓋率應明顯掉到 artist 之下,證明閘有鑑別力。"""
    m = json.loads(json.dumps(mesh))
    v = np.array(m["vertices"], dtype=np.float64).reshape(-1, 2)
    c = v.mean(axis=0)
    v = c + (v - c) * factor
    m["vertices"] = [round(float(x), 3) for x in v.reshape(-1)]
    return m


def run(psd_path, skeleton_path, prefix, epsilon, iou_margin, tmp_dir, budget):
    sk = json.load(open(skeleton_path))
    ms = mesh_slots(sk)
    _, manifest, parts = slice_psd(psd_path, tmp_dir)
    by_name = {e["name"]: (e, im) for e, im in parts}

    report = {"psd": os.path.basename(psd_path), "skeleton": os.path.basename(skeleton_path),
              "epsilon": epsilon, "iou_margin": iou_margin, "parts": []}
    for layer, (entry, im) in by_name.items():
        slot = prefix + layer
        if slot not in ms:
            continue  # 該圖層在生產 spine 不是 mesh(region/未用)→ 跳過
        name = ms[slot]
        png = os.path.join(tmp_dir, entry["file"])
        mask = load_mask(png)

        mesh = gen_v2(png, mode="auto", epsilon_frac=epsilon)
        nv = len(mesh["uvs"]) // 2
        gio = evaluate(mesh, mask, vertex_budget=budget)["criteria"]["AC1_iou"]["value"]
        aio = artist_iou(sk, slot, name, mask)
        chk = setup_clean(mesh)
        neg = evaluate(shrink_mesh(mesh), mask, vertex_budget=budget)["criteria"]["AC1_iou"]["value"]

        # 藝術家 mesh 頂點數(weighted 亦以 uvs 計)
        a = sk["skins"][0]["attachments"][slot][name] if isinstance(sk["skins"], list) \
            else sk["skins"]["attachments"][slot][name]
        artist_nv = len(a["uvs"]) // 2

        iou_pass = gio >= aio - iou_margin
        geom_pass = (chk["self_intersections"] == 0 and chk["triangle_flips"] == 0
                     and chk["degenerate"] == 0)
        neg_ok = neg < aio - iou_margin  # 負對照必須被判 fail,才證明閘有鑑別力
        report["parts"].append({
            "layer": layer, "slot": slot, "mode": mesh.get("_mode"),
            "gen": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
            "artist": {"vertices": artist_nv, "weighted": len(a["vertices"]) != len(a["uvs"])},
            "AC_coverage_iou": {"gen": round(gio, 4), "artist_baseline": round(aio, 4),
                                "delta": round(gio - aio, 4), "pass": iou_pass},
            "AC_setup_geom": {**{k: chk[k] for k in
                              ("self_intersections", "triangle_flips", "degenerate")}, "pass": geom_pass},
            "deform_gate": "N/A (weighted skinning, 0 deform timelines)"
                           if not has_deform(sk, slot, name) else "HAS_DEFORM",
            "neg_control": {"shrunk_iou": round(neg, 4), "discriminates": neg_ok},
            "part_pass": iou_pass and geom_pass and neg_ok,
        })
    report["overall_pass"] = bool(report["parts"]) and all(p["part_pass"] for p in report["parts"])
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--prefix", default="機器人拆件/", help="PSD 圖層名 → spine slot 前綴")
    ap.add_argument("--epsilon", type=float, default=0.004, help="v1 hull Douglas-Peucker(已對生產件校準)")
    ap.add_argument("--margin", type=float, default=0.0, help="gen_iou 可低於 artist 的容差")
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--tmp", default="/tmp/psd_award_pieces")
    a = ap.parse_args()
    rep = run(a.psd, a.skeleton, a.prefix, a.epsilon, a.margin, a.tmp, a.budget)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
