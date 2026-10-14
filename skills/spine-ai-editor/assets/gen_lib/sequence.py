#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib.sequence — spine-ai-editor 2.0 的**序列組合(compose / crossfade / loop)入口**(MERGE_PLAN Phase B4)。

B2(`make_beat.generate_bigwin`)把「**單一** beat」生成包成 skill 入口;B3(`pivot_axis`)加了「繞關節
pivot 變換」結構軸。B4 把 repo 半年累積的**跨 beat 序列組合**(`gen_animations.compose_sequence` /
`crossfade_sequence` + C1 判準)抽成 skill 層級的**一條流程**:給一組「拆件(part)」+ 一個 beat 順序
(`order`) → 產出一份 **schema 合法、過 G1、validator_v1 乾淨** 的**單一可載入** Spine 序列動畫
(In → 主秀節拍… → Loop → Out,或 loopable 的 Idle_Loop)。

== 為什麼存在(B4 相對 B2/B3 的增量 + MERGE_PLAN 指名的「G1 真正戰場」)==
  B2 證「單一 beat」能過 validator_v1;B1 的洞見明記:**單 beat 本就無末鍵 curve(`_bez` 只 curve
  `frames[:-1]`),G1 的真正風險在序列 compose/crossfade** —— 相鄰 beat 接點去重可能把某段的 outgoing
  curve 推到 timeline 末鍵(地雷 #12,runtime 不炸、editor 匯入 AIOOBE crash)。B4 把**序列層**的生成
  固化成對外契約,並以閘 `tools/analyzer/validate_b4_sequence.py` 在**序列層**機械化驗 G2 雙真值
  (遊戲能播 **且** 編輯器能匯入)+ 相異 beat 接點 C1 連續 + loop 閉合 + stiffness 不升。

  **B4 的實測結論(把 B1 的假設關掉)**:此生成器家族的 compose 與 crossfade **天生 editor-safe**:
    · `compose_sequence` 接點去重**丟前者尾幀、保留後者首幀**;前者尾幀必為該 clip 之末(`_bez` 從不
      curve 末鍵)→ 去重永遠丟「乾淨幀」,且序列最末幀 = 最後一個 beat 的末幀(亦乾淨)→ **末鍵 curve 恆 0**。
      (內部仍保有各 beat 的 bezier,非末位,editor 不炸。)
    · `crossfade_sequence` 把序列**重取樣成純線性關鍵幀**(無 curve/c2/c3/c4)→ **末鍵 curve 恆 0**。
  即 G1 在序列層拔 0 條(與 B3 密網格重取樣同屬「結構上 editor-safe」)。閘仍**過 G1**(防禦縱深)並以
  **手動注入接點末鍵 curve 的負對照**證 validator_v1 抓得到地雷 #12 → 閘非恆真。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:每個序列輸出前一律 `curve_tools.strip_last_frame_curves()`(此家族拔 0 條,仍做)。
  - **G3 不覆蓋美術原檔**:從零生成一支新序列動畫(bones/slots/skin 占位 + 單一 composed animation)。

== 過渡期相依(B4 → E1)==
  本檔經 `make_beat._wire_repo_tools()` import repo 的 `tools/analyzer`(gen_animations)與 `assets/curve_tools`。
  **Phase E1** 會 bundle 進 `assets/`(self-contained,G5),屆時移除此相依。

用法(CLI):
  python3 sequence.py --mode compose   --out /tmp/seq.json       # 一次性大獎序列 In→…→Out
  python3 sequence.py --mode crossfade --xf 0.15 --out /tmp/x.json
  python3 sequence.py --mode idle      --repeats 2 --out /tmp/idle.json   # loopable idle
  python3 sequence.py --self-test

程式化:
  from gen_lib.sequence import compose_bigwin_sequence, crossfade_bigwin_sequence, compose_idle_loop
  skel, name = crossfade_bigwin_sequence(IDLE_DEMO_PARTS, xf=0.15)   # 已過 G1,單一可載入序列
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from make_beat import (_wire_repo_tools, _assemble_skeleton,   # noqa: E402
                       DEMO_PARTS, IDLE_DEMO_PARTS)

# 正向大獎序列(手感 PROPOSAL 排序;客觀不變量 = 接點無縫 / C1 / loop 閉合 / stiffness 由閘把關):
#   In(collapsed→id) → hit → combo → charge → cascade(皆 id→id)→ Loop(id→id)→ Out(id→collapsed)
# 內部接點全 identity==identity → C0 無縫;首為 collapsed 起手、尾為 collapsed 收尾(合理進出場,**非** loopable)。
STANDARD_BIGWIN_ORDER = ["In", "hit", "combo", "charge", "cascade", "Loop", "Out"]

SUPPORTED_MODES = ("compose", "crossfade", "idle")


def build_beat_library(parts, beats=None, cascade_dir=None,
                       cascade_reveal=False, cascade_wobble=False):
    """用 `gen_animations.build_animations` 一次產出 `beats` 列出的所有獨立 beat clip。

    parts  : [{"part","role","action"} ...](見 DEMO_PARTS / IDLE_DEMO_PARTS)。
    beats  : 要生成的 beat 名集合;None → STANDARD_BIGWIN_ORDER 去重。
    回傳 (skel_scaffold, anims_dict):
      skel_scaffold = schema 合法最小 skeleton(bones/slots/skin 占位,animations 空)。
      anims_dict    = {beat 名: anim clip},供 compose / crossfade 串接。
    """
    G, _ = _wire_repo_tools()
    if not parts:
        raise ValueError("parts 不可為空")
    if beats is None:
        beats = list(dict.fromkeys(STANDARD_BIGWIN_ORDER))
    skel = _assemble_skeleton(parts)
    gen_skel = {"skeleton": skel["skeleton"], "bones": skel["bones"]}
    storyboard = {"beats": [{"beat": b,
                             "parts": [{"part": p["part"], "role": p["role"], "action": "主秀"}
                                       for p in parts]}
                            for b in beats]}
    anims = G.build_animations(gen_skel, storyboard, cascade_dir=cascade_dir,
                              cascade_reveal=cascade_reveal, cascade_wobble=cascade_wobble)
    return skel, anims


def seal_sequence(skel_scaffold, anims, order, mode="compose", xf=0.15,
                  ramp="smoothstep", nsamp=16, apply_g1=True, anim_name=None):
    """把 `order` 的 beat clip 以 `mode` 串成**單一** composed animation,塞回一份獨立 skeleton,**過 G1**。

    mode     : "compose"(純時間平移 + 接點去重,接點瞬切)/ "crossfade"(接點重疊 xf 秒 + C1 斜坡混合)。
    xf/ramp/nsamp : crossfade 參數(mode="crossfade" 時生效;ramp="smoothstep" → 相異接點 C1 連續)。
    apply_g1 : True(預設)→ 輸出前拔末鍵 curve(此家族拔 0 條,仍做;防禦縱深)。False 僅供負對照。
    回傳 (skeleton_dict, anim_name)。不改輸入 scaffold(deepcopy),可對同一 library 反覆 seal。
    """
    G, ct = _wire_repo_tools()
    if mode not in ("compose", "crossfade"):
        raise ValueError("mode 須為 compose / crossfade,收到 {!r}".format(mode))
    if not order:
        raise ValueError("order 不可為空")
    if mode == "compose":
        composed, _segs = G.compose_sequence(anims, order)
        default_name = "BigWin_Seq"
    else:
        composed, _segs = G.crossfade_sequence(anims, order, xf, nsamp=nsamp, ramp=ramp)
        default_name = "BigWin_Seq_xf"
    aname = anim_name or default_name
    skel = copy.deepcopy(skel_scaffold)
    skel["animations"] = {aname: composed}
    if apply_g1:
        ct.strip_last_frame_curves(skel["animations"][aname])
    return skel, aname


def compose_bigwin_sequence(parts, order=None, apply_g1=True, anim_name="BigWin_Seq",
                            cascade_dir=None, cascade_reveal=False, cascade_wobble=False):
    """純時間平移 + 接點去重 把 order 串成**一次性**大獎序列(In→…→Out)。回傳 (skeleton_dict, anim_name)。

    一次性序列(首 collapsed、尾 collapsed)**設計上非 loopable**(進出場語意);相異 beat 接點 **C0 無縫但
    C1 不連續**(離散節拍,接點速度突變)—— 要平滑接點改用 `crossfade_bigwin_sequence`。
    """
    if order is None:
        order = list(STANDARD_BIGWIN_ORDER)
    skel, anims = build_beat_library(parts, beats=list(dict.fromkeys(order)),
                                     cascade_dir=cascade_dir, cascade_reveal=cascade_reveal,
                                     cascade_wobble=cascade_wobble)
    return seal_sequence(skel, anims, order, mode="compose",
                         apply_g1=apply_g1, anim_name=anim_name)


def crossfade_bigwin_sequence(parts, order=None, xf=0.15, ramp="smoothstep", nsamp=16,
                              apply_g1=True, anim_name="BigWin_Seq_xf",
                              cascade_dir=None, cascade_reveal=False, cascade_wobble=False):
    """同 compose 但接點以 **crossfade(重疊 xf 秒 + C1 斜坡混合)** 串接。回傳 (skeleton_dict, anim_name)。

    `ramp="smoothstep"`(w'(0)=w'(1)=0)→ 相異 beat 接點 **C1 連續**(消 compose 的接點速度 kink);
    `ramp="linear"` 則接點仍 kink(crossfade 本身不足以 C1,**C1 斜坡**才是鑑別子)。crossfade 輸出為**純線性
    關鍵幀** → 天生無末鍵 curve(editor-safe);實測 stiffness **低於** compose(接點平滑 → 不升反降)。
    """
    if order is None:
        order = list(STANDARD_BIGWIN_ORDER)
    skel, anims = build_beat_library(parts, beats=list(dict.fromkeys(order)),
                                     cascade_dir=cascade_dir, cascade_reveal=cascade_reveal,
                                     cascade_wobble=cascade_wobble)
    return seal_sequence(skel, anims, order, mode="crossfade", xf=xf, ramp=ramp,
                         nsamp=nsamp, apply_g1=apply_g1, anim_name=anim_name)


def compose_idle_loop(parts, repeats=2, apply_g1=True, anim_name="Idle_Loop"):
    """把 Loop beat 重複 `repeats` 次串成一支 **loopable** idle 序列(首==尾,可無縫重播)。

    回傳 (skeleton_dict, anim_name)。parts 建議用 IDLE_DEMO_PARTS(limb 走 rotate 擺盪,繞關節 pivot 的典型來源)。
    與大獎一次性序列的關鍵差異:Loop 首尾皆 identity → 重複串接後**首==尾** → 可接 Loop(C0 閉合;Loop 本身亦
    `is_c1_loopable`)。這正是 MERGE_PLAN B4 AC「首尾可接 Loop」的客觀落點。
    """
    G, ct = _wire_repo_tools()
    if repeats < 1:
        raise ValueError("repeats 須 ≥ 1")
    skel, anims = build_beat_library(parts, beats=["Loop"])
    composed, _segs = G.compose_sequence(anims, ["Loop"] * repeats)
    skel = copy.deepcopy(skel)
    skel["animations"] = {anim_name: composed}
    if apply_g1:
        ct.strip_last_frame_curves(skel["animations"][anim_name])
    return skel, anim_name


def write_sequence(parts, out_path, mode="compose", **opts):
    """產序列 + 寫檔(UTF-8, indent=1)。回傳 (out_path, anim_name)。mode: compose/crossfade/idle。"""
    if mode == "idle":
        skel, aname = compose_idle_loop(parts, **opts)
    elif mode == "crossfade":
        skel, aname = crossfade_bigwin_sequence(parts, **opts)
    elif mode == "compose":
        skel, aname = compose_bigwin_sequence(parts, **opts)
    else:
        raise ValueError("mode 須為 {} 之一".format(SUPPORTED_MODES))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)
    return out_path, aname


