#!/usr/bin/env python3
"""S4 候選17(免 API key 路線,方案A):產生「給 ChatGPT 桌面版手動補圖」的資料包,並把結果收回檢查。

子命令:
  make    原圖 + 洞(圓形 --circle cx,cy,r  或  --mask PNG(alpha>127=要補)  或  --decision JSON --part ID 用 manual 遮罩)
          → 資料包資料夾:
            1_upload_this.png   整張 1024 方形畫布,洞已挖成透明(上傳到 ChatGPT 並在洞上塗選/或直接附提示詞)
            mask_openai.png     OpenAI 慣例遮罩(alpha 0=可編輯)— 若 ChatGPT 介面允許上傳遮罩/或之後 API 用
            overlay_preview.png 洞位置預覽(紅圈)
            prompt.txt          建議提示詞(可改)
            meta.json           還原座標用(畫布位置、縮放、洞)
            HOWTO.md            步驟
  ingest  資料包 + ChatGPT 結果圖 → 對齊成同畫布、只在洞內採用結果(洞外強制保持原圖)→ 輸出
          filled.png、compare.png,並報告洞外漂移(結果圖洞外與原圖的差,越小越好)與洞邊接縫。
用法(repo 根):
  python3 tools/mesh_gen/s4_gptfill_package.py make assets/jiuwei_yanlian_char_crop.png -o OUT --circle 512,440,70
  python3 tools/mesh_gen/s4_gptfill_package.py ingest OUT result.png
"""
import argparse, base64, io, json, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

S = 1024
DEFAULT_PROMPT = ("Fill the transparent (erased) area by seamlessly continuing the surrounding content. "
                  "Match the existing style, colors, texture and lighting exactly. "
                  "Do not change anything outside the erased area. Keep the image size and framing identical.")


def to_square(src):
    scale = S / max(src.size)
    im = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ox, oy = (S - im.width) // 2, (S - im.height) // 2
    canvas.paste(im, (ox, oy))
    return canvas, scale, ox, oy


def hole_from_args(a, W, H, scale, ox, oy):
    yy, xx = np.mgrid[0:S, 0:S]
    if a.circle:
        cx, cy, r = [float(v) for v in a.circle.split(",")]   # 原圖座標
        return (xx - (cx * scale + ox)) ** 2 + (yy - (cy * scale + oy)) ** 2 <= (r * scale) ** 2
    if a.mask:
        m = Image.open(a.mask).convert("RGBA")
        arr = np.array(m.split()[-1]) if m.getextrema()[3][0] < 255 else np.array(m.convert("L"))
        m2 = Image.fromarray(((arr > 127) * 255).astype(np.uint8)).resize((round(W * scale), round(H * scale)), Image.NEAREST)
        full = Image.new("L", (S, S), 0); full.paste(m2, (ox, oy)); return np.array(full) > 127
    if a.decision and a.part:
        d = json.load(open(a.decision, encoding="utf-8"))
        p = next(p for p in d["parts"] if p["id"] == a.part)
        raw = base64.b64decode(p["mask_png"].split(",", 1)[-1])
        m = Image.open(io.BytesIO(raw)).convert("RGBA")
        m2 = Image.fromarray(((np.array(m.split()[-1]) > 127) * 255).astype(np.uint8)).resize((round(W * scale), round(H * scale)), Image.NEAREST)
        full = Image.new("L", (S, S), 0); full.paste(m2, (ox, oy)); return np.array(full) > 127
    raise SystemExit("需指定 --circle 或 --mask 或 --decision+--part")


