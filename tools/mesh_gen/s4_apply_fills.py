#!/usr/bin/env python3
"""S4 chunk 309:把驗收通過(含目視覆核)的補圖合成結果寫回切件集,重算 offset/size(外推會長出原框外),
產出新的切件目錄 + manifest,供 manifest_to_psd.js 組 PSD。
用法:python s4_apply_fills.py <src_cut_dir> <dst_cut_dir> <composed_dir> <decisions.json>
decisions.json:{"accept":{"head":"visual_pass","skirt":"gate_pass",...},"reject":{...}}。只套 accept 的件。"""
import json, os, shutil, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inpaint_eval as ie
src, dst, composed, dec_path = sys.argv[1:5]
dec = json.load(open(dec_path))
if os.path.abspath(src) != os.path.abspath(dst):
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst)
man = json.load(open(os.path.join(dst, "manifest.json"))); W, H = man["size"]
applied = {}
for p in man["parts"]:
    pid = p["id"]
    if pid not in dec.get("accept", {}): continue
    cp = os.path.join(composed, f"{pid}.png")
    if not os.path.exists(cp): print(f"skip {pid}: 無合成檔"); continue
    comp = ie.load_rgba(cp)
    if comp.shape[:2] != (H, W): print(f"skip {pid}: 合成尺寸 {comp.shape[:2]} ≠ {(H, W)}"); continue
    a = comp[..., 3] > 0
    if not a.any(): print(f"skip {pid}: 全透明"); continue
    ys, xs = np.where(a); x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    old = (p["offset"], p["size"])
    ie.save_rgba(os.path.join(dst, p["file"]), comp[y0:y1, x0:x1])
    p["offset"] = [x0, y0]; p["size"] = [x1 - x0, y1 - y0]
    p["fill"] = {"source": os.path.relpath(cp, dst), "decision": dec["accept"][pid], "old_offset_size": old}
    p["notes"] = (p.get("notes") or "") + f" [s4_apply_fills: {dec['accept'][pid]}]"
    applied[pid] = {"old": old, "new": (p["offset"], p["size"])}
man["fills_applied"] = applied; man["fill_decisions"] = dec_path
json.dump(man, open(os.path.join(dst, "manifest.json"), "w"), ensure_ascii=False, indent=2)
for k, v in applied.items(): print(f"{k}: offset/size {v['old']} → {v['new']}")
print(f"applied {len(applied)} parts → {dst}")
