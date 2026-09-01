#!/usr/bin/env python3
"""candidate 0e — 分鏡(storyboard)→ Spine 3.8 mesh `deform` timeline(純 CPU,確定性)。

補 `gen_animations.py`(candidate 0d)的缺口:0d 只產 **bone TRS + slot alpha**,mesh 本身不變形。
本器讓 build --animate 的**軟件/特效 mesh**(窗簾、光暈、陰影)真的會 deform,而非只被控制骨剛性搬動。

設計原則(RULES:確定性演算法 + 評估器,不用 ML 學美術決定;變形**用真實位移場轉移**不用未校準 stress_field):
  - **運動來源 = 真實藝術家 deform 場**:由 `deform_eval.real_deform_field` 從真實 main_draw 窗簾/陰影 mesh
    抽出「總位移最大幀」的逐頂點位移場(以 UV 為座標,可轉移到任一拓樸)。這是「柔性布料律動」模板。
  - **轉移**:把該場以 UV 內插(griddata linear + nearest 補洞)套到目標 mesh 的頂點 → 目標 mesh 的位移場。
  - **時間包絡(beat 相依,首尾強制回 setup → 可無縫串接)**:
      loop  :ucos 0→peak→0 正弦包絡(端點=0=setup → 無縫 AC + 與 bone loop 同介面)。
      intro :swell 0→peak(0.6T)→0(settle to setup);ease-out bezier。
      pulse :對稱 0→peak→0。
      outro/hold:mesh 不變形(不寫 deform key;靜態交給 bone scale/alpha)。
  - **幅度校準**:peak 為真實場的**分數**(loop 0.5、intro 0.7、pulse 0.6)→ 位移必 ≤ 真實 deform 幅度
    (真實 max=314.7px);gate 再逐幀確認拓樸乾淨(自交/翻面/退化=0)。

Spine 3.8 deform 格式(寫回 `animations[beat]["deform"]`):
  {skinName: {slot: {attachmentName: [ {"time":t, "offset":0, "vertices":[dx0,dy0,...], "curve":..} ]}}}
  deform vertices 為 attachment-local、y-up(與 mesh setup vertices 同空間),逐頂點相加(見 deform_eval.apply_deform)。
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
from gen_animations import beat_category, safe, DUR, EASE

# 各 beat 類別的取樣數與 peak(真實場的分數 → 位移必 ≤ 真實幅度)。
DEFORM_SAMPLES = {"loop": 12, "intro": 5, "pulse": 5}
DEFORM_PEAK = {"loop": 0.50, "intro": 0.70, "pulse": 0.60}
# 產 deform 的類別;outro/hold → mesh 靜態(不寫 key)。
DEFORM_CATS = set(DEFORM_SAMPLES)


def transfer_field(uvs_src, field, uvs_dst):
    """真實位移場(uvs_src 座標、y-up)→ 內插到 uvs_dst 的逐頂點位移(Nx2)。
    linear 內插 + nearest 補 convex-hull 外的 NaN(同 deform_eval.transfer_deform_check 的約定)。"""
    from scipy.interpolate import griddata
    out = np.zeros((len(uvs_dst), 2), dtype=np.float64)
    for c in (0, 1):
        lin = griddata(uvs_src, field[:, c], uvs_dst, "linear")
        nea = griddata(uvs_src, field[:, c], uvs_dst, "nearest")
        out[:, c] = np.where(np.isnan(lin), nea, lin)
    return out


def _envelope(cat):
    """回傳 [(tau, scale, eased)]。tau∈[0,1];scale 乘在目標位移場;eased→插 ease-out bezier。
    首尾 scale 皆 0 → deform 回 setup → beat 間無縫、與 bone timeline 同介面。"""
    peak = DEFORM_PEAK[cat]
    if cat == "loop":
        n = DEFORM_SAMPLES["loop"]
        pts = [(i / n, peak * (1 - math.cos(2 * math.pi * (i / n))) / 2.0, False) for i in range(n + 1)]
        pts[-1] = (1.0, pts[0][1], False)   # 端點強制相等(消浮點殘差)→ 無縫
        return pts
    if cat == "intro":
        return [(0.0, 0.0, True), (0.6, peak, True), (1.0, 0.0, False)]
    if cat == "pulse":
        return [(0.0, 0.0, True), (0.5, peak, True), (1.0, 0.0, False)]
    return []


def synthesize(target_mesh, uvs_src, field, cat):
    """合成單一 mesh 在單一 beat 的 Spine deform frames(空 list = 該 beat 不變形)。"""
    if cat not in DEFORM_CATS:
        return []
    uvs_dst = np.array(target_mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    dfield = transfer_field(uvs_src, field, uvs_dst)   # Nx2 目標位移場(peak 前)
    T = DUR[cat]
    frames = []
    for (tau, scale, eased) in _envelope(cat):
        dv = (dfield * scale).reshape(-1)
        f = {"time": round(tau * T, 4), "offset": 0,
             "vertices": [round(float(x), 3) for x in dv]}
        if eased:
            f["curve"] = EASE; f["c2"] = 0.0; f["c3"] = EASE; f["c4"] = 1.0
        frames.append(f)
    return frames


def _mesh_attachments(skeleton):
    """回傳 [(skinName, slot, attName, mesh_dict)];mesh_dict 含 uvs/vertices/triangles。
    相容兩種 skins 表示:
      - list 形(如真實 main_draw):[{"name":..,"attachments":{slot:{att}}}]
      - dict 形(build_spine 產出):{skinName:{slot:{att}}} 或 {"attachments":{slot:{att}}}"""
    skins = skeleton.get("skins", [])
    out = []
    if isinstance(skins, list):
        for sk in skins:
            nm = sk.get("name", "default")
            for slot, atts in sk.get("attachments", {}).items():
                for an, a in atts.items():
                    if isinstance(a, dict) and a.get("type") == "mesh":
                        out.append((nm, slot, an, a))
        return out
    # dict 形:先判斷是否 {"attachments":{...}} 單 skin,否則視為 {skinName:{slot:{att}}}
    if isinstance(skins, dict):
        if "attachments" in skins and isinstance(skins["attachments"], dict):
            groups = {"default": skins["attachments"]}
        else:
            groups = skins
        for nm, atts in groups.items():
            if not isinstance(atts, dict):
                continue
            for slot, o in atts.items():
                if not isinstance(o, dict):
                    continue
                for an, a in o.items():
                    if isinstance(a, dict) and a.get("type") == "mesh":
                        out.append((nm, slot, an, a))
    return out


def build_deform(skeleton, storyboard, src_uvs, src_field, per_mesh_source=None):
    """把 mesh deform 寫進 skeleton["animations"][beat]["deform"]。
    per_mesh_source: 可選 {(slot,att): (uvs,field)} 讓每件用自己的真實場(最faithful);
                     否則全體共用 (src_uvs, src_field) 軟布料模板。"""
    meshes = _mesh_attachments(skeleton)
    for beat in storyboard["beats"]:
        name = beat["beat"]
        cat = beat_category(name)
        if cat not in DEFORM_CATS:
            continue
        dfm = {}
        for (skinnm, slot, an, a) in meshes:
            us, fl = (per_mesh_source or {}).get((slot, an), (src_uvs, src_field))
            frames = synthesize(a, us, fl, cat)
            if frames:
                dfm.setdefault(skinnm, {}).setdefault(slot, {})[an] = frames
        if dfm:
            skeleton.setdefault("animations", {}).setdefault(name, {})["deform"] = dfm
    return skeleton


def load_source_field(src_json, slot, name):
    """由真實 spine(如 main_draw)抽一件 mesh 的『最大位移幀』位移場當律動模板。"""
    import deform_eval as de
    sk = json.load(open(src_json, encoding="utf-8"))
    uvs, field, anim = de.real_deform_field(sk, slot, name)
    return uvs, field, anim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json", help="含 mesh + animations(beat)的 skeleton.json")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--src-json", default="assets/main_draw.json", help="律動模板來源真實 spine")
    ap.add_argument("--src-slot", default="image/curtain_left")
    ap.add_argument("--src-name", default="image/curtain_left")
    ap.add_argument("--inplace", action="store_true")
    a = ap.parse_args()
    from analyze_target import analyze
    sk = json.load(open(a.skeleton_json, encoding="utf-8"))
    uvs, field, src_anim = load_source_field(a.src_json, a.src_slot, a.src_name)
    spec = analyze(a.psd, a.genre)
    build_deform(sk, spec["3_motion_storyboard"], uvs, field)
    if a.inplace:
        json.dump(sk, open(a.skeleton_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    summ = {}
    for beat, anim in sk.get("animations", {}).items():
        d = anim.get("deform")
        if d:
            summ[beat] = {sk_: {s: list(v.keys()) for s, v in slots.items()} for sk_, slots in d.items()}
    print(json.dumps({"src_template": f"{a.src_slot}@{src_anim}", "beats_with_deform": summ},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
