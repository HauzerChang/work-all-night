#!/usr/bin/env python3
"""S4 候選17 API 煙霧測試:1 次 images/edits 呼叫(quality=low,1024x1024)驗證端到端可用。
來源:assets/jiuwei_yanlian_char_crop.png 貼到 1024 方形畫布,在角色衣服上挖一個圓洞,請模型補回。
輸出:s4_data/openai_smoke/{input,mask,output}.png + 一行 usage 記錄(openai_usage.jsonl)。
用法(repo 根): python3 tools/mesh_gen/s4_openai_smoke.py
"""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from s4_openai_client import edit_image

OUT = os.path.join(os.path.dirname(__file__), "s4_data", "openai_smoke")


def main():
    os.makedirs(OUT, exist_ok=True)
    src = Image.open("assets/jiuwei_yanlian_char_crop.png").convert("RGBA")
    S = 1024
    scale = S / src.height
    im = src.resize((round(src.width * scale), S), Image.LANCZOS)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    canvas.paste(im, ((S - im.width) // 2, 0))
    rgba = np.array(canvas)
    yy, xx = np.mgrid[0:S, 0:S]
    cx, cy, r = S // 2, int(S * 0.43), 70   # 胸/腰附近的衣物
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    holed = rgba.copy(); holed[mask] = (0, 0, 0, 0)
    Image.fromarray(holed).save(os.path.join(OUT, "input.png"))
    Image.fromarray((mask * 255).astype(np.uint8)).save(os.path.join(OUT, "mask.png"))
    prompt = ("Fill the transparent circular hole by seamlessly continuing the surrounding red and gold "
              "embroidered garment fabric. Keep style, colors and lighting identical. Do not change anything outside the hole.")
    out, rec = edit_image(holed, mask, prompt, size="1024x1024", quality="low", tag="smoke-1")
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(OUT, "output.png"))
    # 並排對照:原圖 / 挖洞 / 結果(只看洞周圍)
    box = (cx - 160, cy - 160, cx + 160, cy + 160)
    tiles = [Image.fromarray(a).crop(box).resize((480, 480), Image.LANCZOS).convert("RGB")
             for a in (rgba, holed, np.clip(out, 0, 255).astype(np.uint8))]
    sheet = Image.new("RGB", (480 * 3 + 20, 480), (30, 30, 30))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 490, 0))
    sheet.save(os.path.join(OUT, "compare_orig_holed_filled.png"))
    print("OK", {k: rec.get(k) for k in ("http_status", "elapsed_s", "usage", "image_px", "mask_coverage_pct")})


if __name__ == "__main__":
    main()
