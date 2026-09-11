#!/usr/bin/env python3
"""軌跡工具鏈的自我驗收閘(AC-first;RULES.md 的自我驗證迴圈)。

A1 三分解可加性      actual == rigid + rotOwn + transOwn(殘差 < 1e-9 px)
A2 無損 round-trip   分析→spec(旋鈕全中性)→套回,local 關鍵值與原檔逐值相同 + V1–V7 全 PASS
A3 延後 L 幀         套後的自身位移 == 原自身位移循環平移 L 幀;總長不變
A4 幅度縮放          scale=k → 自身位移峰對峰 == k×原值(以震盪中心縮放)
A5 負對照            動到別的骨骼 / key 超長 / 改 skins / 改原動畫 → 對應閘要 FAIL
A6 JS↔Python parity  編輯器頁內演算法與 Python 逐點相同(< 1e-9)
A7 瀏覽器端到端      無頭瀏覽器操作編輯器 → 匯出 spec → Python 套用,
                     頁面預測的世界軌跡 vs 實測 < 0.5px(這條成立,來回試錯才真的省下)

用法:python3 tools/motion/validate_motion_tools.py [--json assets/main_draw.json] [--no-browser]
"""
import argparse
import copy
import json
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import analyze_trajectory as AT  # noqa: E402
import apply_motion_spec as AP  # noqa: E402
import motion_spec as MS  # noqa: E402
import spine_world as W  # noqa: E402
import verify_motion as V  # noqa: E402

CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


def editor_path():
    """編輯器位置:repo 的 tools/motion/ 與 skill 套件的 scripts/motion/ 相對位置相同。"""
    cands = [os.path.join(ROOT, "spine_trajectory_editor.html"),
             os.path.join(HERE, "..", "spine_trajectory_editor.html"),
             os.path.join(HERE, "spine_trajectory_editor.html"),
             os.environ.get("SPINE_TRAJECTORY_EDITOR", "")]
    for c in cands:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    raise SystemExit("找不到 spine_trajectory_editor.html(可用環境變數 SPINE_TRAJECTORY_EDITOR 指定)")
RESULTS = []


def skip(name, why):
    print(f"  [skip] {name} — {why}")


def ac(name, ok, detail):
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
    return ok


