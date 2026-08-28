#!/usr/bin/env python3
"""S4 補圖 — 直接在 PSD 內編輯(而非對已匯出的裁切 PNG 編輯),確保切圖/補圖共用同一套
PSD 全域座標系(使用者要求,見 knowledge/s4-psd-inplace-edit.md)。

為什麼要在 PSD 裡編輯,不對匯出的單獨 PNG 編輯:
  每個切件 PNG 是「裁到該層 bbox」的局部座標(見 psd_slice.py 的 offset 記錄)。若對這張
  PNG 做補圖後,還要自己把結果貼回正確的 PSD 全域座標,等於重新發明一次 offset 換算——
  這正是 psd_slice.py 的 reassemble() 先前踩過的 bug 類型(見 log/s4-2026-08-28-003.md:
  負 offset 換算錯誤)。直接在 PSD 內編輯:讀某層原本的 (layer.left, layer.top) 當基準、
  patch 完的圖直接用同一組座標寫回去,座標系統一致性由 psd-tools 的 API 保證,不必自己算。

用法:
  python3 psd_inplace_patch.py <psd> <圖層名> --method cv2_ns --mode interior -o out.psd
  (--demo-hole 用合成挖洞測試 pipeline;實務補圖應改傳自己的已修補 PNG,見 patch_layer_with_image)
"""
import argparse, json
import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Tag

import inpaint_eval as ie
from psd_slice import evaluate as slice_evaluate


def _set_layer_name(layer, name):
    """psd-tools 寫入新圖層時,legacy Pascal-string 名稱預設用 macroman 編碼,
    中文/非 ASCII 名稱會直接 encode 失敗(UnicodeEncodeError)。真實 Photoshop PSD
    的作法是:legacy 欄位放隨意 ASCII 佔位、真正名稱寫進 Unicode Layer Name('luni')
    tagged block——讀取時一律以 luni 優先(psd-tools 的 .name 屬性也是如此)。
    這裡照同樣慣例寫,確保存出的 PSD 能被我方工具與真正 Photoshop 都正確讀到中文名。"""
    layer._record.name = "layer" if not name.isascii() else name
    layer._record.tagged_blocks.set_data(Tag.UNICODE_LAYER_NAME, name)


def patch_layer_with_image(psd_path, layer_name, patched_local_rgba, out_path):
    """把一張已經修好的局部(裁切座標)RGBA 圖,寫回 PSD 內同名圖層的原本全域位置與 z 序。
    這是給「已經在別處產生補圖結果」的呼叫端用的通用函式;patched_local_rgba 必須跟
    原圖層同尺寸(topil() 的裁切座標系),否則位置對不上。"""
    psd = PSDImage.open(psd_path)
    layers = [l for l in psd.descendants() if not l.is_group() and l.is_visible()]
    layer = next((l for l in layers if l.name == layer_name), None)
    if layer is None:
        raise ValueError(f"找不到圖層 {layer_name!r}(可見 leaf 圖層:{[l.name for l in layers]})")
    if patched_local_rgba.shape[:2] != (layer.height, layer.width):
        raise ValueError(f"patched 尺寸 {patched_local_rgba.shape[:2]} 跟原圖層 "
                          f"{(layer.height, layer.width)} 不符,座標系會對不上")

    g_left, g_top = layer.left, layer.top  # 全域座標,直接沿用,不必自己換算
    idx = psd.index(layer)
    psd.remove(layer)
    im = Image.fromarray(np.clip(patched_local_rgba, 0, 255).astype(np.uint8), "RGBA")
    new_layer = psd.create_pixel_layer(im, name=layer_name, top=g_top, left=g_left)
    _set_layer_name(new_layer, layer_name)
    psd.remove(new_layer)
    psd.insert(idx, new_layer)  # 保留原本 z 序位置

    psd.save(out_path)
    return {"layer": layer_name, "global_offset": [g_left, g_top], "z_index": idx, "out": out_path}


def demo_hole_patch(psd_path, layer_name, mode, method, seed, out_path):
    """示範/自我測試用:對某層合成挖洞 → 用既有 inpaint_eval baseline 補 → 寫回 PSD。
    重用 inpaint_eval 的挖洞/填補函式,不重新發明。"""
    psd = PSDImage.open(psd_path)
    layers = [l for l in psd.descendants() if not l.is_group() and l.is_visible()]
    layer = next((l for l in layers if l.name == layer_name), None)
    if layer is None:
        raise ValueError(f"找不到圖層 {layer_name!r}")
    local_gt = np.array(layer.topil().convert("RGBA")).astype(np.float64)
    holed, mask = ie.punch_hole(local_gt, mode=mode, frac=0.12, seed=seed)
    fill_fn = ie.METHODS[method]
    patched = fill_fn(holed, local_gt, mask)
    return patch_layer_with_image(psd_path, layer_name, patched, out_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("psd")
    ap.add_argument("layer", help="要補的圖層名(需與 PSD 內可見 leaf 圖層名完全相符)")
    ap.add_argument("--mode", choices=["interior", "edge"], default="interior")
    ap.add_argument("--method", choices=list(ie.METHODS.keys()), default="cv2_ns")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--out", required=True, help="輸出 PSD 路徑(不覆蓋原檔)")
    ap.add_argument("--eval", action="store_true",
                     help="patch 完後立刻跑 psd_slice.evaluate() 自驗座標系/重組是否一致")
    a = ap.parse_args()

    report = demo_hole_patch(a.psd, a.layer, a.mode, a.method, a.seed, a.out)
    if a.eval:
        report["slice_eval"] = slice_evaluate(a.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
