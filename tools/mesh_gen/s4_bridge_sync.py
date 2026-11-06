#!/usr/bin/env python3
"""在使用者本機執行:把 chunk60/bridge 任務包搬到 Codex bridge 資料夾(push),或把結果搬回 repo(pull)。
用法:python tools/mesh_gen/s4_bridge_sync.py push|pull <bridge 根目錄> [--chunk chunk60]
不依賴第三方套件;Windows/macOS/Linux 皆可。"""
import argparse, glob, os, shutil, sys

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("action", choices=["push", "pull", "status"])
ap.add_argument("bridge", help=r"bridge 根目錄,如 C:\Users\user\Desktop\切圖補圖研究\bridge")
ap.add_argument("--chunk", default="chunk60")
a = ap.parse_args()
HERE = os.path.dirname(os.path.abspath(__file__))
PK = os.path.join(HERE, "s4_data", a.chunk, "bridge")
BR = os.path.abspath(a.bridge)
if not os.path.isdir(BR):
    sys.exit(f"找不到 bridge 資料夾:{BR}")

def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst); print("  ", os.path.relpath(src, HERE), "->", dst)

if a.action == "push":
    n = 0
    for f in sorted(glob.glob(os.path.join(PK, "briefs", "todo", "*.md"))):
        cp(f, os.path.join(BR, "briefs", "todo", os.path.basename(f))); n += 1
    for f in sorted(glob.glob(os.path.join(PK, "ref", "*"))):
        cp(f, os.path.join(BR, "ref", os.path.basename(f)))
    print(f"已放入 {n} 張任務單。請確認 codex_bridge.cmd 視窗開著;完成後執行 pull。")
elif a.action == "pull":
    out = os.path.join(HERE, "s4_data", a.chunk, "filled"); n = 0
    for f in sorted(glob.glob(os.path.join(BR, "out", "*_filled.png"))):
        cp(f, os.path.join(out, os.path.basename(f))); n += 1
    for f in glob.glob(os.path.join(BR, "logs", "*.run.txt")) + glob.glob(os.path.join(BR, "logs", "*.exit.txt")):
        cp(f, os.path.join(out, "logs", os.path.basename(f)))
    for d in ("failed",):
        for f in glob.glob(os.path.join(BR, d, "*.md")):
            cp(f, os.path.join(out, "logs", d + "_" + os.path.basename(f)))
    print(f"取回 {n} 張補圖 → {out}。請 git add/commit/push 該資料夾。")
else:
    for d in ("briefs/todo", "running", "done", "failed", "out"):
        p = os.path.join(BR, d); print(f"{d:12s}", len(os.listdir(p)) if os.path.isdir(p) else "(無)")
    st = os.path.join(BR, "logs", "bridge_status.json")
    print(open(st, encoding="utf-8-sig").read() if os.path.exists(st) else "無 bridge_status.json(bridge 未啟動過)")