def spec_from_traj(tj, out_anim, **edit):
    sp = {"schema": MS.SCHEMA, "source": tj["source"], "target": tj["target"],
          "body": {"bone": tj["body"]["bone"]},
          "output": {"animation": out_anim, "mode": "new"},
          "edit": dict(tj["edit"])}
    sp["edit"].update(edit)
    return sp


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(ROOT, "assets", "main_draw.json"))
    ap.add_argument("--anim", default="main_draw_loop")
    ap.add_argument("--bone", default="face")
    ap.add_argument("--body", default="main")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.exists(a.json):
        raise SystemExit(f"找不到 skeleton JSON:{a.json}\n"
                         "(skill 套件不內含測試資產,請用 --json 指向你的 Main.json,"
                         "並用 --anim/--bone/--body 指定動畫與骨骼)")
    data = json.load(open(a.json, encoding="utf-8"))
    sk = W.Skel(data)
    anim = data["animations"][a.anim]
    dur = W.duration(anim)
    fps = 30.0
    tj = AT.analyze(data, a.anim, a.bone, a.body, fps, 4, None, a.json)
    px, py = tj["target"]["point"]
    print(f"資產 {os.path.relpath(a.json)} · {a.anim} · 目標 {a.bone} · 主體 {a.body} "
          f"· 追蹤點 {tj['target']['pointDesc']}")

    # ---- A1 三分解可加性 ----
    resid = 0.0
    for i in range(201):
        t = dur * i / 200
        r, ro, tr, act = sk.own_split(a.bone, anim, t, px, py)
        resid = max(resid, abs(r[0] + ro[0] + tr[0] - act[0]), abs(r[1] + ro[1] + tr[1] - act[1]))
    ac("A1 三分解可加性", resid < 1e-9, f"max residual {resid:.3g} px")

    # ---- A2 無損 round-trip ----
    sp = spec_from_traj(tj, a.anim + "_rt")
    nd, info = AP.apply_spec(sp, data)
    checks = V.structural_checks(data, nd, a.anim, a.anim + "_rt", a.bone)
    orig_keys = anim["bones"][a.bone].get("translate") or []
    new_keys = nd["animations"][a.anim + "_rt"]["bones"][a.bone]["translate"]
    if orig_keys and len(orig_keys) == len(new_keys):
        kerr = max(max(abs(o.get("x", 0) - n.get("x", 0)), abs(o.get("y", 0) - n.get("y", 0)))
                   for o, n in zip(orig_keys, new_keys))
        terr = max(abs(o.get("time", 0) - n.get("time", 0)) for o, n in zip(orig_keys, new_keys))
    else:
        kerr = terr = float("nan")
    degenerate = not tj["editable"]["usable"]
    if degenerate:
        skip("A2/A3/A4/A7/A8", f"目標 {a.bone} 在 {a.anim} 沒有可調的自身運動曲線"
             f"(translate {tj['editable']['keys']} 個 key、振幅 {tj['editable']['oscillationPP']}px = 靜態擺位);"
             "旋鈕類 AC 不適用,只跑結構與 parity")
    if not degenerate:
        ac("A2 無損 round-trip", V.all_pass(checks) and kerr <= 1e-4 and terr <= 1e-4,
           f"V1–V7 {'全 PASS' if V.all_pass(checks) else '有 FAIL:' + str([c[0] for c in checks if not c[1]])}"
           f";local 關鍵值最大差 {kerr:.3g} px、時間差 {terr:.3g}s")

    # ---- A3 延後 L 幀 ----
    L = 5.0
    spL = spec_from_traj(tj, a.anim + "_lag", lag=L)
    ndL, infoL = AP.apply_spec(spL, data)
    chkL = V.structural_checks(data, ndL, a.anim, a.anim + "_lag", a.bone)
    MO = V.measure(data, a.anim, a.bone, a.body, fps, 8, (px, py))
    MN = V.measure(ndL, a.anim + "_lag", a.bone, a.body, fps, 8, (px, py))
    nf = dur * fps
    n = len(MO["frame"]) - 1
    step = n / nf                      # 每幀取樣點數
    shift = int(round(L * step))
    err = max(max(abs(MN["transOwn"][i][0] - MO["transOwn"][(i - shift) % n][0]),
                  abs(MN["transOwn"][i][1] - MO["transOwn"][(i - shift) % n][1]))
              for i in range(n))
    dur_ok = abs(W.duration(ndL["animations"][a.anim + "_lag"]) - dur) < 1e-9
    if not degenerate:
        ac("A3 延後 L=5 幀", err < 0.15 and dur_ok and V.all_pass(chkL),
           f"與原曲線循環平移 5 幀比對 max {err:.4f} px(世界↔local 內插的固有殘差);"
           f"總長 {'不變' if dur_ok else '**變了**'}")

    # ---- A4 幅度縮放 ----
    k = 1.15
    spS = spec_from_traj(tj, a.anim + "_amp", scale=k)
    ndS, _ = AP.apply_spec(spS, data)
    MS_ = V.measure(ndS, a.anim + "_amp", a.bone, a.body, fps, 8, (px, py))

    def pp(series, i):
        v = [p[i] for p in series]
        return max(v) - min(v)

    before, after = pp(MO["transOwn"], 1), pp(MS_["transOwn"], 1)
    ratio = after / before if before > 1e-9 else float("nan")
    if not degenerate:
        ac("A4 幅度縮放 ×1.15", abs(ratio - k) < 0.02,
           f"自身位移 Y 峰對峰 {before:.3f} → {after:.3f} px(比值 {ratio:.4f},目標 {k})")

    # ---- A5 負對照 ----
    neg = []
    bad = copy.deepcopy(nd)                      # 多動一根不該動的骨骼
    other = next(b for b in bad["animations"][a.anim + "_rt"]["bones"] if b != a.bone)
    tl = bad["animations"][a.anim + "_rt"]["bones"][other]
    ch = list(tl.keys())[0]
    tl[ch] = copy.deepcopy(tl[ch])
    tl[ch][0] = dict(tl[ch][0]); tl[ch][0]["__tamper"] = 1
    c2 = V.structural_checks(data, bad, a.anim, a.anim + "_rt", a.bone)
    neg.append(("V2 應抓到多動的骨骼", not dict((c[0], c[1]) for c in c2)["V2"]))

    bad2 = copy.deepcopy(nd)                     # keyframe 超出總長
    bad2["animations"][a.anim + "_rt"]["bones"][a.bone]["translate"].append({"time": dur + 0.2, "x": 0, "y": 0})
    c3 = V.structural_checks(data, bad2, a.anim, a.anim + "_rt", a.bone)
    neg.append(("V7 應抓到 key 超出總長", not dict((c[0], c[1]) for c in c3)["V7"]))

    bad3 = copy.deepcopy(nd)                     # 動到 skins
    if isinstance(bad3.get("skins"), list) and bad3["skins"]:
        bad3["skins"][0]["__tamper"] = 1
    else:
        bad3["skins"] = {"__tamper": 1}
    c4 = V.structural_checks(data, bad3, a.anim, a.anim + "_rt", a.bone)
    neg.append(("V5 應抓到 skins 被動", not dict((c[0], c[1]) for c in c4)["V5"]))

    bad4 = copy.deepcopy(nd)                     # 動到原動畫
    bad4["animations"][a.anim]["bones"][a.bone]["translate"][0]["y"] = 99
    c5 = V.structural_checks(data, bad4, a.anim, a.anim + "_rt", a.bone)
    neg.append(("V4 應抓到原動畫被改", not dict((c[0], c[1]) for c in c5)["V4"]))

    ac("A5 負對照", all(v for _, v in neg), "; ".join(f"{k2}{'✓' if v else '✗'}" for k2, v in neg))

    # ---- A6 JS↔Python parity ----
    probe = os.path.join(HERE, "js_core_probe.js")
    try:
        raw = subprocess.run(["node", probe, a.json, a.anim, a.bone, a.body, str(px), str(py), "30", "4"],
                             capture_output=True, text=True, timeout=120, check=True).stdout
        js = json.loads(raw)
        dmax = 0.0
        for s in js["series"]:
            t = s["t"]
            r, ro, tr, act = sk.own_split(a.bone, anim, t, px, py)
            b = sk.world_pos(a.body, anim, t)
            for jv, pv in ((s["rigid"], r), (s["rotOwn"], ro), (s["transOwn"], tr), (s["actual"], act), (s["body"], b)):
                dmax = max(dmax, abs(jv[0] - pv[0]), abs(jv[1] - pv[1]))
        C = {"curve": 0.374, "c2": 0.02, "c3": 0.636, "c4": 0.99}
        keys = [{"frame": 0, "wx": 0, "wy": 3, "curve": C}, {"frame": 6, "wx": 1.5, "wy": -2, "curve": C},
                {"frame": 13, "wx": -1.5, "wy": 4, "curve": C}, {"frame": 20, "wx": 0, "wy": 3}]
        smax = 0.0
        for case, jr in js["spec"].items():
            lag, scale = (float(x) for x in case.split("|"))
            kb = MS.apply_knobs(keys, ("wx", "wy"), lag=lag, scale=scale, nf=20)
            wr = MS.wrap_cycle(kb, 20, ("wx", "wy"))
            for i, jk in enumerate(jr["wrapped"]):
                smax = max(smax, abs(jk["frame"] - wr[i]["frame"]), abs(jk["wx"] - wr[i]["wx"]), abs(jk["wy"] - wr[i]["wy"]))
            for i, js_ in enumerate(jr["samples"]):
                pv = MS.sample_keys(wr, ("wx", "wy"), i * 0.25, 20)
                smax = max(smax, abs(js_["wx"] - pv["wx"]), abs(js_["wy"] - pv["wy"]))
        ac("A6 JS↔Python parity", dmax < 1e-9 and smax < 1e-9,
           f"世界座標 max diff {dmax:.3g} px;spec 數學(旋鈕/迴圈切分/取樣) max diff {smax:.3g}")
    except Exception as e:  # noqa: BLE001
        ac("A6 JS↔Python parity", False, f"node 探針失敗:{e}")

    # ---- A7/A8 瀏覽器 ----
    if a.no_browser:
        print("  [skip] A7 瀏覽器端到端、A8 viewer 橋接(--no-browser)")
    else:
        if degenerate:
            skip("A7/A8", "退化目標,跳過瀏覽器端到端與橋接(無曲線可編輯)")
        else:
            ok, detail = browser_e2e(a)
            ac("A7 瀏覽器端到端", ok, detail)
            ok8, detail8 = bridge_e2e(a)
            ac("A8 viewer 橋接契約", ok8, detail8)

    print()
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{'全數通過' if npass == len(RESULTS) else '**有未過項目**'}:{npass}/{len(RESULTS)}")
    return 0 if npass == len(RESULTS) else 1


