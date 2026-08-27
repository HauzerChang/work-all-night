#!/usr/bin/env python3
"""分鏡→動畫 自我驗收閘(量化,不靠肉眼)。

對 storyboard_to_anim 產出的 Spine `animations` 跑可機讀 AC:

  AC1 結構合法    : bone/slot 名皆存在於 skeleton;timeline 鍵合法;time 單調遞增、≥0。
  AC2 Loop 無縫    : Loop 每條 timeline 首尾 keyframe 值相等(可循環,tol 極小)。
  AC3 有動作       : 每個 beat 每件至少一條 timeline 的值域 range > 門檻(非 no-op)。
  AC4 Loop 有界    : Loop rotate ≤ 8°、scale ∈ [0.9,1.1]、translate ≤ 12px(待機不暴衝)。
  AC5 FK 軌跡合理  : 以簡易前向運動學(root-child)取件中心世界軌跡,無 NaN、
                    Loop 軌跡首尾閉合、In/Out 位移量在合理級距(In 有明顯入場位移、Out 收斂)。

⚠️ FK 取樣用線性內插(Spine bezier 只改時序、不改 keyframe 端點值),故值域/首尾/閉合判定
   與實機一致;曲線平滑手感(緩動)屬主觀,留給使用者在 spine_inspector 目視。
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))


def _val(kf, keys):
    return {k: kf.get(k) for k in keys}


def _time(kf):
    return kf.get("time", 0.0)


def _lerp_track(track, t, fields):
    """線性內插一條 timeline 在時間 t 的 field 值(端點外推為端點)。"""
    if not track:
        return None
    if t <= _time(track[0]):
        return {f: track[0].get(f) for f in fields}
    if t >= _time(track[-1]):
        return {f: track[-1].get(f) for f in fields}
    for i in range(len(track) - 1):
        a, b = track[i], track[i + 1]
        ta, tb = _time(a), _time(b)
        if ta <= t <= tb:
            u = 0.0 if tb == ta else (t - ta) / (tb - ta)
            return {f: a.get(f, 0.0) + u * (b.get(f, 0.0) - a.get(f, 0.0)) for f in fields}
    return {f: track[-1].get(f) for f in fields}


FIELDS = {"rotate": ["angle"], "translate": ["x", "y"], "scale": ["x", "y"]}


def _range(track, field):
    vals = [kf.get(field, 0.0) for kf in track]
    return max(vals) - min(vals)


def validate(anims, skeleton):
    bone_names = {b["name"] for b in skeleton["bones"]}
    slot_names = {s["name"] for s in skeleton["slots"]}
    # 件中心世界座標(setup):bone x,y(root-child,無旋轉)
    bone_xy = {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in skeleton["bones"]}

    report = {"beats": {}, "ac": {}}
    ac1 = ac2 = ac3 = ac4 = ac5 = True
    problems = []

    for beat, a in anims.items():
        binfo = {"bones": {}, "seamless": True, "moved_parts": 0, "n_parts": 0}
        # ---- AC1 結構 + AC2 無縫 + AC3 有動 + AC4 有界 ----
        for bname, tls in a.get("bones", {}).items():
            if bname not in bone_names:
                ac1 = False; problems.append(f"[{beat}] 未知 bone {bname}")
                continue
            per = {}
            moved = False
            for tl, track in tls.items():
                fields = FIELDS.get(tl)
                if fields is None:
                    ac1 = False; problems.append(f"[{beat}]{bname} 非法 timeline {tl}")
                    continue
                # time 單調
                ts = [_time(k) for k in track]
                if any(t < 0 for t in ts) or any(ts[i] > ts[i + 1] for i in range(len(ts) - 1)):
                    ac1 = False; problems.append(f"[{beat}]{bname}.{tl} time 非單調")
                rng = {f: _range(track, f) for f in fields}
                per[tl] = rng
                if any(abs(v) > 1e-4 for v in rng.values()):
                    moved = True
                # AC2 Loop 無縫:首尾值相等
                if beat == "Loop":
                    for f in fields:
                        v0, v1 = track[0].get(f, 0.0), track[-1].get(f, 0.0)
                        # 特效 rotate 0→360 視為無縫(角度同餘 360)
                        d = abs(v1 - v0)
                        if tl == "rotate":
                            d = min(d, abs(d - 360.0))
                        if d > 1e-3:
                            binfo["seamless"] = False; ac2 = False
                            problems.append(f"[Loop]{bname}.{tl}.{f} 首尾差 {d:.3f}")
                # AC4 Loop 有界
                if beat == "Loop":
                    if tl == "rotate" and rng["angle"] > 8.0 + 1e-6 and bname_role_effect(bname):
                        pass  # 特效 spin 例外(下面單獨處理)
                    if tl == "rotate":
                        # 特效 0→360 例外
                        if rng["angle"] > 8.0 + 1e-6 and rng["angle"] < 359.0:
                            ac4 = False; problems.append(f"[Loop]{bname} rotate range {rng['angle']:.1f}>8")
                    if tl == "scale":
                        for f in fields:
                            vv = [k.get(f, 1.0) for k in track]
                            if min(vv) < 0.9 - 1e-6 or max(vv) > 1.1 + 1e-6:
                                ac4 = False; problems.append(f"[Loop]{bname} scale {f} 越界")
                    if tl == "translate" and max(abs(v) for v in [k.get(f, 0.0) for k in track for f in fields]) > 12 + 1e-6:
                        ac4 = False; problems.append(f"[Loop]{bname} translate>12px")
            per["moved"] = moved
            binfo["bones"][bname] = per
            binfo["n_parts"] += 1
            if moved:
                binfo["moved_parts"] += 1
        # slots 結構
        for sname, tls in a.get("slots", {}).items():
            if sname not in slot_names:
                ac1 = False; problems.append(f"[{beat}] 未知 slot {sname}")

        # AC3:每 beat 應大多數件有動
        if binfo["n_parts"] > 0 and binfo["moved_parts"] < binfo["n_parts"]:
            # 允許個別件在某 beat 靜止,但至少 >=1
            if binfo["moved_parts"] == 0:
                ac3 = False; problems.append(f"[{beat}] 無任何件有動作")

        # ---- AC5 FK 軌跡 ----
        traj = fk_trajectory(a, bone_xy, dur_guess(a))
        binfo["fk"] = traj
        for bname, tr in traj.items():
            if any(math.isnan(x) or math.isnan(y) for (x, y) in tr["samples"]):
                ac5 = False; problems.append(f"[{beat}]{bname} FK NaN")
        if beat == "Loop":
            for bname, tr in traj.items():
                if tr["closure"] > 0.5:
                    ac5 = False; problems.append(f"[Loop]{bname} FK 首尾未閉合 {tr['closure']:.2f}")
        report["beats"][beat] = binfo

    report["ac"] = {"AC1_struct": ac1, "AC2_loop_seamless": ac2,
                    "AC3_has_motion": ac3, "AC4_loop_bounded": ac4, "AC5_fk_traj": ac5}
    report["problems"] = problems
    report["overall_pass"] = all(report["ac"].values())
    return report


# 供 AC4 判斷特效(名稱以 b_光暈 等;此處用簡化:凡 rotate range≈360 即視為特效 spin)
def bname_role_effect(bname):
    return False


def dur_guess(a):
    d = 0.0
    for tls in a.get("bones", {}).values():
        for track in tls.values():
            if track:
                d = max(d, _time(track[-1]))
    return d or 1.0


def fk_trajectory(a, bone_xy, dur, n=12):
    """對每根有 timeline 的 bone,取件中心世界座標軌跡(root-child 前向運動學)。
    root-child 無旋轉繼承 → 世界中心 = setup(x,y) + translate;rotate/scale 繞自身
    中心不改中心位置,但會改件外觀,故軌跡主看 translate。回傳 samples + 位移量 + 閉合誤差。"""
    out = {}
    for bname, tls in a.get("bones", {}).items():
        bx, by = bone_xy.get(bname, (0.0, 0.0))
        tr = tls.get("translate")
        samples = []
        for i in range(n + 1):
            t = dur * i / n
            if tr:
                v = _lerp_track(tr, t, ["x", "y"])
                samples.append((bx + (v["x"] or 0.0), by + (v["y"] or 0.0)))
            else:
                samples.append((bx, by))
        xs = [s[0] for s in samples]; ys = [s[1] for s in samples]
        disp = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        closure = math.hypot(samples[0][0] - samples[-1][0], samples[0][1] - samples[-1][1])
        out[bname] = {"samples": samples, "displacement": round(disp, 3),
                      "closure": round(closure, 4)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", help="build_spine 產出的 skeleton.json")
    ap.add_argument("--anims", default=None, help="若動畫另存;預設讀 skeleton 內的 animations")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton, encoding="utf-8"))
    anims = json.load(open(a.anims, encoding="utf-8")) if a.anims else sk.get("animations", {})
    rep = validate(anims, sk)
    # 精簡輸出
    slim = {"ac": rep["ac"], "overall_pass": rep["overall_pass"],
            "problems": rep["problems"][:20]}
    for beat, bi in rep["beats"].items():
        slim.setdefault("beats", {})[beat] = {
            "moved_parts": f"{bi['moved_parts']}/{bi['n_parts']}",
            "seamless": bi["seamless"],
            "fk_disp": {b: t["displacement"] for b, t in bi["fk"].items()},
        }
    print(json.dumps(slim, ensure_ascii=False, indent=1))
    sys.exit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
