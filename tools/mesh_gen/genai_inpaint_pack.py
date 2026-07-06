#!/usr/bin/env python3
"""P1-B:生成式 AI 補圖「提示詞包」產生器(prompt pack)。

使用者定義的作法(2026-07-06):Claude 是理解型非生成型 →
  ① 用目前 CPU 補圖(telea)把被遮區**先填滿**(給生成 AI 當底/位置提示)
  ② 產生「提示詞包」:底圖 + 遮罩 + 周邊脈絡圖 + 文字提示詞(著重**部位生成**,
     例:「耳機右罩→軀幹」= 生成耳機右罩下層的身體部件)
  ③ 交外部生成型 AI(ChatGPT/gpt-image-1 遮罩編輯、SD inpaint…)完整化
  ④ 回圖過 `inpaint_eval` 閘 + Claude vision 語意自評 + 人審

本工具產 ② 的檔案組;文字提示詞含結構模板 + 語意欄位(部位描述由 Claude vision
看圖後填,或人工補)。輸出目錄:
  base_cpu_fill.png   下層件(全畫布),被遮區已 CPU 粗補 —— 生成 AI 的編輯底圖
  mask.png            要重繪的區域(白=重繪,黑=保留)—— gpt-image-1 遮罩慣例:透明=編輯
  mask_alpha.png      同遮罩但存成「要編輯區=透明」的 RGBA(可直接當 OpenAI images.edit 的 mask)
  context.png         完整合成圖 + 紅框標補區(給生成 AI / 人看脈絡)
  prompt.txt          文字提示詞(中英雙語模板)
  pack.json           機讀 manifest(層名/遮罩統計/檔案清單)
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_tools import PSDImage
from inpaint import complete_layer, occlusion_mask

PROMPT_TEMPLATE = """【任務 / Task】
這是 2D 遊戲角色的一個部位圖層(part layer)。圖層「{lower}」被上層「{upper}」遮住的區域
已用演算法粗略填色(見 base_cpu_fill.png 中 mask 標示的區域),請只重繪該遮罩區域,
把它完整化成自然延續的「{lower}」部位:延續既有輪廓線稿、色塊與明暗,不要改動遮罩外的任何像素。

This is a body-part layer of a 2D game character. The area of layer "{lower}" hidden behind
"{upper}" has been roughly color-filled by an algorithm (the masked area in base_cpu_fill.png).
Repaint ONLY the masked area so it becomes a natural continuation of the "{lower}" part:
continue the existing dark outlines, flat color regions and shading. Do not change any pixel
outside the mask.

【部位語意 / Part semantics】(由 Claude vision 看圖填寫)
{semantics}

【風格 / Style】
- 賽璐璐平塗(flat cel-shading)、乾淨的深色輪廓線、無雜訊
- 與 base_cpu_fill.png 遮罩外區域的線寬、色階完全一致
- 背景保持透明(輸出含 alpha 的 PNG,尺寸與 base 相同:{W}x{H})

【參考 / Reference】
- context.png:角色完整合成圖,紅框 = 需要生成的區域(該區在完整圖中被「{upper}」蓋住)
"""


def full_rgba(psd, name, W, H):
    l = [x for x in psd.descendants() if x.name == name][0]
    im = np.array(l.topil().convert("RGBA"))
    o = np.zeros((H, W, 4), np.uint8)
    o[int(l.top):int(l.top) + im.shape[0], int(l.left):int(l.left) + im.shape[1]] = im
    return o


def composite_all(psd, W, H):
    c = np.zeros((H, W, 4), np.uint8)
    for l in psd.descendants():
        if l.is_group() or not l.is_visible():
            continue
        src = full_rgba(psd, l.name, W, H)
        a = src[..., 3:4].astype(np.float32) / 255.0
        c[..., :3] = (src[..., :3] * a + c[..., :3] * (1 - a)).astype(np.uint8)
        c[..., 3] = np.maximum(c[..., 3], src[..., 3])
    return c


def build_pack(psd_path, upper, lower, out_dir, grow=14, semantics="(待填:此區應是什麼部位結構、有哪些線稿/色塊要延續)"):
    psd = PSDImage.open(psd_path)
    W, H = psd.width, psd.height
    U = full_rgba(psd, upper, W, H)
    L = full_rgba(psd, lower, W, H)
    fill = occlusion_mask(L[..., 3], U[..., 3], grow=grow)
    n_fill = int(fill.sum())
    base = complete_layer(L, fill, "telea")

    os.makedirs(out_dir, exist_ok=True)
    cv2.imwrite(os.path.join(out_dir, "base_cpu_fill.png"), cv2.cvtColor(base, cv2.COLOR_RGBA2BGRA))
    cv2.imwrite(os.path.join(out_dir, "mask.png"), (fill * 255).astype(np.uint8))
    # OpenAI images.edit 慣例:mask 的「透明」處=要編輯 → base 的 RGBA,把 fill 區 alpha 挖 0
    mask_alpha = base.copy()
    mask_alpha[..., 3] = np.where(fill > 0, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(out_dir, "mask_alpha.png"), cv2.cvtColor(mask_alpha, cv2.COLOR_RGBA2BGRA))

    comp = composite_all(psd, W, H)
    ctx = comp[..., :3].copy()
    ys, xs = np.where(fill > 0)
    if len(ys):
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
        cv2.rectangle(ctx, (int(x0) - 4, int(y0) - 4), (int(x1) + 4, int(y1) + 4), (255, 40, 40), 2)
    cv2.imwrite(os.path.join(out_dir, "context.png"), cv2.cvtColor(ctx, cv2.COLOR_RGB2BGR))

    prompt = PROMPT_TEMPLATE.format(upper=upper, lower=lower, W=W, H=H, semantics=semantics)
    open(os.path.join(out_dir, "prompt.txt"), "w").write(prompt)
    manifest = {"psd": os.path.basename(psd_path), "upper": upper, "lower": lower,
                "grow": grow, "fill_px": n_fill, "canvas": [W, H],
                "files": ["base_cpu_fill.png", "mask.png", "mask_alpha.png", "context.png", "prompt.txt"],
                "gate": "回圖後跑 inpaint_eval.evaluate(結果, mask, 原 alpha) + vision 語意自評 + 人審"}
    json.dump(manifest, open(os.path.join(out_dir, "pack.json"), "w"), ensure_ascii=False, indent=2)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("upper", help="上層(遮擋者)圖層名")
    ap.add_argument("lower", help="下層(要補的部位)圖層名")
    ap.add_argument("-o", "--out", default="genai_pack")
    ap.add_argument("--grow", type=int, default=14)
    ap.add_argument("--semantics", default=None, help="部位語意描述(Claude vision 看圖後填)")
    a = ap.parse_args()
    kw = {"semantics": a.semantics} if a.semantics else {}
    m = build_pack(a.psd, a.upper, a.lower, a.out, a.grow, **kw)
    print(json.dumps(m, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
