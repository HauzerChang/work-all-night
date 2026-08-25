#!/usr/bin/env python3
"""分鏡 → 動畫 keyframe(候選 0d)— 把 analyzer #3 storyboard 的 Loop(待機呼吸)beat
確定性地轉成 Spine 3.8 `animations.loop` timeline,讓 build_spine 產出的靜態素材「會動」。

設計原則(與 RULES 一致:確定性演算法 + 可自我量化的閘,不用 ML 學美術決定):
  角色 → 運動原語(role → motion primitive),全部參數化、可被 validate_animation 反算量測:
    body   : 呼吸 = translate.y 升餘弦起伏 + 微幅 scale 同步(胸口起伏)
    head   : 微點頭 = rotate 正弦(小角度)
    limb   : 末梢微盪 = rotate 正弦(小角度),**各肢體相位錯開**(phase offset)
    effect : 微脈動 = slot.color alpha 升餘弦循環

keyframe 取樣策略:每個週期以 K 個等距 keyframe 直接取樣解析函數,線性內插(Spine 無 curve 鍵=linear)。
  → 產生器與驗證器用同一種內插,保證「閘驗到的就是 JSON 裡的東西」(誠實)。
  → bezier 緩動屬後續精修;dense-linear(K=12)對 proposal 級自動待機足夠平滑。
loop 無縫:每條 timeline 第 0 幀 == 第 period 幀(週期函數在 t=0 與 t=T 同值)。

座標/命名約定沿用 build_spine:件 <name> → bone `b_<safe(name)>`、slot `<safe(name)>`。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _samples(fn, period, K):
    """在 [0,period] 等距取 K+1 個 keyframe(含閉環尾幀=首幀值),回傳 [(time,value),...]。"""
    out = []
    for k in range(K + 1):
        t = period * k / K
        # 尾幀強制等於首幀值,消除浮點誤差確保無縫 loop
        val = fn(0.0) if k == K else fn(t)
        out.append((round(t, 4), val))
    return out


def _kf_scalar(samples, key, zero=0.0):
    """把 [(t,v)] 轉成 Spine scalar timeline(rotate: key='angle';translate 單軸另處理)。"""
    kfs = []
    for (t, v) in samples:
        kf = {} if t == 0 else {"time": t}
        kf[key] = round(v, 3)
        kfs.append(kf)
    return kfs


def build_loop(skeleton, storyboard, period=2.0, K=12,
               body_amp=None, head_deg=3.0, limb_deg=4.0,
               scale_amp=0.012, effect_alpha_min=0.75):
    """由 storyboard 的 Loop beat 生成 animations.loop dict。回傳 (anim_dict, report)。"""
    H = skeleton["skeleton"].get("height", 0) or 0
    if body_amp is None:
        body_amp = max(3.0, min(12.0, 0.015 * H))   # 依畫布高自動定呼吸幅度
    bone_names = {b["name"] for b in skeleton["bones"]}
    slot_by_name = {s["name"]: s for s in skeleton["slots"]}

    loop_beat = None
    for b in storyboard["beats"]:
        if b["beat"].lower() in ("loop", "idle"):
            loop_beat = b
            break
    if loop_beat is None:
        raise ValueError("storyboard 無 Loop/idle beat")

    bones_tl, slots_tl = {}, {}
    report = {"period": period, "body": [], "head": [], "limb": [], "effect": [], "skipped": []}

    # 先數肢體數量以分配相位
    limbs = [r for r in loop_beat["parts"]
             if r["role"] not in ("特效",) and _role_en(r["role"]) == "limb"]
    limb_index = {id(r): i for i, r in enumerate(limbs)}
    n_limb = max(1, len(limbs))

    for r in loop_beat["parts"]:
        part = r["part"]
        nm = safe(part)
        bone = f"b_{nm}"
        role = _role_en(r["role"])

        if role == "effect":
            slot = slot_by_name.get(nm)
            if slot is None:
                report["skipped"].append((part, "no-slot"))
                continue
            amp = (1.0 - effect_alpha_min)
            fn = lambda t, amp=amp: 1.0 - amp * (1.0 - math.cos(2 * math.pi * t / period)) / 2.0
            sm = _samples(fn, period, K)
            color = []
            for (t, a) in sm:
                aa = max(0, min(255, int(round(a * 255))))
                kf = {} if t == 0 else {"time": t}
                kf["color"] = "ffffff%02x" % aa
                color.append(kf)
            slots_tl[nm] = {"color": color}
            report["effect"].append({"slot": nm, "alpha_range": [round(min(a for _, a in sm), 3),
                                                                  round(max(a for _, a in sm), 3)]})
            continue

        if bone not in bone_names:
            report["skipped"].append((part, "no-bone"))
            continue

        if role == "body":
            # 呼吸:translate.y 升餘弦(0→+A→0) + scale 同步微幅
            fy = lambda t: body_amp * (1.0 - math.cos(2 * math.pi * t / period)) / 2.0
            sy = _samples(fy, period, K)
            translate = []
            for (t, v) in sy:
                kf = {} if t == 0 else {"time": t}
                kf["y"] = round(v, 3)
                translate.append(kf)
            fs = lambda t: 1.0 + scale_amp * (1.0 - math.cos(2 * math.pi * t / period)) / 2.0
            ss = _samples(fs, period, K)
            scale = []
            for (t, v) in ss:
                kf = {} if t == 0 else {"time": t}
                kf["x"] = round(v, 4); kf["y"] = round(v, 4)
                scale.append(kf)
            bones_tl[bone] = {"translate": translate, "scale": scale}
            report["body"].append({"bone": bone, "ty_range": [round(min(v for _, v in sy), 3),
                                                               round(max(v for _, v in sy), 3)]})

        elif role == "head":
            fr = lambda t: head_deg * math.sin(2 * math.pi * t / period)
            sm = _samples(fr, period, K)
            bones_tl[bone] = {"rotate": _kf_scalar(sm, "angle")}
            report["head"].append({"bone": bone, "deg_range": [round(min(v for _, v in sm), 3),
                                                               round(max(v for _, v in sm), 3)]})

        elif role == "limb":
            i = limb_index[id(r)]
            phi = i / n_limb           # 相位錯開:0, 1/n, 2/n ...
            fr = lambda t, phi=phi: limb_deg * math.sin(2 * math.pi * (t / period + phi))
            sm = _samples(fr, period, K)
            bones_tl[bone] = {"rotate": _kf_scalar(sm, "angle")}
            report["limb"].append({"bone": bone, "phase": round(phi, 3),
                                   "deg_range": [round(min(v for _, v in sm), 3),
                                                 round(max(v for _, v in sm), 3)]})

    anim = {}
    if slots_tl:
        anim["slots"] = slots_tl
    if bones_tl:
        anim["bones"] = bones_tl
    return anim, report


def _role_en(role):
    """storyboard role 欄位('特效'/'body'/'head'/'limb')→ 英文原語。"""
    if role == "特效":
        return "effect"
    return role


def annotate(skeleton_path, spec_path=None, psd=None, genre="slot_bigwin",
             out_path=None, **kw):
    """讀 skeleton.json,由 spec(或現算)取 storyboard,注入 animations.loop,寫回。"""
    sk = json.load(open(skeleton_path, encoding="utf-8"))
    if spec_path:
        spec = json.load(open(spec_path, encoding="utf-8"))
    else:
        from analyze_target import analyze
        spec = analyze(psd, genre)
    storyboard = spec["3_motion_storyboard"]
    anim, report = build_loop(sk, storyboard, **kw)
    sk.setdefault("animations", {})["loop"] = anim
    out_path = out_path or skeleton_path
    json.dump(sk, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"out": out_path, "report": report,
            "bones_animated": len(anim.get("bones", {})),
            "slots_animated": len(anim.get("slots", {}))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", help="build_spine 產的 skeleton.json")
    ap.add_argument("--psd", help="原 PSD(用於現算 storyboard;或用 --spec)")
    ap.add_argument("--spec", help="analyze_target 存好的 spec json")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--period", type=float, default=2.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = annotate(a.skeleton, spec_path=a.spec, psd=a.psd, genre=a.genre,
                 out_path=a.out, period=a.period)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