def make(a):
    src = Image.open(a.image).convert("RGBA")
    canvas, scale, ox, oy = to_square(src)
    hole = hole_from_args(a, src.width, src.height, scale, ox, oy)
    if a.grow:
        hole = ndimage.binary_dilation(hole, iterations=a.grow)
    if not hole.any():
        raise SystemExit("洞是空的")
    os.makedirs(a.out, exist_ok=True)
    base = np.array(canvas)
    holed = base.copy(); holed[hole] = (0, 0, 0, 0)
    Image.fromarray(holed).save(os.path.join(a.out, "1_upload_this.png"))
    canvas.save(os.path.join(a.out, "original_canvas.png"))
    mk = np.zeros((S, S, 4), np.uint8); mk[..., :3] = 255; mk[..., 3] = np.where(hole, 0, 255)
    Image.fromarray(mk).save(os.path.join(a.out, "mask_openai.png"))
    ov = canvas.convert("RGB"); ys, xs = np.nonzero(hole)
    d = ImageDraw.Draw(ov); d.rectangle([xs.min() - 6, ys.min() - 6, xs.max() + 6, ys.max() + 6], outline=(255, 60, 60), width=3)
    ov.save(os.path.join(a.out, "overlay_preview.png"))
    open(os.path.join(a.out, "prompt.txt"), "w", encoding="utf-8").write(a.prompt or DEFAULT_PROMPT)
    json.dump({"source": os.path.basename(a.image), "src_size": list(src.size), "canvas": S, "scale": scale,
               "offset": [ox, oy], "hole_px": int(hole.sum()), "hole_bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]},
              open(os.path.join(a.out, "meta.json"), "w"), indent=1)
    open(os.path.join(a.out, "HOWTO.md"), "w", encoding="utf-8").write(f"""# ChatGPT 桌面版補圖步驟

1. 開 ChatGPT(使用有圖片生成功能的模型/GPT-image),附上 `1_upload_this.png`(洞=透明區)。
2. 貼上 `prompt.txt` 的提示詞送出。若介面提供「選取區域/編輯」,在洞的位置塗選後再送出。
3. 生成後下載結果圖(PNG),存成 `result.png`。建議同一張重試 2~3 次,各存 `result_1.png`、`result_2.png`…
4. 回到 repo 根目錄執行:
   `python3 tools/mesh_gen/s4_gptfill_package.py ingest {a.out} result.png`
   (會自動把結果縮放對齊、**只採用洞內**,洞外強制保持原圖,並輸出 `filled.png` / `compare.png` 與漂移報告)
5. 把 `{a.out}` 資料夾(含 result*.png 與 ingest 輸出)commit/push,或直接傳給我。
""")
    print("package ->", a.out, "hole_px", int(hole.sum()))


def ingest(a):
    meta = json.load(open(os.path.join(a.pkg, "meta.json")))
    orig = np.array(Image.open(os.path.join(a.pkg, "original_canvas.png")).convert("RGBA")).astype(np.float64)
    mk = np.array(Image.open(os.path.join(a.pkg, "mask_openai.png")))[..., 3]
    hole = mk < 128
    res = Image.open(a.result).convert("RGBA")
    scale_note = None
    if res.size != (S, S):
        scale_note = f"結果圖尺寸 {res.size} ≠ {S}x{S},已縮放(若長寬比不同請檢查是否被裁切)"
        res = res.resize((S, S), Image.LANCZOS)
    r = np.array(res).astype(np.float64)
    # 洞外漂移:結果 vs 原圖(僅在原圖不透明處比)
    outside = (~hole) & (orig[..., 3] > 200)
    drift = float(np.abs(r[..., :3] - orig[..., :3])[outside].mean())
    out = orig.copy(); out[hole] = r[hole]; out[..., 3][hole] = 255 if a.opaque else r[..., 3][hole]
    # 洞邊接縫:洞邊緣 3px 環內,洞內側與洞外側平均色差
    inner = hole & ~ndimage.binary_erosion(hole, iterations=3)
    outer = ndimage.binary_dilation(hole, iterations=3) & ~hole
    seam = float(np.abs(out[inner][:, :3].mean(0) - out[outer][:, :3].mean(0)).mean()) if inner.any() and outer.any() else None
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(a.pkg, "filled.png"))
    x0, y0, x1, y1 = meta["hole_bbox"]; pad = 60
    box = (max(0, x0 - pad), max(0, y0 - pad), min(S, x1 + pad), min(S, y1 + pad))
    tiles = []
    for arr in (orig, np.array(Image.open(os.path.join(a.pkg, "1_upload_this.png")).convert("RGBA")).astype(np.float64), out):
        t = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).crop(box)
        bg = Image.new("RGBA", t.size, (60, 60, 60, 255)); bg.alpha_composite(t)
        tiles.append(bg.convert("RGB").resize((t.width * 2, t.height * 2), Image.LANCZOS))
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 20, tiles[0].height), (24, 24, 28)); x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 10
    sheet.save(os.path.join(a.pkg, "compare.png"))
    rep = {"outside_hole_drift_mean_abs_rgb": round(drift, 2), "seam_mean_abs_rgb": None if seam is None else round(seam, 2),
           "note": scale_note, "hint": "drift 大(>8)代表 ChatGPT 改動了洞外內容/位移縮放;已被強制還原,但結果的洞內對位可信度也會下降。"}
    json.dump(rep, open(os.path.join(a.pkg, "ingest_report.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("make"); m.add_argument("image"); m.add_argument("-o", "--out", required=True)
    m.add_argument("--circle"); m.add_argument("--mask"); m.add_argument("--decision"); m.add_argument("--part")
    m.add_argument("--grow", type=int, default=0, help="洞向外膨脹 px(給模型多一點接縫修補空間)"); m.add_argument("--prompt")
    i = sp.add_parser("ingest"); i.add_argument("pkg"); i.add_argument("result"); i.add_argument("--opaque", action="store_true", help="洞內 alpha 強制 255")
    a = ap.parse_args()
    make(a) if a.cmd == "make" else ingest(a)


if __name__ == "__main__":
    main()
