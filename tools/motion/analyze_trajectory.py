#!/usr/bin/env python3
"""軌跡分析器:Spine 動畫 → 目標部位的運動軌跡包(traj.json)。

對應 spine-motion-skill 標準流程的第 1–4 步:
  1 結構盤點(父鏈 / setup / 通道 / slot-attachment)
  2 世界座標取樣(主體 + 目標,每幀多點)
  3 分離「剛體跟隨 rigid」與「自身位移 own = actual − rigid」
  4 量化(極值幀、峰對峰幅度、Pearson、循環互相關最佳滯後)

產物 `traj.json` 是 `spine_trajectory_editor.html` 的輸入,也是
`apply_motion_spec.py` 的比對基準。編輯器另可直接讀原始 skeleton JSON
(頁內同一套演算法),本 CLI 供排程 / CI / skill 流程使用。

用法:
  python3 tools/motion/analyze_trajectory.py --json assets/main_draw.json \
      --anim main_draw_loop --bone face --body main --out out/traj_face.json
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spine_world as W  # noqa: E402

SCHEMA = "spine-motion-trajectory/1"


# ---------- 結構盤點 ----------
def slots_of_bone(data, bone):
    return [s["name"] for s in data.get("slots", []) if s.get("bone") == bone]


def auto_point(data, bone):
    """挑一個能反映『這根骨骼帶著什麼在動』的追蹤點(該骨骼 slot 的 attachment 位移)。
    骨骼原點對 rotate-only 的骨骼完全不動,追原點會把跟隨運動誤讀成 0。"""
    names = slots_of_bone(data, bone)
    best = None
    skins = data.get("skins") or {}
    # 3.8 有兩種 skins 格式:{name: {slot: {...}}} 與 [{"name":..,"attachments":{slot:{...}}}]
    skin_maps = list(skins.values()) if isinstance(skins, dict) else [(sk.get("attachments") or {}) for sk in skins]
    for skin in skin_maps:
        for sname in names:
            for att in (skin.get(sname) or {}).values():
                x, y = float(att.get("x", 0.0)), float(att.get("y", 0.0))
                w, h = float(att.get("width", 0.0)), float(att.get("height", 0.0))
                area = max(w * h, 1.0)
                if best is None or area > best[0]:
                    best = (area, x, y, sname)
    if best:
        return (best[1], best[2], f"slot '{best[3]}' attachment 中心")
    return (0.0, 0.0, "骨骼原點(該骨骼無 attachment)")


def _curve_of(key):
    """Spine 3.8 緊湊 curve 散鍵 → spec 的 curve 欄位(dict / 'stepped' / None=linear)。"""
    c = key.get("curve")
    if c is None:
        return None
    if c == "stepped":
        return "stepped"
    return {"curve": float(c), "c2": float(key.get("c2", 0.0)),
            "c3": float(key.get("c3", 1.0)), "c4": float(key.get("c4", 1.0))}


def channels_of(anim, bone):
    return sorted(((anim.get("bones") or {}).get(bone) or {}).keys())


# ---------- 主流程 ----------
def analyze(data, anim_name, bone, body_bone, fps=30.0, spf=4, point=None, src_path=None):
    if anim_name not in data.get("animations", {}):
        raise SystemExit(f"animation '{anim_name}' 不存在;可選:{list(data['animations'])}")
    sk = W.Skel(data)
    for b in (bone, body_bone):
        if b not in sk.bones:
            raise SystemExit(f"bone '{b}' 不存在")
    anim = data["animations"][anim_name]
    dur = W.duration(anim)
    if dur <= 0:
        raise SystemExit(f"animation '{anim_name}' 總長為 0,無法分析軌跡")
    nf = dur * fps
    n = max(1, int(round(nf * spf)))
    ts = [dur * i / n for i in range(n + 1)]
    fr = [t * fps for t in ts]

    if point is None:
        px, py, pdesc = auto_point(data, bone)
    else:
        px, py = point
        pdesc = f"指定點 ({px:g},{py:g})"

    body = [sk.world_pos(body_bone, anim, t) for t in ts]
    split = [sk.own_split(bone, anim, t, px, py) for t in ts]
    rigid = [p[0] for p in split]
    rot_own = [p[1] for p in split]
    trans_own = [p[2] for p in split]
    actual = [p[3] for p in split]
    own = [(a[0] - r[0], a[1] - r[1]) for a, r in zip(actual, rigid)]

    def c(s_, i):
        return [round(p[i], 4) for p in s_]

    def pp(v):
        return round(max(v) - min(v), 3) if v else 0.0

    def dm(v):
        m = sum(v) / len(v)
        return [x - m for x in v]

    rigidX, rigidY = c(rigid, 0), c(rigid, 1)
    ownX, ownY = c(own, 0), c(own, 1)
    lagcX, rcX, lagsX, rsX = W.best_lag(dm(rigidX), ownX, spf)
    lagcY, rcY, lagsY, rsY = W.best_lag(dm(rigidY), ownY, spf)

    # 節拍:主體骨骼的 keyframe 幀 + 剛體掛點的世界極值幀
    beats = sorted({round(t * fps, 3) for t in W.key_times(anim, body_bone)})
    ext_rigid_y = W.extrema(fr, rigidY)
    ext_rigid_x = W.extrema(fr, rigidX)

    # 目前目標骨骼的 keyframe(供編輯器當初始編輯點)
    tkeys = {}
    for ch, keys in (((anim.get("bones") or {}).get(bone)) or {}).items():
        tkeys[ch] = [dict(k, time=float(k.get("time", 0.0)), frame=round(float(k.get("time", 0.0)) * fps, 4))
                     for k in keys]

    # 可編輯曲線 = **translate 造成的自身位移**(世界座標)。
    # 用 transOwn 而非 own 總量:只有這一塊能無損寫回 translate 關鍵值;
    # rotate 造成的 rotOwn 另走 rotate 通道,混在一起會在 round-trip 重複計入。
    edit_keys = []
    src_keys = tkeys.get("translate")
    frames_for_edit = [k["frame"] for k in src_keys] if src_keys else list(beats)
    for i, f in enumerate(frames_for_edit):
        t = min(max(f / fps, 0.0), dur)
        _, _, tr, _ = sk.own_split(bone, anim, t, px, py)
        e = {"frame": round(f, 4), "wx": round(tr[0], 4), "wy": round(tr[1], 4)}
        cv = _curve_of(src_keys[i]) if src_keys else None
        if cv is not None:
            e["curve"] = cv
        edit_keys.append(e)

    # 可編輯性:延後/幅度旋鈕作用在「被寫成關鍵幀的自身運動」上。
    # 只有 1 個 translate key = 靜態擺位(常見:美術用動畫通道擺件),沒有曲線可調。
    kx = [k["wx"] for k in edit_keys]
    ky = [k["wy"] for k in edit_keys]
    osc = max(max(kx) - min(kx), max(ky) - min(ky)) if edit_keys else 0.0
    editable = {"keys": len(edit_keys), "oscillationPP": round(osc, 4),
                "staticOffset": [round(sum(kx) / len(kx), 4) if kx else 0.0,
                                 round(sum(ky) / len(ky), 4) if ky else 0.0],
                "usable": len(edit_keys) >= 2 and osc > 1e-6}

    warns = list(sk.warnings)
    if not editable["usable"]:
        warns.append(
            f"目標 '{bone}' 的 translate 只有 {len(edit_keys)} 個關鍵幀且振幅 {osc:.3g}px"
            "(＝靜態擺位,不是動起來的曲線):延後/幅度旋鈕對它沒有作用。"
            "要做跟隨動態,先在編輯器裡沿主體節拍加關鍵幀。")
    if pp(ownX) < 1e-6 and pp(ownY) < 1e-6:
        warns.append(f"目標 '{bone}' 在 '{anim_name}' 沒有可量的自身位移(峰對峰 ≈ 0):"
                     "它可能只被父體帶著走,或該通道全為 0。可改追蹤點(--point)或換目標骨骼。")
    if pp(rigidX) < 1e-6 and pp(rigidY) < 1e-6:
        warns.append(f"主體 '{body_bone}' 沒有帶動目標(剛體跟隨峰對峰 ≈ 0):節拍無從對齊,先確認主體骨骼選對。")

    out = {
        "schema": SCHEMA,
        "source": {
            "json": os.path.relpath(src_path) if src_path else None,
            "sha1": hashlib.sha1(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12],
            "animation": anim_name,
            "fps": fps,
            "duration": round(dur, 6),
            "frames": round(nf, 4),
            "samplesPerFrame": spf,
        },
        "target": {
            "bone": bone,
            "point": [px, py],
            "pointDesc": pdesc,
            "parentChain": sk.parent_chain(bone),
            "setup": {k: sk.bones[bone].get(k) for k in ("x", "y", "rotation", "scaleX", "scaleY") if k in sk.bones[bone]},
            "channels": channels_of(anim, bone),
            "slots": slots_of_bone(data, bone),
            "keys": tkeys,
        },
        "body": {
            "bone": body_bone,
            "parentChain": sk.parent_chain(body_bone),
            "channels": channels_of(anim, body_bone),
            "beats": beats,
        },
        "samples": {
            "frame": [round(f, 4) for f in fr],
            "bodyX": c(body, 0), "bodyY": c(body, 1),
            "rigidX": rigidX, "rigidY": rigidY,
            "actualX": c(actual, 0), "actualY": c(actual, 1),
            "ownX": ownX, "ownY": ownY,
            "rotOwnX": c(rot_own, 0), "rotOwnY": c(rot_own, 1),
            "transOwnX": c(trans_own, 0), "transOwnY": c(trans_own, 1),
        },
        "metrics": {
            "amplitude": {
                "bodyX": pp(c(body, 0)), "bodyY": pp(c(body, 1)),
                "rigidX": pp(rigidX), "rigidY": pp(rigidY),
                "ownX": pp(ownX), "ownY": pp(ownY),
                "rotOwnX": pp(c(rot_own, 0)), "rotOwnY": pp(c(rot_own, 1)),
                "transOwnX": pp(c(trans_own, 0)), "transOwnY": pp(c(trans_own, 1)),
                "actualX": pp(c(actual, 0)), "actualY": pp(c(actual, 1)),
            },
            "corrOwnVsRigid": {"x": round(W.pearson(dm(rigidX), ownX), 4),
                               "y": round(W.pearson(dm(rigidY), ownY), 4)},
            "bestLag": {
                "x": {"complementary": lagcX, "r": round(rcX, 4), "sync": lagsX, "rSync": round(rsX, 4)},
                "y": {"complementary": lagcY, "r": round(rcY, 4), "sync": lagsY, "rSync": round(rsY, 4)},
            },
            "extremaRigidY": [[round(f, 2), round(v, 3), k] for f, v, k in ext_rigid_y],
            "extremaRigidX": [[round(f, 2), round(v, 3), k] for f, v, k in ext_rigid_x],
            "extremaOwnY": [[round(f, 2), round(v, 3), k] for f, v, k in W.extrema(fr, ownY)],
            "extremaOwnX": [[round(f, 2), round(v, 3), k] for f, v, k in W.extrema(fr, ownX)],
        },
        "editable": editable,
        "edit": {
            "channel": "translate",
            "space": "world",
            "keys": edit_keys,
            "lag": 0.0,
            "scale": 1.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
        },
        "warnings": warns,
    }
    return out


def summarize(tj):
    s, m = tj["source"], tj["metrics"]
    L = []
    L.append(f"# {s['animation']}  {s['duration']}s = {s['frames']:g} 幀 @{s['fps']:g}fps")
    L.append(f"目標 {tj['target']['bone']}  父鏈 {' → '.join(tj['target']['parentChain'])}  通道 {tj['target']['channels'] or '(無)'}")
    L.append(f"追蹤點 {tj['target']['pointDesc']} = {tj['target']['point']}")
    L.append(f"主體 {tj['body']['bone']}  節拍(幀) {tj['body']['beats']}")
    a = m["amplitude"]
    L.append(f"峰對峰幅度(px)  剛體跟隨 X {a['rigidX']} / Y {a['rigidY']}   自身位移 X {a['ownX']} / Y {a['ownY']}   實際 X {a['actualX']} / Y {a['actualY']}")
    L.append(f"  自身位移拆解:translate 造成 X {a['transOwnX']} / Y {a['transOwnY']}   rotate 造成 X {a['rotOwnX']} / Y {a['rotOwnY']}")
    L.append(f"own vs 主體 相關  X {m['corrOwnVsRigid']['x']:+.3f}   Y {m['corrOwnVsRigid']['y']:+.3f}   (+1 同步放大 / 0 正交 / −1 互補)")
    by = m["bestLag"]["y"]
    L.append(f"互相關最佳滯後 Y:互補 {by['complementary']:g} 幀 (r={by['r']:+.2f})、同步 {by['sync']:g} 幀 (r={by['rSync']:+.2f})")
    L.append(f"剛體 Y 極值 {[(f, k) for f, v, k in m['extremaRigidY']]}")
    L.append(f"自身 Y 極值 {[(f, k) for f, v, k in m['extremaOwnY']]}")
    e = tj["editable"]
    L.append(f"可編輯性:translate 關鍵幀 {e['keys']} 個、振幅 {e['oscillationPP']}px、靜態擺位 {e['staticOffset']}"
             f" → {'可用旋鈕調整' if e['usable'] else '**無曲線可調(需先加關鍵幀)**'}")
    if tj["warnings"]:
        L.append("警告:" + "; ".join(tj["warnings"]))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Spine 動畫目標部位軌跡分析(世界座標)")
    ap.add_argument("--json", required=True, help="Spine 3.8 skeleton JSON")
    ap.add_argument("--anim", required=True)
    ap.add_argument("--bone", required=True, help="目標(次級動態)骨骼")
    ap.add_argument("--body", required=True, help="主體骨骼(節拍來源)")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--spf", type=int, default=4, help="每幀取樣點數")
    ap.add_argument("--point", default="auto", help="追蹤點 local 座標 'x,y' 或 auto")
    ap.add_argument("--out", help="輸出 traj.json 路徑")
    ap.add_argument("--csv", help="另存每幀對照表 CSV")
    a = ap.parse_args(argv)

    data = json.load(open(a.json, encoding="utf-8"))
    pt = None if a.point == "auto" else tuple(float(v) for v in a.point.split(","))
    tj = analyze(data, a.anim, a.bone, a.body, a.fps, a.spf, pt, a.json)
    print(summarize(tj))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(tj, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print(f"\n已寫出 {a.out}")
    if a.csv:
        write_csv(tj, a.csv)
        print(f"已寫出 {a.csv}")
    return tj


def write_csv(tj, path):
    """skill 規範的『07_對照表.csv』:frame, body_X, own_X, actual_X, body_Y, own_Y, actual_Y(每幀一列)。"""
    s = tj["samples"]
    spf = tj["source"]["samplesPerFrame"]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("frame,body_X,own_X,actual_X,body_Y,own_Y,actual_Y\n")
        for i in range(0, len(s["frame"]), spf):
            f.write(f"{s['frame'][i]:g},{s['rigidX'][i]:.3f},{s['ownX'][i]:.3f},{s['actualX'][i]:.3f},"
                    f"{s['rigidY'][i]:.3f},{s['ownY'][i]:.3f},{s['actualY'][i]:.3f}\n")


if __name__ == "__main__":
    main()