# --------------------------------------------------------------------- 自檢(不寫檔)
def _count_lastkey_curves(anim):
    n = 0
    for sec in ("bones", "slots"):
        for chans in anim.get(sec, {}).values():
            for frames in chans.values():
                if isinstance(frames, list) and frames and isinstance(frames[-1], dict) \
                   and any(k in frames[-1] for k in ("curve", "c2", "c3", "c4")):
                    n += 1
    return n


def _self_test():
    """compose / crossfade / idle 各產一支,回報 bone 數與末鍵 curve 數(G1 後應 0)。
    完整 validator_v1 雙真值驗收見 tools/analyzer/validate_b4_sequence.py。"""
    ok = True
    cases = [
        ("compose",   lambda: compose_bigwin_sequence(IDLE_DEMO_PARTS)),
        ("crossfade", lambda: crossfade_bigwin_sequence(IDLE_DEMO_PARTS, xf=0.15)),
        ("idle",      lambda: compose_idle_loop(IDLE_DEMO_PARTS, repeats=2)),
    ]
    for label, fn in cases:
        skel, aname = fn()
        anim = skel["animations"][aname]
        nb = len(anim.get("bones", {}))
        lk = _count_lastkey_curves(anim)
        good = nb >= 2 and lk == 0
        ok = ok and good
        print("  {:10s} anim={:14s} bones={} lastframe_curves={} -> {}".format(
            label, aname, nb, lk, "OK" if good else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="gen_lib 序列組合入口(B4)")
    ap.add_argument("--mode", default="compose", choices=SUPPORTED_MODES)
    ap.add_argument("--out", help="輸出 skeleton.json 路徑")
    ap.add_argument("--xf", type=float, default=0.15, help="crossfade 重疊秒數")
    ap.add_argument("--ramp", default="smoothstep", help="crossfade 斜坡:smoothstep/smootherstep/linear")
    ap.add_argument("--repeats", type=int, default=2, help="idle Loop 重複次數")
    ap.add_argument("--idle-parts", action="store_true", help="用 IDLE_DEMO_PARTS(limb 走 rotate)")
    ap.add_argument("--no-g1", action="store_true", help="不拔末鍵 curve(除錯/負對照用)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        ok = _self_test()
        print("SELF-TEST:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)

    parts = IDLE_DEMO_PARTS if (a.idle_parts or a.mode == "idle") else DEMO_PARTS
    if not a.out:
        ap.error("需要 --out(或用 --self-test)")
    opts = {"apply_g1": not a.no_g1}
    if a.mode == "idle":
        opts["repeats"] = a.repeats
    elif a.mode == "crossfade":
        opts.update(xf=a.xf, ramp=a.ramp)
    out, aname = write_sequence(parts, a.out, mode=a.mode, **opts)
    print(json.dumps({"out": out, "anim": aname, "mode": a.mode, "parts": len(parts),
                      "g1_applied": not a.no_g1}, ensure_ascii=False))


if __name__ == "__main__":
    main()
