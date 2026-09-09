#!/usr/bin/env python3
"""把編輯器匯出的 motion spec 套回 Spine JSON,並跑完整驗證清單。

  編輯器(改軌跡) → spec.json → 本工具 → 新動畫寫進 skeleton JSON → 驗證數字

流程對應 spine-motion-skill 第 5、6 步:
  · 只動目標骨骼的 timeline;原動畫 deepcopy 成新版(預設 `<anim>_v2`)供 A/B
  · 世界座標的自身位移 → 用當下父體世界矩陣反矩陣換成 local translate 關鍵值
  · 延後 / 幅度旋鈕 → 迴圈邊界 de Casteljau 切分 → 總長不變、loop 無縫
  · 寫檔後跑 V1–V7 結構閘 + Q1–Q3 量化閘

用法:
  python3 tools/motion/apply_motion_spec.py --spec out/spec.json --write
  python3 tools/motion/apply_motion_spec.py --spec out/spec.json --json other.json --out out/new.json
"""
import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_spec as MS  # noqa: E402
import spine_world as W  # noqa: E402
import verify_motion as V  # noqa: E402

FIELDS = ("wx", "wy")


def build_keys(spec, data, anim, sk, nf, fps):
    """spec.edit → (wrapped 世界關鍵值, Spine local translate timeline)。"""
    ed = spec["edit"]
    bone = spec["target"]["bone"]
    keys = [dict(k) for k in ed["keys"]]
    per_axis = {"wx": float(ed.get("scaleX", 1.0)), "wy": float(ed.get("scaleY", 1.0))}
    knobbed = MS.apply_knobs(keys, FIELDS, lag=float(ed.get("lag", 0.0)),
                             scale=float(ed.get("scale", 1.0)), per_axis=per_axis, nf=nf)
    wrapped = MS.wrap_cycle(knobbed, nf, FIELDS, loop=bool(ed.get("loop", True)))

    space = ed.get("space", "world")
    local = []
    for k in wrapped:
        t = min(max(float(k["frame"]) / fps, 0.0), W.duration(anim))
        if space == "world":
            dx, dy = sk.world_to_local_delta(bone, anim, t, float(k["wx"]), float(k["wy"]), zero=(bone,))
        else:
            dx, dy = float(k["wx"]), float(k["wy"])
        local.append({"frame": k["frame"], "x": dx, "y": dy, "curve": k.get("curve")})
    return wrapped, MS.to_spine_keys(local, fps, ("x", "y"))


def build_rotate_keys(spec, nf, fps):
    rot = spec.get("rotate")
    if not rot or not rot.get("keys"):
        return None
    keys = [dict(k) for k in rot["keys"]]
    knobbed = MS.apply_knobs(keys, ("angle",), lag=float(rot.get("lag", spec["edit"].get("lag", 0.0))),
                             scale=float(rot.get("scale", 1.0)), nf=nf)
    wrapped = MS.wrap_cycle(knobbed, nf, ("angle",))
    return MS.to_spine_keys(wrapped, fps, ("angle",))


def apply_spec(spec, data):
    """回傳 (new_data, info)。不寫檔。"""
    src = spec["source"]
    anim_name = src["animation"]
    fps = float(src.get("fps", 30.0))
    bone = spec["target"]["bone"]
    out_name = (spec.get("output") or {}).get("animation") or f"{anim_name}_v2"
    mode = (spec.get("output") or {}).get("mode", "new")

    if anim_name not in data.get("animations", {}):
        raise SystemExit(f"animation '{anim_name}' 不在 JSON 裡")
    if bone not in {b["name"] for b in data.get("bones", [])}:
        raise SystemExit(f"bone '{bone}' 不在 JSON 裡")
    if out_name in data["animations"] and mode != "overwrite" and out_name != anim_name:
        raise SystemExit(f"動畫 '{out_name}' 已存在;要覆寫請把 output.mode 設 'overwrite'")

    new_data = copy.deepcopy(data)
    sk = W.Skel(new_data)
    anim = new_data["animations"][anim_name]
    dur = W.duration(anim)
    nf = dur * fps

    wrapped, tkeys = build_keys(spec, new_data, anim, sk, nf, fps)
    rkeys = build_rotate_keys(spec, nf, fps)

    new_anim = copy.deepcopy(anim)
    new_anim.setdefault("bones", {}).setdefault(bone, {})
    new_anim["bones"][bone]["translate"] = tkeys
    if rkeys:
        new_anim["bones"][bone]["rotate"] = rkeys
    new_data["animations"][out_name] = new_anim

    info = {
        "animation": anim_name, "outAnimation": out_name, "bone": bone,
        "fps": fps, "duration": dur, "frames": nf,
        "wrappedKeys": wrapped, "translateKeys": tkeys, "rotateKeys": rkeys,
        "knobs": {k: spec["edit"].get(k) for k in ("lag", "scale", "scaleX", "scaleY")},
    }
    return new_data, info


def intent_fn(wrapped, nf):
    def f(frame):
        v = MS.sample_keys(wrapped, FIELDS, frame, nf)
        return (v["wx"], v["wy"])
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description="套用軌跡編輯 spec 到 Spine JSON 並驗證")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--json", help="覆寫 spec.source.json 指定的 skeleton JSON")
    ap.add_argument("--out", help="輸出 JSON 路徑(預設不寫檔,只驗證)")
    ap.add_argument("--write", action="store_true", help="就地寫回來源 JSON")
    ap.add_argument("--spf", type=int, default=4)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    spec = json.load(open(a.spec, encoding="utf-8"))
    if spec.get("schema") != MS.SCHEMA:
        print(f"警告:spec schema = {spec.get('schema')!r}(預期 {MS.SCHEMA!r})", file=sys.stderr)
    src_json = a.json or spec["source"].get("json")
    if not src_json or not os.path.exists(src_json):
        raise SystemExit(f"找不到 skeleton JSON:{src_json}(可用 --json 指定)")
    data = json.load(open(src_json, encoding="utf-8"))

    new_data, info = apply_spec(spec, data)
    point = spec["target"].get("point") or [0.0, 0.0]
    body = (spec.get("body") or {}).get("bone") or info["bone"]

    checks = V.structural_checks(data, new_data, info["animation"], info["outAnimation"], info["bone"])
    quant = V.quantitative(data, new_data, info["animation"], info["outAnimation"], info["bone"], body,
                           info["fps"], a.spf, point,
                           intent=intent_fn(info["wrappedKeys"], info["frames"]),
                           predicted=spec.get("predicted"))
    ok = V.all_pass(checks)
    if not a.quiet:
        print(f"目標 {info['bone']} @ {info['animation']} → 新動畫 '{info['outAnimation']}'  "
              f"旋鈕 {info['knobs']}  keys {len(info['translateKeys'])}")
        print(V.report(checks, quant))

    if ok and (a.write or a.out):
        path = a.out or src_json
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        json.dump(new_data, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print(f"已寫出 {path}")
    elif not ok:
        print("驗證未全過 → **不寫檔**", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
