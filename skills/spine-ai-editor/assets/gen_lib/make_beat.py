#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**確定性大獎節拍生成**入口(MERGE_PLAN Phase B2)。

這支把 repo 半年累積的確定性生成引擎(`gen_animations.build_animations` + beat_templates +
tier_variants)包成**一條 skill 層級的流程**:給一組「拆件(part)」+ 一個 beat 類型 →
產出一份 **schema 合法、過 G1(末鍵 curve 必拔)、validator_v1 乾淨** 的完整 Spine 3.8 skeleton JSON,
可直接丟進 `assets/spine-viewer.html` 載入播放(使用者端),或進 Cocos。

== 為什麼存在(B2 相對 B1 的增量)==
  B1(`tools/analyzer/validate_v2_bridge.py`)只證明了「repo 的**一支** cascade beat」能過 validator_v1,
  而且是在閘裡**臨時**組 skeleton。B2 把這條流程抽成**可重用的 skill 入口** `generate_bigwin()`,
  並涵蓋 4 種大獎單件運動基元 **cascade / pop(cascade 預設波) / wobble / twist**(見 beat 參數),
  讓「用 skill 生成 → 驗收」成為一條固定、可機讀的流程,而非每次手搭。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:輸出前一律呼叫 `curve_tools.strip_last_frame_curves()`(地雷 #12,
    runtime 不炸、editor 炸)。單 beat 下 repo `_bez` 只 curve `frames[:-1]`,故通常拔 0 條;
    真正的末鍵 curve 風險在**序列 compose/crossfade**(Phase B4),這支先把關卡機械化。
  - **G3 不覆蓋美術原檔**:本流程**從零生成**一份新 skeleton(bones/slots/skin 占位 + animations),
    不碰任何既有檔;要 patch 既有角色請用 `references/animation_patch_patterns.md` 的 patch 流程。

== 過渡期相依(B2 → E1)==
  本檔目前**import repo 的 `tools/analyzer`**(透過下方 `_wire_repo_tools()` 路徑 shim)。
  這是 MERGE_PLAN 明列的**過渡期**做法("或過渡期 references 指向 repo tools")。
  **Phase E1** 會把生成碼 bundle 進 `assets/`(self-contained,滿足 G5),屆時移除此 shim。
  在 repo 環境下(排程)本檔即可跑;純使用者端(無 repo tools)須等 E1 bundle 後才 standalone。

用法(CLI):
  python3 make_beat.py --beat cascade --out /tmp/bigwin.json        # 預設 demo 5 件機器人
  python3 make_beat.py --beat wobble  --out /tmp/w.json
  python3 make_beat.py --beat cascade --cascade-wobble --out /tmp/cw.json
  python3 make_beat.py --psd ../../../assets/robot_parts.psd --genre slot_bigwin --beat cascade --out /tmp/r.json
  python3 make_beat.py --self-test                                   # 不寫檔,跑內建 4 beat 自檢

程式化:
  from gen_lib.make_beat import generate_bigwin, DEMO_PARTS
  skel = generate_bigwin(DEMO_PARTS, beat="cascade")   # dict,已過 G1
