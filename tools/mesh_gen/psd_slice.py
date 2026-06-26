#!/usr/bin/env python3
"""S4 PSD-first 切圖工具 — 分層 PSD → 各部位件 PNG + manifest,並自驗重組無損。

PSD-first 契約(見 knowledge/s4-psd-contract.md):美術交分層 PSD,每個可見 leaf 圖層
= 一個可動部位件。本工具:
  讀 PSD → 枚舉可見 leaf 圖層 → 每件切出『裁到該層 bbox 的緊湊 PNG』+ 記 offset/size
  → 輸出 manifest.json → 自驗:各件依 offset 以 alpha-over 由下而上重組 == PSD composite。

復用 S2 切圖閘精神(切圖正確 ⇔ 重組還原原圖、0 孤兒)。對應 PLAN.md S4 完成條件。
"""
import argparse, json, os
import numpy as np
from PIL import Image
from psd_tools import PSDImage


def leaf_layers(psd):
    """可見 leaf 圖層,依繪製順序(由下而上)。
    psd-tools `descendants()` 已是由下而上(index 0 = 最底層),直接用即可
    (經自驗:正序重組 MAE≈0.01,反序 15)。"""
    return [l for l in psd.descendants() if not l.is_group() and l.is_visible()]


def slice_psd(psd_path, out_dir=None):
    psd = PSDImage.open(psd_path)
    W, H = psd.width, psd.height
    manifest = {"source": os.path.basename(psd_path), "size": [W, H], "parts": []}
    parts = []
    for i, layer in enumerate(leaf_layers(psd)):
        im = layer.topil()  # 裁到該層 bbox 的像素
        if im is None:
            continue
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        left, top = int(layer.left), int(layer.top)
        safe = layer.name.replace("/", "__")
        entry = {"name": layer.name, "z": i,
                 "offset": [left, top], "size": [im.width, im.height]}
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            fn = f"{i:02d}_{safe}.png"
            im.save(os.path.join(out_dir, fn))
            entry["file"] = fn
        manifest["parts"].append(entry)
        parts.append((entry, im))
    if out_dir:
        json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"),
                  ensure_ascii=False, indent=2)
    return psd, manifest, parts


def reassemble(parts, W, H, skip=None):
    """各件 alpha-over 由下而上重組;skip=z 可漏掉某件(負對照用)。回傳 (canvas, cover)。"""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cover = np.zeros((H, W), np.int32)
    for entry, im in parts:
        if skip is not None and entry["z"] == skip:
            continue
        full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        full.paste(im, tuple(entry["offset"]))
        canvas = Image.alpha_composite(canvas, full)
        l, t = entry["offset"]; w, h = entry["size"]
        a = np.array(im.split()[-1]) > 8
        cover[t:t + h, l:l + w] += a.astype(np.int32)
    return canvas, cover


def evaluate(psd_path, mae_thresh=1.0, orphan_thresh=0.005):
    psd, manifest, parts = slice_psd(psd_path)
    W, H = psd.width, psd.height
    ref = psd.composite().convert("RGBA").resize((W, H))
    recon, cover = reassemble(parts, W, H)
    a = np.asarray(recon, np.int32); b = np.asarray(ref, np.int32)
    mae = float(np.abs(a - b).mean())
    content = np.asarray(ref.split()[-1]) > 8
    orphan = float(np.logical_and(content, cover == 0).sum() / max(int(content.sum()), 1))
    res = {
        "AC1_parse": {"pass": len(parts) > 0, "parts": len(parts),
                      "names": [e["name"] for e, _ in parts]},
        "AC2_recon": {"pass": mae < mae_thresh, "mae": round(mae, 4), "thresh": mae_thresh},
        "AC3_no_orphan": {"pass": orphan <= orphan_thresh,
                          "orphan_ratio": round(orphan, 5), "thresh": orphan_thresh},
    }
    overall = all(v["pass"] for v in res.values())
    return {"overall_pass": overall, "size": [W, H], "criteria": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("-o", "--out", default=None, help="切出各件 PNG + manifest 的目錄")
    ap.add_argument("--eval", action="store_true", help="只跑自驗閘")
    a = ap.parse_args()
    if a.eval:
        rep = evaluate(a.psd)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)
    _, manifest, _ = slice_psd(a.psd, a.out or "psd_parts")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