def browser_e2e(a):
    """用無頭瀏覽器實際操作編輯器:載入骨架 → 設旋鈕 → 匯出 spec → Python 套回 → 比對預測。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (False, "未安裝 playwright(pip install playwright);其餘 AC 不受影響")
    if not os.path.exists(CHROME):
        return (False, f"找不到 chromium:{CHROME}")
    page_url = "file://" + editor_path()
    skel = json.load(open(a.json, encoding="utf-8"))
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.type + ":" + m.text) if m.type == "error" else None)
        pg.goto(page_url)
        pg.wait_for_timeout(300)
        spec = pg.evaluate(
            """([skel, anim, bone, body]) => {
                loadSkeleton(skel, 'main_draw.json');
                S.animName = anim; S.bone = bone; S.bodyBone = body; S.pointLocked = false;
                reanalyze(true);
                S.knobs.lag = 5; S.knobs.scale = 1.15; S.knobs.curve = 'keep';
                // 模擬使用者在圖上改一個關鍵幀(第 2 個點往上拉 2px、往後 1 幀)
                if (S.keys.length > 1) { S.keys[1].wy += 2; S.keys[1].frame += 1; S.keys.sort((x,y)=>x.frame-y.frame); }
                redraw();
                return buildSpec();
            }""", [skel, a.anim, a.bone, a.body])
        shot = os.path.join(os.getcwd(), "out", "editor_e2e.png")
        os.makedirs(os.path.dirname(shot), exist_ok=True)
        pg.screenshot(path=shot, full_page=True)
        b.close()
    if errs:
        return (False, f"頁面有錯誤:{errs[:3]}")
    spec["source"]["json"] = a.json
    spec["output"]["animation"] = a.anim + "_e2e"
    data = json.load(open(a.json, encoding="utf-8"))
    nd, info = AP.apply_spec(spec, data)
    checks = V.structural_checks(data, nd, a.anim, a.anim + "_e2e", a.bone)
    quant = V.quantitative(data, nd, a.anim, a.anim + "_e2e", a.bone, a.body, 30.0, 4,
                           spec["target"]["point"],
                           intent=AP.intent_fn(info["wrappedKeys"], info["frames"]),
                           predicted=spec.get("predicted"))
    perr = quant.get("predictErrMax")
    ok = V.all_pass(checks) and perr is not None and perr < 0.5
    with open(os.path.join(os.getcwd(), "out", "editor_e2e.spec.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    return (ok, f"頁面匯出 spec(lag=5, scale=1.15, 拖動 1 個關鍵幀)→ 套回後 "
                f"V1–V7 {'全 PASS' if V.all_pass(checks) else 'FAIL'};"
                f"頁面預測 vs 實測世界軌跡 max {perr} px({quant.get('predictErrN')} 點);截圖 out/editor_e2e.png")


def bridge_e2e(a):
    """A8:模擬 viewer 端(bridge_harness.html)收送 postMessage,證明
    「編輯器送出的 translate keys」貼進動畫後 == 編輯器自己畫的預測。
    這是進階功能『直接從 viewer 編輯軌跡』的可驗證部分;
    真正的 spine-webgl 畫面預覽要在使用者端(CDN 通)才跑得起來。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (False, "未安裝 playwright")
    harness = ("file://" + os.path.join(HERE, "bridge_harness.html")
               + "?editor=" + "file://" + editor_path())
    skel = json.load(open(a.json, encoding="utf-8"))
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(harness)
        pg.wait_for_function("window.__loaded === true", timeout=15000)
        pg.evaluate("([s,an,bo,bd]) => window.sendLoad(s,an,bo,bd)", [skel, a.anim, a.bone, a.body])
        pg.wait_for_timeout(400)
        fr = pg.frames[1]
        spec = fr.evaluate("""([anim,bone,body]) => {
            S.animName=anim; S.bone=bone; S.bodyBone=body; S.pointLocked=false; reanalyze(true);
            S.knobs.lag=4; S.knobs.scale=1.2; syncUI(); redraw();
            document.querySelector('#btnPreview').click();
            return buildSpec();
        }""", [a.anim, a.bone, a.body])
        pg.wait_for_function("window.__preview !== null", timeout=8000)
        prev = pg.evaluate("window.__preview")
        b.close()
    if errs:
        return (False, f"頁面錯誤:{errs[:2]}")
    if not prev or prev.get("bone") != a.bone or not prev.get("keys"):
        return (False, f"未收到合格的 preview 訊息:{str(prev)[:120]}")

    # 依 viewer 端 applyTrajectoryPreview 的作法把 keys 貼進新動畫,再用同一套閘驗
    data = json.load(open(a.json, encoding="utf-8"))
    nd = copy.deepcopy(data)
    out = a.anim + "_bridge"
    nd["animations"][out] = copy.deepcopy(nd["animations"][a.anim])
    nd["animations"][out].setdefault("bones", {}).setdefault(a.bone, {})["translate"] = prev["keys"]
    checks = V.structural_checks(data, nd, a.anim, out, a.bone)
    quant = V.quantitative(data, nd, a.anim, out, a.bone, a.body, 30.0, 4,
                           spec["target"]["point"], predicted=spec.get("predicted"))
    perr = quant.get("predictErrMax")
    ok = V.all_pass(checks) and perr is not None and perr < 0.5
    return (ok, f"harness 收到 {len(prev['keys'])} 個 translate keys(lag=4, 幅度×1.2);"
                f"貼進動畫後 V1–V7 {'全 PASS' if V.all_pass(checks) else 'FAIL:' + str([c[0] for c in checks if not c[1]])};"
                f"與編輯器預測 max {perr} px")


if __name__ == "__main__":
    sys.exit(main())
