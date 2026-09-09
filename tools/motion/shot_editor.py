#!/usr/bin/env python3
"""無頭瀏覽器對軌跡編輯器截圖(給 knowledge/figures 用,也是「不靠肉眼」的自我驗證手段)。

用法:
  python3 tools/motion/shot_editor.py --json assets/main_draw.json --anim main_draw_loop \
      --bone face --body main --lag 5 --out knowledge/figures/s6-trajectory-editor.png
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(ROOT, "assets", "main_draw.json"))
    ap.add_argument("--anim", required=True)
    ap.add_argument("--bone", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--lag", type=float, default=0.0)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1500)
    ap.add_argument("--height", type=int, default=980)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    skel = json.load(open(a.json, encoding="utf-8"))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": a.width, "height": a.height}, device_scale_factor=2)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://" + os.path.join(ROOT, "spine_trajectory_editor.html"))
        pg.wait_for_timeout(300)
        info = pg.evaluate("""([skel,anim,bone,body,lag,scale,name]) => {
            loadSkeleton(skel, name);
            S.animName=anim; S.bone=bone; S.bodyBone=body; S.pointLocked=false; reanalyze(true);
            S.knobs.lag=lag; S.knobs.scale=scale; syncUI(); redraw();
            const m=buildSpec().metrics;
            return {before:m.before, after:m.after, phase:m.phaseDeg};
        }""", [skel, a.anim, a.bone, a.body, a.lag, a.scale, os.path.basename(a.json)])
        pg.screenshot(path=a.out, full_page=True)
        b.close()
    if errs:
        print("頁面錯誤:", errs[:3], file=sys.stderr)
        return 1
    print(f"已存 {a.out}\n  前:{info['before']}\n  後:{info['after']}\n  相位 {info['phase']}°")
    return 0


if __name__ == "__main__":
    sys.exit(main())
