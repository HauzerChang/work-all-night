#!/usr/bin/env python3
"""S1 目標圖反推分析器 — 靜態 2D 目標圖 → Asset & Rig Requirement Spec。

對應 PLAN.md「S1 反推分析器」,並落實使用者新增研究項目(2026-08-19):分析目標 2D 圖,
反推 spine 動畫開發的前置需求。核心信念(見 Spine能力鍛鍊計畫.md):**運動決定一切** ——
一個部件之所以要獨立,是因為它半獨立地運動。

輸入:分層 PSD(每個可見 leaf 圖層 = 候選可動件)。輸出五段規格:
  1. 運動構件(movable parts):件清單 + 幾何 + z 序 + 質心。
  2. 周邊特效(effects):把每件分類為 結構件 / 特效件(glow/radial/particle),用確定性訊號打分。
  3. 動作腳本與分鏡(motion storyboard):由件 + 類型先驗提「此圖能怎麼動」的分鏡草案(PROPOSAL)。
  4. 拆圖策略(slicing strategy):每件交付規格(切件/padding/命名/mesh vs region/pivot 提示)。
  5. 補圖項目(inpainting items):由 setup 疊放遮擋 × 提案運動,反推「哪件的哪塊會被移開露出」需補繪。

⚠️ 純靜圖沒有真實運動 → #3/#4/#5 的「運動」是**由類型先驗提出的提案**,非觀測;
   需用真值(如 robot_parts.psd ⇄ Award spine)驗證召回。見 validate_analyzer_award.py。
   確定性演算法 + 可驗證閘,不靠 ML 猜「沒有唯一解的美術決定」。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from psd_slice import slice_psd  # 重用 PSD 抽層(offset/size/opacity/z)
import genre_priors as GP

# 美術命名先驗:出現這些字樣 → 強烈暗示特效件(藝術家命名是最可靠的真實訊號)
EFFECT_KW = ["光暈", "光晕", "glow", "光", "粒子", "particle", "放射", "radial",
             "star", "星", "spark", "火花", "ray", "光線", "flare", "發光", "halo",
             "圈", "circle_light", "光球", "ball", "亮", "shine", "lens", "bloom"]

# 類型先驗庫已抽到 genre_priors.py(可驗證、可擴充)。


def part_metrics(entry, im, W, H):
    """單件量化指標(來源:切件 RGBA + offset + 畫布尺寸)。"""
    rgba = np.array(im)
    a = rgba[:, :, 3]
    fg = a > 8
    area = int(fg.sum())
    l, t = entry["offset"]
    w, h = entry["size"]
    # 質心(畫布座標)
    ys, xs = np.where(fg)
    cx = float(xs.mean() + l) if area else l + w / 2
    cy = float(ys.mean() + t) if area else t + h / 2
    soft = float(((a > 8) & (a < 250)).sum() / max(area, 1))         # 羽化帶比例
    coverage = area / float(W * H)                                    # 佔畫布比例
    # 內部細節密度(Canny 邊 / 前景面積):特效多平滑 → 低
    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.bitwise_and(edges, edges, mask=fg.astype(np.uint8) * 255)
    detail = float((edges > 0).sum() / max(area, 1))
    # 飽和/明度(特效常低飽和高明度或單色亮)
    hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV)
    sat = float(hsv[:, :, 1][fg].mean()) if area else 0.0
    val = float(hsv[:, :, 2][fg].mean()) if area else 0.0
    return {"name": entry["name"], "area": area, "bbox": [l, t, l + w, t + h], "size": [w, h],
            "centroid": [round(cx, 1), round(cy, 1)], "soft": round(soft, 3),
            "coverage": round(coverage, 3), "detail": round(detail, 3),
            "sat": round(sat, 1), "val": round(val, 1), "z": entry["z"],
            "mask_fg": fg, "offset": [l, t]}


def envelopment(part, others):
    """此件 alpha 涵蓋其他件質心的比例(背景光暈會包住眾件)。"""
    fg = part["mask_fg"]; l, t = part["offset"]; H, W = fg.shape
    if not others:
        return 0.0
    cnt = 0
    for o in others:
        cx, cy = o["centroid"]
        x = int(cx - l); y = int(cy - t)
        if 0 <= y < H and 0 <= x < W and fg[y, x]:
            cnt += 1
    return cnt / len(others)


def classify_effect(part, name, others, n_parts):
    """確定性特效打分(0..1)+ 子類。訊號加權後閾值判定。"""
    s = {}
    lname = name.lower()
    s["name_kw"] = 1.0 if any(k.lower() in lname for k in EFFECT_KW) else 0.0
    s["feather"] = min(part["soft"] / 0.20, 1.0)                     # 羽化 >=0.2 滿分
    s["coverage"] = min(part["coverage"] / 0.40, 1.0)               # 佔畫布 >=40% 滿分
    s["envelop"] = envelopment(part, others)                        # 包住其他件
    s["low_detail"] = 1.0 - min(part["detail"] / 0.15, 1.0)         # 細節越低越像特效
    s["z_extreme"] = 1.0 if part["z"] in (0, n_parts - 1) else 0.0  # 最底/最頂
    w = {"name_kw": 0.34, "feather": 0.18, "coverage": 0.14,
         "envelop": 0.16, "low_detail": 0.10, "z_extreme": 0.08}
    score = sum(w[k] * s[k] for k in w)
    is_effect = score >= 0.45
    # 子類
    subtype = None
    if is_effect:
        if s["coverage"] >= 0.6 or s["envelop"] >= 0.6:
            subtype = "glow/radial(背景放射光,包住主體)"
        elif "粒子" in name or "particle" in lname or "spark" in lname or "star" in lname:
            subtype = "particle(粒子)"
        else:
            subtype = "glow(局部發光)"
    return {"is_effect": is_effect, "score": round(score, 3),
            "subtype": subtype, "signals": {k: round(v, 3) for k, v in s.items()}}


def label_structural_role(part, name, W, H, all_struct):
    """結構件角色啟發(body/head/limb/other)— 供分鏡與 pivot 提示。"""
    lname = name.lower()
    kw = {"頭": "head", "head": "head", "臉": "head", "身": "body", "body": "body",
          "軀": "body", "手": "limb", "hand": "limb", "arm": "limb", "臂": "limb",
          "腳": "limb", "腿": "limb", "leg": "limb", "foot": "limb", "翅": "limb", "wing": "limb"}
    for k, v in kw.items():
        if k in name or k in lname:
            return v
    # 無關鍵字 → 用面積/位置:最大且居中 = body;上方小件 = head;其餘 = limb
    areas = sorted([p["area"] for p in all_struct], reverse=True)
    if part["area"] == areas[0]:
        return "body"
    cx, cy = part["centroid"]
    if cy < H * 0.4 and part["area"] < areas[0] * 0.5:
        return "head"
    return "limb"


def build_storyboard(parts_out, genre):
    prior = GP.get(genre)
    beats = []
    for b in prior["beats"]:
        rolemap = prior.get("roles", {}).get(b["key"], {})
        rows = []
        for p in parts_out:
            role = "effect" if p["classification"]["is_effect"] else p.get("struct_role", "limb")
            act = rolemap.get(role) or rolemap.get("limb") or "(依先驗未定義)"
            rows.append({"part": p["name"], "role": "特效" if role == "effect" else role,
                         "action": act})
        entry = {"beat": b["key"], "desc": b["desc"], "parts": rows}
        if b.get("cat"):           # 先驗明確宣告的運動基元類別(主秀 hit/reveal 接線)
            entry["cat"] = b["cat"]
        beats.append(entry)
    validated = prior.get("validated_against")
    status = (f"PROPOSAL(先驗已對真值 {validated} 驗證覆蓋)" if validated
              else "PROPOSAL(⚠️ 未驗證先驗,無對應真值 spine)")
    return {"genre": genre, "genre_desc": prior.get("desc"),
            "tier_variants": prior.get("tiers"),
            "validated_against": validated, "beats": beats, "status": status}


def _canvas_mask(part, W, H):
    m = np.zeros((H, W), bool)
    l, t = part["offset"]; h, w = part["mask_fg"].shape
    m[t:t + h, l:l + w] = part["mask_fg"]
    return m


def occlusion_reveal_inpainting(parts_full, parts_out, W, H):
    """setup 疊放遮擋分析 → 兩個獨立產出(誠實區分):

    A. 露出區(reveal-on-move):上層可動結構件蓋住『下層件已有內容』的區域。
       運動移開後這塊會露出;因下層已完整(present overlap)→ **不需補圖,只需知會 rigger**。
    B. 補圖候選(inpainting):下層件輪廓內的**封閉破洞**(binary_fill_holes 找出),且被上層蓋住。
       分層 PSD 通常各層完整 → 此清單多半為空,這正是「PSD-first 契約能繞開補圖」的量化證據。

    ⚠️ 關鍵:純靜態**分層**圖無法可靠分辨「該補的洞」與「本就是背景的透明」——
       上層 bbox 內的透明多半是背景而非破洞。故 B 只採「封閉洞」這個可靠訊號;
       若輸入是**單張未分層平圖**,則所有被蓋區都是潛在破洞(契約不同,結論相反)。"""
    from scipy import ndimage
    effect = {p["name"]: p["classification"]["is_effect"] for p in parts_out}
    role = {p["name"]: p.get("struct_role") for p in parts_out}
    reveal, inpaint = [], []
    canvas = {p["name"]: _canvas_mask(p, W, H) for p in parts_full}
    for upper in parts_full:
        un = upper["name"]
        if effect[un]:
            continue                       # 特效不當「移開的遮擋者」(半透明疊加,不造破洞)
        mu = canvas[un]
        for lower in parts_full:
            ln = lower["name"]
            if lower["z"] >= upper["z"] or effect[ln]:
                continue                   # 只看更下層;下層是特效(背景光暈)→ 其切件本就完整,跳過
            ml = canvas[ln]
            present = mu & ml              # 下層已有內容、被上層蓋 → 露出區
            pa = int(present.sum())
            if pa >= max(50, 0.01 * lower["area"]):
                ys, xs = np.where(present)
                reveal.append({
                    "revealed_part": ln, "hidden_by": un, "mover_role": role[un],
                    "area_px": pa, "frac_of_part": round(pa / max(lower["area"], 1), 3),
                    "region_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                    "note": f"『{un}』({role[un]})移開後露出『{ln}』此區;下層已完整 → 不需補圖",
                })
            # 封閉破洞:下層輪廓內的透明,且被上層覆蓋
            holes = ndimage.binary_fill_holes(ml) & ~ml
            hole_under = holes & mu
            ha = int(hole_under.sum())
            if ha >= max(50, 0.005 * lower["area"]):
                ys, xs = np.where(hole_under)
                inpaint.append({
                    "inpaint_part": ln, "under_mover": un, "mover_role": role[un],
                    "hole_area_px": ha,
                    "region_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                    "reason": f"『{ln}』輪廓內封閉破洞被『{un}』蓋住;移開後露出破洞 → 需補繪",
                })
    reveal.sort(key=lambda d: -d["area_px"])
    inpaint.sort(key=lambda d: -d["hole_area_px"])
    verdict = ("分層完整,補圖需求極低(0 封閉破洞)——PSD-first 契約成立"
               if not inpaint else f"偵測到 {len(inpaint)} 處封閉破洞候選,需美術補繪")
    return {"verdict": verdict, "reveal_on_move": reveal, "inpaint_candidates": inpaint}


def slicing_strategy(parts_out, source_name):
    rows = []
    for p in parts_out:
        eff = p["classification"]["is_effect"]
        # mesh vs region:軟/大/會形變 → mesh;剛體小件 → region(沿用 S3/S4 慣例)
        if eff or p["metrics"]["soft"] >= 0.15 or p["metrics"]["coverage"] >= 0.15:
            geo = "mesh(軟邊/大面積/易形變)"
        elif p.get("struct_role") in ("limb", "head"):
            geo = "region(剛體;旋轉/位移即可)或按需 mesh"
        else:
            geo = "region"
        rows.append({
            "part": p["name"],
            "slot_name": f"{source_name}/{p['name']}",     # S4 揭示的命名慣例
            "cut": "獨立切件 + 每邊 1px(atlas 2px)padding",
            "geometry": geo,
            "pivot_hint": p["metrics"]["centroid"],         # 先給質心,骨架階段再微調
            "note": "特效件" if eff else f"結構件/{p.get('struct_role','')}",
        })
    return {"convention": "slot=<檔名>/<圖層名>;件尺寸=原始邏輯尺寸;atlas 可 0.70 縮小打包",
            "parts": rows}


def analyze(psd_path, genre="slot_bigwin"):
    psd, manifest, parts = slice_psd(psd_path)
    W, H = psd.width, psd.height
    source = os.path.splitext(os.path.basename(psd_path))[0]
    # 指標
    full = [part_metrics(e, im, W, H) for e, im in parts]
    n = len(full)
    parts_out = []
    struct_metrics = []  # 佔位,先分類再定角色
    # 先分類特效
    classifications = []
    for i, m in enumerate(full):
        others = [full[j] for j in range(n) if j != i]
        classifications.append(classify_effect(m, parts[i][0]["name"], others, n))
    struct = [full[i] for i in range(n) if not classifications[i]["is_effect"]]
    for i, (e, im) in enumerate(parts):
        m = full[i]; c = classifications[i]
        role = None if c["is_effect"] else label_structural_role(m, e["name"], W, H, struct)
        pub_m = {k: m[k] for k in ("area", "bbox", "size", "centroid", "soft",
                                   "coverage", "detail", "sat", "val", "z")}
        parts_out.append({"name": e["name"], "z": e["z"], "opacity": e["opacity"],
                          "metrics": pub_m, "classification": c, "struct_role": role})
    spec = {
        "source": os.path.basename(psd_path),
        "canvas": [W, H],
        "genre": genre,
        "1_movable_parts": [
            {"name": p["name"], "z": p["z"], "bbox": p["metrics"]["bbox"],
             "area": p["metrics"]["area"], "centroid": p["metrics"]["centroid"]}
            for p in parts_out],
        "2_effects": [
            {"name": p["name"], "is_effect": p["classification"]["is_effect"],
             "subtype": p["classification"]["subtype"], "score": p["classification"]["score"],
             "signals": p["classification"]["signals"],
             "struct_role": p["struct_role"]}
            for p in parts_out],
        "3_motion_storyboard": build_storyboard(parts_out, genre),
        "4_slicing_strategy": slicing_strategy(parts_out, source),
        "5_occlusion": occlusion_reveal_inpainting(full, parts_out, W, H),
    }
    return spec


def to_markdown(spec):
    L = []
    L.append(f"# 目標圖反推規格 — {spec['source']}  ({spec['canvas'][0]}×{spec['canvas'][1]}, 類型={spec['genre']})\n")
    L.append("## 1. 運動構件(可動件)")
    L.append("| 件 | z | bbox | 面積 | 質心 |")
    L.append("|---|--:|---|--:|---|")
    for p in spec["1_movable_parts"]:
        L.append(f"| {p['name']} | {p['z']} | {p['bbox']} | {p['area']} | {p['centroid']} |")
    L.append("\n## 2. 周邊特效分類")
    L.append("| 件 | 判定 | 子類 | 分數 | 結構角色 |")
    L.append("|---|---|---|--:|---|")
    for p in spec["2_effects"]:
        L.append(f"| {p['name']} | {'特效' if p['is_effect'] else '結構'} | {p['subtype'] or '-'} "
                 f"| {p['score']} | {p['struct_role'] or '-'} |")
    L.append("\n## 3. 動作腳本 / 分鏡(先驗提案)")
    sb = spec["3_motion_storyboard"]
    L.append(f"> 類型:{sb['genre_desc']}  檔位變體:{sb['tier_variants']}  狀態:{sb['status']}")
    for b in sb["beats"]:
        L.append(f"\n### {b['beat']} — {b['desc']}")
        L.append("| 件 | 角色 | 動作 |")
        L.append("|---|---|---|")
        for r in b["parts"]:
            L.append(f"| {r['part']} | {r['role']} | {r['action']} |")
    L.append("\n## 4. 拆圖策略(交付規格)")
    ss = spec["4_slicing_strategy"]
    L.append(f"> 慣例:{ss['convention']}")
    L.append("| 件 | slot 命名 | 切法 | 幾何 | pivot 提示 | 備註 |")
    L.append("|---|---|---|---|---|---|")
    for r in ss["parts"]:
        L.append(f"| {r['part']} | {r['slot_name']} | {r['cut']} | {r['geometry']} | {r['pivot_hint']} | {r['note']} |")
    L.append("\n## 5. 遮擋 / 露出 / 補圖分析")
    oc = spec["5_occlusion"]
    L.append(f"> **判定:{oc['verdict']}**")
    L.append("\n### 5A. 露出區(運動移開後露出;下層已完整 → 不需補圖,知會 rigger)")
    if not oc["reveal_on_move"]:
        L.append("(無)")
    else:
        L.append("| 露出件 | 被誰蓋 | 移動者角色 | 面積px | 佔該件% | 區域bbox |")
        L.append("|---|---|---|--:|--:|---|")
        for it in oc["reveal_on_move"]:
            L.append(f"| {it['revealed_part']} | {it['hidden_by']} | {it['mover_role']} | {it['area_px']} "
                     f"| {it['frac_of_part']*100:.1f}% | {it['region_bbox']} |")
    L.append("\n### 5B. 補圖候選(封閉破洞)")
    if not oc["inpaint_candidates"]:
        L.append("(0 封閉破洞 — 分層完整,無需補繪)")
    else:
        L.append("| 需補件 | 破洞被誰蓋 | 破洞面積px | 區域bbox |")
        L.append("|---|---|--:|---|")
        for it in oc["inpaint_candidates"]:
            L.append(f"| {it['inpaint_part']} | {it['under_mover']} | {it['hole_area_px']} | {it['region_bbox']} |")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--json", default=None, help="輸出 spec JSON 路徑")
    ap.add_argument("--md", default=None, help="輸出 markdown 規格路徑")
    a = ap.parse_args()
    spec = analyze(a.psd, a.genre)
    if a.json:
        json.dump(spec, open(a.json, "w"), ensure_ascii=False, indent=2)
    md = to_markdown(spec)
    if a.md:
        open(a.md, "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
