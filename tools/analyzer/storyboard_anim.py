#!/usr/bin/env python3
"""S1 #3d — 分鏡 → 動畫 keyframe(idle/loop 呼吸循環)。

把 build_spine 產出的靜態素材(bones/slots)配上 **一支無縫循環的待機/呼吸動畫**,
讓「目標圖 → Spine 素材」的產物真的會動。動作由**結構角色**驅動(對齊 storyboard 先驗):

  body  : 呼吸 = scale 微幅起伏(±breath)+ 胸口 y 微移        (平滑 cos ease,起訖回原)
  head  : 微點頭/傾 = rotate 小幅正弦                           (相位 0)
  limb  : 末梢小幅擺盪 = rotate 正弦,**逐件相位錯開**(相位 = i·2π/n_limb)
  effect: 脈動 = slot color alpha 微幅循環(base→dim→base)

設計原則(可被 validate_anim.py 量化):
  1) 無縫循環:每條 timeline 首幀(t=0)== 末幀(t=T)。以「完整正弦/餘弦週期」取樣達成
     (相位差整 2π → 端點相等),即使有相位錯開仍閉合。
  2) 幅度有界:scale∈[1-breath,1+breath]、rotate∈[-A,A]、translate 佔畫布極小比例
     → 不會飛出畫面 / 不會誇張變形。
  3) 相位錯開:limb 峰值時間依序不同(相位錯開),避免全身同步「紙板感」。
  4) 純線性內插(不寫 curve 鍵 = Spine 3.8 預設 linear);對正弦以 K 段過取樣,足夠平滑
     且讓端點值 = 內插極值,range 可由 keyframe 值直接判定(不需重算 bezier)。

只生 idle/loop 這一支「循環」節拍(最乾淨、可用 loop-closure 自驗);In/Out 屬後續。
"""
import math

sys_beat_alias = {"loop", "idle", "Loop"}  # 視為「循環呼吸」的節拍 key


def _cos_ease(k, K):
    """0→1→0 的平滑起伏(半餘弦),k=0..K;端點 (0,K) 皆為 0。"""
    return 0.5 - 0.5 * math.cos(2 * math.pi * k / K)


def _sin_cycle(k, K, phase):
    """完整正弦週期,k=0..K;k=0 與 k=K 相位差 2π → 值相等(閉合)。"""
    return math.sin(2 * math.pi * k / K + phase)


def _fmt(v, nd=3):
    return round(float(v), nd)


def _hex_alpha(a):
    """base 白 + alpha(0..1)→ 'ffffff{aa}'。"""
    aa = max(0, min(255, int(round(a * 255))))
    return "ffffff%02x" % aa


def pick_loop_beat(spec):
    """從 storyboard 選出『循環』節拍 key;優先 idle,其次 loop/Loop。"""
    beats = [b["beat"] for b in spec["3_motion_storyboard"]["beats"]]
    for want in ("idle", "loop", "Loop"):
        if want in beats:
            return want
    # 泛用回退:任何含 idle/loop 子字串者
    for b in beats:
        if b.lower() in ("idle", "loop"):
            return b
    return None


def build_loop_animation(spec, safe, T=1.5, K=8,
                         breath=0.03, head_deg=2.0, limb_deg=4.0,
                         body_dy_frac=0.01, eff_alpha_lo=0.55):
    """回傳 (anim_name, anim_dict)。

    spec   : analyze_target 的規格(需 2_effects 內含 struct_role/is_effect、canvas)。
    safe   : build_spine.safe(把件名轉成 bone/slot 安全名)的同一函式。
    T      : 循環總長(秒)。K:每週期取樣段數(keyframe = K+1,首末閉合)。
    """
    beat = pick_loop_beat(spec)
    src = spec["source"].rsplit(".", 1)[0]
    name = f"{src}_{beat}" if beat else f"{src}_idle"
    W, H = spec["canvas"]
    body_dy = body_dy_frac * H

    # 收集角色(effect 優先於 struct_role)
    parts = []
    for e in spec["2_effects"]:
        role = "effect" if e["is_effect"] else (e.get("struct_role") or "limb")
        parts.append((e["name"], role))
    limbs = [p for p in parts if p[1] == "limb"]

    bones, slots = {}, {}
    times = [round(k * T / K, 4) for k in range(K + 1)]

    def key(t, **kv):
        d = {} if t == 0 else {"time": t}
        d.update(kv)
        return d

    limb_i = 0
    for (pname, role) in parts:
        b = f"b_{safe(pname)}"
        s = safe(pname)
        if role == "body":
            scale, trans = [], []
            for k in range(K + 1):
                e = _cos_ease(k, K)            # 0→1→0
                f = 1.0 + breath * e
                scale.append(key(times[k], x=_fmt(f), y=_fmt(f)))
                trans.append(key(times[k], x=0.0, y=_fmt(body_dy * e)))
            bones[b] = {"scale": scale, "translate": trans}
        elif role == "head":
            rot = [key(times[k], angle=_fmt(head_deg * _sin_cycle(k, K, 0.0), 2))
                   for k in range(K + 1)]
            bones[b] = {"rotate": rot}
        elif role == "limb":
            phase = (2 * math.pi * limb_i / max(len(limbs), 1))   # 相位錯開
            limb_i += 1
            rot = [key(times[k], angle=_fmt(limb_deg * _sin_cycle(k, K, phase), 2))
                   for k in range(K + 1)]
            bones[b] = {"rotate": rot}
        else:  # effect:alpha 脈動(base 全亮 → dim → 全亮)
            col = []
            for k in range(K + 1):
                e = _cos_ease(k, K)                        # 0→1→0
                a = 1.0 - (1.0 - eff_alpha_lo) * e         # 1 → lo → 1
                col.append(key(times[k], color=_hex_alpha(a)))
            slots[s] = {"color": col}

    anim = {}
    if bones:
        anim["bones"] = bones
    if slots:
        anim["slots"] = slots
    meta = {"name": name, "beat": beat, "duration": T, "K": K,
            "n_body": sum(1 for _, r in parts if r == "body"),
            "n_head": sum(1 for _, r in parts if r == "head"),
            "n_limb": len(limbs),
            "n_effect": sum(1 for _, r in parts if r == "effect")}
    return name, anim, meta


if __name__ == "__main__":
    import argparse, json, os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from analyze_target import analyze
    from build_spine import safe
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--genre", default="slot_bigwin")
    a = ap.parse_args()
    spec = analyze(a.psd, a.genre)
    nm, anim, meta = build_loop_animation(spec, safe)
    print(json.dumps({"meta": meta, "animation": {nm: anim}},
                     ensure_ascii=False, indent=1))
