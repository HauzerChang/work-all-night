#!/usr/bin/env python3
"""驗證清單:改完 Spine JSON 後,證明「只動了該動的、沒撐長動畫、拿到的就是編輯器承諾的」。

結構閘(spine-motion-skill 第 6 步的清單,逐條可機讀):
  V1 新動畫總長 == 原動畫總長
  V2 兩份動畫之間有差異的骨骼 == 只有目標骨骼
  V3 slot timeline 完全相同(除非刻意切 attachment)
  V4 原動畫逐 byte 未被碰(新版另存時)
  V5 skins(權重/attachment)未被碰
  V6 其他所有動畫未被碰
  V7 所有 keyframe 時間 ≤ 總長(超過 = 動畫被撐長 = 主體末尾凍結)

量化閘(閉迴路,證明「編輯器畫的」==「Spine 裡真的發生的」):
  Q1 目標點世界軌跡 vs 編輯器預測 的最大誤差
  Q2 實測自身位移 own(t) vs spec 設計值 的最大誤差(關鍵幀 / 全時段)
  Q3 實測滯後幀、own↔主體相關、峰對峰幅度(前 → 後)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spine_world as W  # noqa: E402


def _clone_no_anim(data):
    return {k: v for k, v in data.items() if k != "animations"}


def structural_checks(orig_data, new_data, anim, new_anim, target_bone, allow_slots=False):
    """回傳 [(id, ok, 說明)]。orig_data = 修改前的完整 JSON(backup)。"""
    res = []
    oa = orig_data["animations"][anim]
    na = new_data["animations"].get(new_anim)
    if na is None:
        return [("V0", False, f"新動畫 '{new_anim}' 不存在")]

    do, dn = W.duration(oa), W.duration(na)
    res.append(("V1", abs(do - dn) < 1e-9, f"總長 {do:.5f}s → {dn:.5f}s"))

    ob, nb = oa.get("bones", {}), na.get("bones", {})
    diff = sorted({b for b in set(ob) | set(nb) if ob.get(b) != nb.get(b)})
    res.append(("V2", diff == [target_bone], f"有差異的骨骼 = {diff or '(無)'}(應只有 {target_bone})"))

    same_slots = oa.get("slots", {}) == na.get("slots", {})
    res.append(("V3", same_slots or allow_slots, "slot timeline " + ("相同" if same_slots else "有變動")))

    if new_anim != anim:
        same_orig = orig_data["animations"][anim] == new_data["animations"].get(anim)
        res.append(("V4", same_orig, "原動畫 " + ("未被碰" if same_orig else "**被改到**")))
    else:
        res.append(("V4", True, "就地覆寫模式(使用者指定),不檢查原動畫"))

    same_skin = orig_data.get("skins") == new_data.get("skins")
    res.append(("V5", same_skin, "skins(權重/attachment)" + ("未被碰" if same_skin else "**被改到**")))

    others = sorted(set(orig_data["animations"]) - {anim})
    bad = [a for a in others if orig_data["animations"][a] != new_data["animations"].get(a)]
    res.append(("V6", not bad, f"其他 {len(others)} 支動畫" + ("未被碰" if not bad else f"**被改到**:{bad}")))

    over = []
    for bone, chans in nb.items():
        for ch, keys in chans.items():
            for k in keys:
                if float(k.get("time", 0.0)) > do + 1e-9:      # 以**原動畫**總長為準
                    over.append((bone, ch, k.get("time")))
    res.append(("V7", not over, f"keyframe 時間都 ≤ 原總長 {do:.5f}s" if not over
                else f"**超出原總長**:{over[:3]}"))
    return res


def measure(data, anim_name, bone, body_bone, fps, spf, point):
    """回傳 dict:frames / rigid / rotOwn / transOwn / own(=rot+trans) / actual,皆為 [(x,y)]。"""
    sk = W.Skel(data)
    anim = data["animations"][anim_name]
    dur = W.duration(anim)
    n = max(1, int(round(dur * fps * spf)))
    ts = [dur * i / n for i in range(n + 1)]
    px, py = point
    sp = [sk.own_split(bone, anim, t, px, py) for t in ts]
    return {
        "frame": [t * fps for t in ts],
        "rigid": [p[0] for p in sp],
        "rotOwn": [p[1] for p in sp],
        "transOwn": [p[2] for p in sp],
        "own": [(p[1][0] + p[2][0], p[1][1] + p[2][1]) for p in sp],
        "actual": [p[3] for p in sp],
    }


def quantitative(orig_data, new_data, anim, new_anim, bone, body_bone, fps, spf, point,
                 intent=None, predicted=None):
    """intent: callable(frame)->(wx,wy) 設計值;predicted: {'frame':[],'worldX':[],'worldY':[]} 編輯器預測。"""
    M = measure(new_data, new_anim, bone, body_bone, fps, spf, point)
    O = measure(orig_data, anim, bone, body_bone, fps, spf, point)
    fr = M["frame"]
    out = {}

    def pp(v):
        return round(max(v) - min(v), 3)

    def dm(v):
        m = sum(v) / len(v)
        return [x - m for x in v]

    def ax(series, i):
        return [p[i] for p in series]

    out["amplitude"] = {
        "ownX": (pp(ax(O["own"], 0)), pp(ax(M["own"], 0))),
        "ownY": (pp(ax(O["own"], 1)), pp(ax(M["own"], 1))),
        "transOwnY": (pp(ax(O["transOwn"], 1)), pp(ax(M["transOwn"], 1))),
        "actualX": (pp(ax(O["actual"], 0)), pp(ax(M["actual"], 0))),
        "actualY": (pp(ax(O["actual"], 1)), pp(ax(M["actual"], 1))),
        "rigidY": (pp(ax(O["rigid"], 1)), pp(ax(M["rigid"], 1))),
    }
    out["corr"] = {
        "x": (round(W.pearson(dm(ax(O["rigid"], 0)), ax(O["own"], 0)), 4),
              round(W.pearson(dm(ax(M["rigid"], 0)), ax(M["own"], 0)), 4)),
        "y": (round(W.pearson(dm(ax(O["rigid"], 1)), ax(O["own"], 1)), 4),
              round(W.pearson(dm(ax(M["rigid"], 1)), ax(M["own"], 1)), 4)),
    }
    lc, rc, ls, rs = W.best_lag(dm(ax(M["rigid"], 1)), ax(M["own"], 1), spf)
    out["lagY"] = {"complementary": lc, "r": round(rc, 4), "sync": ls, "rSync": round(rs, 4)}

    if intent is not None:
        # 設計值只描述 translate 通道造成的自身位移 → 與實測 transOwn 比
        errs = [max(abs(intent(f)[0] - o[0]), abs(intent(f)[1] - o[1])) for f, o in zip(fr, M["transOwn"])]
        out["intentErrMax"] = round(max(errs), 5)
        out["intentErrMean"] = round(sum(errs) / len(errs), 5)
    if predicted:
        pf, pxs, pys = predicted["frame"], predicted["worldX"], predicted["worldY"]
        idx = {round(f, 3): i for i, f in enumerate(fr)}
        errs = []
        for f, x, y in zip(pf, pxs, pys):
            i = idx.get(round(f, 3))
            if i is not None:
                errs.append(max(abs(x - M["actual"][i][0]), abs(y - M["actual"][i][1])))
        out["predictErrMax"] = round(max(errs), 5) if errs else None
        out["predictErrN"] = len(errs)
    return out


def report(checks, quant=None):
    lines = ["驗證清單:"]
    for cid, ok, msg in checks:
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {cid} {msg}")
    if quant:
        lines.append("量化(前 → 後):")
        a = quant["amplitude"]
        for k, (b, af) in a.items():
            lines.append(f"  峰對峰 {k:<8} {b:8.3f} → {af:8.3f} px")
        lines.append(f"  own↔主體相關 X {quant['corr']['x'][0]:+.3f} → {quant['corr']['x'][1]:+.3f}   "
                     f"Y {quant['corr']['y'][0]:+.3f} → {quant['corr']['y'][1]:+.3f}")
        ly = quant["lagY"]
        lines.append(f"  互相關最佳滯後 Y:互補 {ly['complementary']:g} 幀 (r={ly['r']:+.2f})、"
                     f"同步 {ly['sync']:g} 幀 (r={ly['rSync']:+.2f})")
        if "intentErrMax" in quant:
            lines.append(f"  Q2 實測 own vs 設計值 最大誤差 {quant['intentErrMax']} px(平均 {quant['intentErrMean']})")
        if quant.get("predictErrMax") is not None:
            lines.append(f"  Q1 世界軌跡 vs 編輯器預測 最大誤差 {quant['predictErrMax']} px({quant['predictErrN']} 點)")
    return "\n".join(lines)


def all_pass(checks):
    return all(ok for _, ok, _ in checks)
