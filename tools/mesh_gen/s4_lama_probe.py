#!/usr/bin/env python3
"""S4 候選 4:LaMa(深度 inpaint)可行性探測(一次性 probe,不進 production pipeline)。

背景:`knowledge/s4-inpaint-evaluator.md` 量化出 CPU baseline(nearest/cv2.inpaint)在機械
細節紋理材質(身體/左手)任何洞尺寸皆 1a fail(ssim 上限 ~0.51)。候選 4 要探測的兩件事:
  1. 網路政策是否擋深度 inpaint 的模型權重下載/框架安裝?
  2. 若裝得起來,LaMa 在同一批 1a fail 案例上是否真的能把 ssim/premult_mae 拉過門檻?

依賴刻意不寫進 `requirements.txt`(見 `prompts/run_s4.md` 檔案隔離契約——不影響其他排程的
環境;且如下方結論,本次未建議採用,不該讓每個 session 都重裝這麼重的依賴)。
本檔只依賴 inpaint_eval 既有的挖洞/指標/門檻函式,不改動 production 代碼。
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from inpaint_eval import (  # noqa: E402
    load_rgba, save_rgba, punch_hole, score, passes, score_1b, passes_1b,
    estimate_alpha_taper, THRESH,
)


def fill_lama(rgba_holed, mask, lama):
    """RGB 用 LaMa,alpha 沿用 `fill_cv2_inpaint` 同款 `estimate_alpha_taper`——與既有
    cv2 candidate 同一套 alpha 處理,才能只看 RGB inpainting 品質這一個變因的差異。"""
    from PIL import Image
    import numpy as np
    rgb = np.clip(rgba_holed[..., :3], 0, 255).astype("uint8")
    m = (mask.astype("uint8")) * 255
    result = lama(Image.fromarray(rgb), Image.fromarray(m))
    h, w = rgba_holed.shape[:2]
    result = np.array(result)[:h, :w]  # simple_lama pads to modulo-8; crop back
    out = rgba_holed.copy()
    out[..., :3][mask] = result.astype(rgba_holed.dtype)[mask]
    out[..., 3][mask] = estimate_alpha_taper(rgba_holed[..., 3], mask)[mask]
    return out


def run_case(path, mode, seed, lama, out_dir=None):
    gt = load_rgba(path)
    try:
        _, mask = punch_hole(gt, mode=mode, frac=0.12, seed=seed)
    except ValueError as e:
        return {"skipped": True, "reason": str(e)}
    holed = gt.copy()
    holed[mask] = 0
    t0 = time.time()
    recon = fill_lama(holed, mask, lama)
    dt = time.time() - t0
    s = score(recon, gt, mask)
    s["pass"] = passes(s)
    content = gt[..., 3] > 8
    s_1b = score_1b(recon, mask, content, mode=mode)
    s_1b["pass"] = passes_1b(s_1b, mode) if s_1b["applicable"] else None
    s["1b"] = s_1b
    s["seconds"] = round(dt, 2)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        save_rgba(os.path.join(out_dir, f"{base}_{mode}_lama.png"), recon)
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--modes", nargs="+", default=["interior"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    from simple_lama_inpainting import SimpleLama
    print("loading LaMa model (downloads big-lama.pt on first run)...", file=sys.stderr)
    t0 = time.time()
    lama = SimpleLama()
    print(f"model ready in {time.time()-t0:.1f}s", file=sys.stderr)

    report = {}
    for path in a.images:
        for mode in a.modes:
            key = f"{os.path.basename(path)}::{mode}"
            report[key] = run_case(path, mode, a.seed, lama, a.out)
            print(f"{key}: {json.dumps(report[key], ensure_ascii=False)}", file=sys.stderr)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