"""
from __future__ import annotations
import argparse
import json
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """掛上 **self-contained bundle**(`gen_lib/_bundled/`)與本 `assets/`(validator_v1/curve_tools)。

    E1(2026-10-18)已把生成碼 bundle 進 `_bundled/`(gen_animations / beat_templates /
    tier_variants / spine_anim / pivot_rotation 等 verbatim copy),故**不再相依 repo `tools/`**
    (滿足 MERGE_PLAN G5)。回傳 (gen_animations_module, curve_tools_module)。

    函式名沿用 `_wire_repo_tools` 以維持 gen_lib 內部/pivot_axis/sequence 的既有呼叫簽章零回歸;
    語意已從「掛 repo tools」改為「掛 bundled + assets」。_bundled 清單的真值來源見 `_bundled/README.md`。
    """
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    assets = os.path.dirname(here)                                 # .../assets
    bundled = os.path.join(here, "_bundled")                       # .../assets/gen_lib/_bundled
    for p in (bundled, assets):                                    # bundled 置前:bare import 必命中自帶副本
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import gen_animations as G
        import curve_tools as ct
    except ImportError as e:
        raise ImportError(
            "gen_lib 需要 self-contained bundle(gen_lib/_bundled/gen_animations.py)與 "
            "assets/curve_tools.py。E1 後本 skill 自帶生成碼,不應再缺。原始錯誤:{}".format(e))
    return G, ct


# --------------------------------------------------------------------- demo 件(無需 PSD)
# 5 件機器人大獎典型配置(核心/肢體/特效),用於 standalone 示範與自檢(不依賴 .psd)。
DEMO_PARTS = [
    {"part": "body",  "role": "核心", "action": "主秀"},
    {"part": "head",  "role": "核心", "action": "主秀"},
    {"part": "arm_L", "role": "肢體", "action": "主秀"},
    {"part": "arm_R", "role": "肢體", "action": "主秀"},
    {"part": "光暈",   "role": "特效", "action": "主秀"},
]

# 支援的大獎 beat 類型(skill 入口對外契約)。cascade=跨件 pop 波(預設);
# "pop" 是 cascade 的單件運動基元 → 以 cascade 預設波呈現。wobble/twist 為單件 shear 基元。
SUPPORTED_BEATS = ("cascade", "pop", "wobble", "twist")

# idle/Loop demo 件(B3 繞關節 pivot 變換的典型來源)。**role 用英文**(body/head/limb/特效):
# 大獎 cascade 對所有件一視同仁,idle Loop 則依 role 給不同通道(limb 走 **rotate** 擺盪 → 可繞關節 pivot)。
IDLE_DEMO_PARTS = [
    {"part": "body",  "role": "body", "action": "主秀"},
    {"part": "head",  "role": "head", "action": "主秀"},
    {"part": "arm_L", "role": "limb", "action": "主秀"},
    {"part": "arm_R", "role": "limb", "action": "主秀"},
    {"part": "光暈",   "role": "特效", "action": "主秀"},
]


def parts_from_psd(psd_path, genre="slot_bigwin", beat_source="Loop"):
    """(過渡期)從分層 PSD 反推拆件清單,取某 beat 的 parts(預設 Loop 的主秀件序)。
    回傳 [{"part","role","action"} ...]。需 repo 的 analyze_target(S1 分析器)。"""
    _wire_repo_tools()
    from analyze_target import analyze                      # noqa: E402
    sb = analyze(psd_path, genre)["3_motion_storyboard"]
    beat = next(b for b in sb["beats"] if b["beat"] == beat_source)
    return [{"part": p["part"], "role": p["role"], "action": "主秀"} for p in beat["parts"]]


def _assemble_skeleton(parts):
    """把 parts 組成一份 schema 合法的最小完整 skeleton(bones + slots + default skin 占位)。
    每件給一個 32x32 region 占位 attachment,讓 anim 引用到的 bone/slot 全部存在。"""
    G, _ = _wire_repo_tools()
    bones = [{"name": "root"}]
    slots, skin = [], {}
    for i, p in enumerate(parts):
        bn = "b_" + G.safe(p["part"])
        sn = p["part"]
        bones.append({"name": bn, "parent": "root", "x": 100.0 + 30 * i, "y": 80.0})
        slots.append({"name": sn, "bone": bn, "attachment": sn})
        skin[sn] = {sn: {"width": 32, "height": 32}}
    skel = {
        "skeleton": {"hash": "genlib_b2", "spine": "3.8.75", "x": 0, "y": 0,
                     "width": 713, "height": 693, "images": "./"},
        "bones": bones,
        "slots": slots,
        "skins": {"default": skin},
        "animations": {},
    }
    return skel


def generate_bigwin(parts, beat="cascade", cascade_dir=None,
                    cascade_reveal=False, cascade_wobble=False, apply_g1=True):
    """用 repo 的確定性生成引擎產一支大獎 beat,回傳**過 G1** 的完整 Spine skeleton dict。

    parts        : [{"part","role","action"} ...](見 DEMO_PARTS / parts_from_psd)。
    beat         : SUPPORTED_BEATS 之一。"pop" 走 cascade 預設(pop)波。
    cascade_dir  : cascade 跨件波相位來源(None=件序 / "lr"/"rl"/"co"/"oc" / 角度 / 向量 / ("geo",src))。
    cascade_reveal / cascade_wobble : cascade 的單件運動基元換成入場/晃動波(互斥;見 gen_animations)。
    apply_g1     : True(預設)→ 輸出前拔末鍵 curve(地雷 #12)。設 False 僅供負對照/除錯。

    回傳 (skeleton_dict, anim_name)。
    """
    if beat not in SUPPORTED_BEATS:
        raise ValueError("beat 須為 {} 之一,收到 {!r}".format(SUPPORTED_BEATS, beat))
    G, ct = _wire_repo_tools()
    if not parts:
        raise ValueError("parts 不可為空")

    # "pop" = cascade 的單件運動基元 → 以 cascade 預設(pop)波生成。
    beat_name = "cascade" if beat == "pop" else beat

    skel = _assemble_skeleton(parts)
    storyboard = {"beats": [{"beat": beat_name, "desc": "B2 gen_lib 大獎 {}".format(beat),
                             "parts": [{"part": p["part"], "role": p["role"], "action": "主秀"}
                                       for p in parts]}]}
    gen_skel = {"skeleton": skel["skeleton"], "bones": skel["bones"]}
    kwargs = {}
    if beat_name == "cascade":
        kwargs.update(cascade_dir=cascade_dir, cascade_reveal=cascade_reveal,
                      cascade_wobble=cascade_wobble)
    anims = G.build_animations(gen_skel, storyboard, **kwargs)
    skel["animations"] = anims

    if apply_g1:
        for a in skel["animations"].values():
            ct.strip_last_frame_curves(a)
    return skel, beat_name


def generate_idle(parts, apply_g1=True):
    """產一支 idle/Loop beat(body 呼吸、**limb 擺盪 rotate**、head 點頭、特效 alpha 脈動),
    回傳 (skeleton_dict, "Loop")。**已過 G1**。

    與大獎 beat(`generate_bigwin`)的關鍵差異:大獎 cascade 對所有件一視同仁(scale/shear 脈衝),
    idle Loop 依 **role** 給不同通道——**limb 走 rotate 通道** → 這正是 **繞關節 pivot 變換**
    (`pivot_axis.apply_joint_pivots`,MERGE_PLAN Phase B3)的典型來源:手臂該繞肩轉、頭該繞頸轉,
    非 rig 下 bone 落件中心,須 keyframe 級補償 Δ=(M−I)(O−P) 才物理。

    parts    : [{"part","role","action"} ...];**role 須用英文** body/head/limb/特效
               (大獎 beat 不分 role,故 DEMO_PARTS 用中文 role;idle 依 role → 用 IDLE_DEMO_PARTS)。
    apply_g1 : True(預設)→ 輸出前拔末鍵 curve(地雷 #12)。
    """
    G, ct = _wire_repo_tools()
    if not parts:
        raise ValueError("parts 不可為空")
    skel = _assemble_skeleton(parts)
    storyboard = {"beats": [{"beat": "Loop", "desc": "B3 gen_lib idle",
                             "parts": [{"part": p["part"], "role": p["role"], "action": "主秀"}
                                       for p in parts]}]}
    gen_skel = {"skeleton": skel["skeleton"], "bones": skel["bones"]}
    anims = G.build_animations(gen_skel, storyboard)
    skel["animations"] = anims
    if apply_g1:
        for a in skel["animations"].values():
            ct.strip_last_frame_curves(a)
    return skel, "Loop"


def write_bigwin(parts, out_path, beat="cascade", **opts):
    """generate_bigwin + 寫檔(UTF-8, indent=1)。回傳 (out_path, anim_name)。"""
    skel, aname = generate_bigwin(parts, beat=beat, **opts)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)
    return out_path, aname


# --------------------------------------------------------------------- 自檢(不寫檔)
def _self_test():
    """生成 cascade/pop/wobble/twist 各一支,回報 bone/slot 數與是否可過 G1(本地快檢,
    完整 validator_v1 雙真值驗收見 tools/analyzer/validate_b2_genlib.py)。"""
    ok = True
    for b in SUPPORTED_BEATS:
        skel, aname = generate_bigwin(DEMO_PARTS, beat=b)
        anim = skel["animations"][aname]
        nb = len(anim.get("bones", {}))
        ns = len(anim.get("slots", {}))
        # 快檢:生成後無末鍵 curve(G1 已套)
        bad = 0
        for sec in ("bones", "slots"):
            for tls in anim.get(sec, {}).values():
                for fr in tls.values():
                    if isinstance(fr, list) and fr and isinstance(fr[-1], dict) \
                       and any(k in fr[-1] for k in ("curve", "c2", "c3", "c4")):
                        bad += 1
        good = nb >= 2 and bad == 0
        ok = ok and good
        print("  {:8s} anim={:10s} bones={} slots={} lastframe_curves={} -> {}".format(
            b, aname, nb, ns, bad, "OK" if good else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="gen_lib 大獎節拍生成入口(B2)")
    ap.add_argument("--beat", default="cascade", choices=SUPPORTED_BEATS)
    ap.add_argument("--out", help="輸出 skeleton.json 路徑")
    ap.add_argument("--psd", help="(過渡期)分層 PSD,反推拆件清單")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--cascade-dir", default=None, help="cascade 波方向:lr/rl/co/oc/角度/geo:src")
    ap.add_argument("--cascade-reveal", action="store_true")
    ap.add_argument("--cascade-wobble", action="store_true")
    ap.add_argument("--no-g1", action="store_true", help="不拔末鍵 curve(除錯/負對照用)")
    ap.add_argument("--self-test", action="store_true", help="跑內建 4 beat 自檢,不寫檔")
    a = ap.parse_args()

    if a.self_test:
        ok = _self_test()
        print("SELF-TEST:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)

    parts = parts_from_psd(a.psd, a.genre) if a.psd else DEMO_PARTS
    cdir = a.cascade_dir
    if cdir is not None and cdir.startswith("geo:"):
        cdir = ("geo", cdir[4:])
    if not a.out:
        ap.error("需要 --out(或用 --self-test)")
    out, aname = write_bigwin(parts, a.out, beat=a.beat, cascade_dir=cdir,
                              cascade_reveal=a.cascade_reveal, cascade_wobble=a.cascade_wobble,
                              apply_g1=not a.no_g1)
    print(json.dumps({"out": out, "anim": aname, "beat": a.beat, "parts": len(parts),
                      "g1_applied": not a.no_g1}, ensure_ascii=False))


if __name__ == "__main__":
    main()
