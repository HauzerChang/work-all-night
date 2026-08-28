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
        entry = {"name": layer.name, "z": i, "opacity": int(getattr(layer, "opacity", 255)),
                 "offset": [left, top], "size": [im.width, im.height]}
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            fn = f"{i:02d}_{safe}.png"
            im.save(os.path.join(out_dir, fn))
            entry["file"] = fn
        manifest["parts"].append(entry)
        parts.append((entry, im))
    if out_dir:
        # 存 PSD 原始 composite 當預覽器的參照圖(供 psd_preview.html 疊圖比對重組結果)
        # force=True:對「我方工具重存」的 PSD,內嵌合併預覽圖常缺真實 alpha(見
        # knowledge/s4-psd-inplace-edit.md),composite() 預設會直接吃到這張壞掉的預覽,
        # 讓 alpha 整張變 255(全不透明)。force 讓它從實際圖層重新合成,對原生 Photoshop
        # 檔案也安全(兩者差異 <1 premult MAE,純捨入誤差)。
        comp = psd.composite(force=True).convert("RGBA").resize((W, H))
        comp.save(os.path.join(out_dir, "composite.png"))
        manifest["composite"] = "composite.png"
        json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"),
                  ensure_ascii=False, indent=2)
    return psd, manifest, parts


def reassemble(parts, W, H, skip=None):
    """各件 alpha-over 由下而上重組(套用圖層 opacity);skip=z 漏掉某件(負對照)。回傳 (canvas, cover)。"""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cover = np.zeros((H, W), np.int32)
    for entry, im in parts:
        if skip is not None and entry["z"] == skip:
            continue
        op = entry.get("opacity", 255)
        if op < 255:  # 圖層 opacity 烤進 alpha(切件本身不含,僅重組驗證時還原 composite)
            r, g, b, a = im.split()
            a = a.point(lambda v: v * op // 255)
            im = Image.merge("RGBA", (r, g, b, a))
        full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        full.paste(im, tuple(entry["offset"]))
        canvas = Image.alpha_composite(canvas, full)
        l, t = entry["offset"]; w, h = entry["size"]
        a = np.array(im.split()[-1]) > 8
        # 圖層 bbox 可能部份/完全超出畫布(如美術留在畫布外的參考圖層)→ 裁到畫布內再疊,
        # 否則負 offset 會讓 numpy slice 用 Python 負索引語意,算出錯誤區塊甚至 shape 不合而 crash。
        src_l, src_t = max(0, -l), max(0, -t)
        dst_l, dst_t = max(0, l), max(0, t)
        dst_r, dst_b = min(W, l + w), min(H, t + h)
        if dst_r > dst_l and dst_b > dst_t:
            cw, ch = dst_r - dst_l, dst_b - dst_t
            cover[dst_t:dst_t + ch, dst_l:dst_l + cw] += \
                a[src_t:src_t + ch, src_l:src_l + cw].astype(np.int32)
    return canvas, cover


def _premult_diff(recon, ref):
    """premultiplied-alpha 比對:透明區自動歸零、半透明正確加權。
    回傳 (premult_rgb_mae, alpha_mae)。避免在 alpha=0 的無意義 RGB 上誤判
    (composite 透明區填白、重組填黑 → 直接比 RGB 會假性失敗)。"""
    a = np.asarray(recon, np.float64); b = np.asarray(ref, np.float64)
    ap = a[..., :3] * a[..., 3:4] / 255.0
    bp = b[..., :3] * b[..., 3:4] / 255.0
    return float(np.abs(ap - bp).mean()), float(np.abs(a[..., 3] - b[..., 3]).mean())


def evaluate(psd_path, mae_thresh=2.0, orphan_thresh=0.005):
    psd, manifest, parts = slice_psd(psd_path)
    W, H = psd.width, psd.height
    ref = psd.composite(force=True).convert("RGBA").resize((W, H))  # 理由同上,見 slice_psd()
    recon, cover = reassemble(parts, W, H)
    rgb_mae, alpha_mae = _premult_diff(recon, ref)  # premultiplied:透明區不誤判
    content = np.asarray(ref.split()[-1]) > 8
    orphan = float(np.logical_and(content, cover == 0).sum() / max(int(content.sum()), 1))
    res = {
        "AC1_parse": {"pass": len(parts) > 0, "parts": len(parts),
                      "names": [e["name"] for e, _ in parts]},
        "AC2_recon": {"pass": rgb_mae < mae_thresh and alpha_mae < mae_thresh,
                      "premult_rgb_mae": round(rgb_mae, 4), "alpha_mae": round(alpha_mae, 4),
                      "thresh": mae_thresh},
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
