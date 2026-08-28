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


def _find_layer(psd, layer_name):
    layers = [l for l in psd.descendants() if not l.is_group() and l.is_visible()]
    layer = next((l for l in layers if l.name == layer_name), None)
    if layer is None:
        raise ValueError(f"找不到圖層 {layer_name!r}(可見 leaf 圖層:{[l.name for l in layers]})")
    return layer


def patch_layer_with_image(psd_path, layer_name, patched_local_rgba, out_path):
    """把一張已經修好的局部(裁切座標)RGBA 圖,寫回 PSD 內同名圖層的原本全域位置與 z 序。
    這是給「已經在別處產生補圖結果」的呼叫端用的通用函式;patched_local_rgba 必須跟
    原圖層同尺寸(topil() 的裁切座標系),否則位置對不上。"""
    psd = PSDImage.open(psd_path)
    layer = _find_layer(psd, layer_name)
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
    layer = _find_layer(psd, layer_name)
    local_gt = np.array(layer.topil().convert("RGBA")).astype(np.float64)
    holed, mask = ie.punch_hole(local_gt, mode=mode, frac=0.12, seed=seed)
    fill_fn = ie.METHODS[method]
    patched = fill_fn(holed, local_gt, mask)
    return patch_layer_with_image(psd_path, layer_name, patched, out_path)


# ---------- 評分→採用→落地(打通完整鏈路,見 STATE_S4.md 候選 1) ----------
#
# demo_hole_patch()/patch_layer_with_image() 是「呼叫端已經決定好要用哪個 baseline」的
# 半成品鏈路。這裡補上中間那段:真實補圖沒有真值,沒辦法用 inpaint_eval 的 1a(比真值)
# 分數挑 baseline —— 只能用 1b(自我參照)分數盲選。patch_layer_auto() 給真實情境用
# (呼叫端提供實際缺洞 mask);demo_auto_patch() 是這條鏈路自己的評估器:合成挖洞模擬
# 「盲選」情境(選擇邏輯全程不碰 gt),寫回後才用 gt 算 1a 分數「揭曉」盲選挑得好不好
# ——這個揭曉步驟只存在於自我測試,真實補圖沒有 gt 可揭曉。

def patch_layer_auto(psd_path, layer_name, mask, out_path, mode="interior",
                      methods=ie.CANDIDATE_METHODS):
    """真實情境:layer 目前的樣子(local RGBA)已經有個缺洞(如遮擋物拆除後露出的洞),
    呼叫端給出 mask(跟該層同尺寸的 bool/0-255 陣列,True/非0 = 要補的區域)。
    跑候選 baseline → 用 1b 分數盲選 → 寫回同一個 PSD。

    `mode`:呼叫端必須明確指出這個洞是 "interior"(完全落在件內部,如遮擋件蓋住角色身上
    某處)還是 "edge"(洞跨在件的真實輪廓邊界上,如遮擋件本身就定義部分輪廓)——這無法
    從 mask 本身自動判斷可靠地推出,1b 的自我參照假設只在 interior 校準過(見
    knowledge/s4-inpaint-1b-lenient-gate.md);傳錯會讓 edge 洞被誤判為有信心的 pass_1b。"""
    psd = PSDImage.open(psd_path)
    layer = _find_layer(psd, layer_name)
    local_rgba = np.array(layer.topil().convert("RGBA")).astype(np.float64)
    mask = np.asarray(mask).astype(bool)
    if mask.shape != local_rgba.shape[:2]:
        raise ValueError(f"mask 尺寸 {mask.shape} 跟圖層 {local_rgba.shape[:2]} 不符")

    scored = ie.score_candidates(local_rgba, mask, methods)
    chosen, reason = ie.select_best(scored, priority=methods, applicable=(mode == "interior"))
    result = patch_layer_with_image(psd_path, layer_name, scored[chosen]["recon"], out_path)
    result["mode"] = mode
    result["chosen_method"] = chosen
    result["chosen_reason"] = reason
    result["candidate_1b_scores"] = {k: v["score"] for k, v in scored.items()}
    return result


def demo_auto_patch(psd_path, layer_name, mode, seed, out_path, methods=ie.CANDIDATE_METHODS):
    """本鏈路的評估器:合成挖洞模擬『真實無真值』情境,盲選(選擇邏輯不碰 gt,且照
    knowledge/s4-inpaint-1b-lenient-gate.md 的範圍收斂只在 interior 模式信任 1b pass)後
    寫回,再用 gt 算選中結果的 1a 分數當驗收(僅測試用途,證明盲選沒有選到明顯比其他候選
    差的 baseline;不能拿來當真實補圖的信心來源,因為真實情境本來就沒有 gt 可比)。"""
    psd = PSDImage.open(psd_path)
    layer = _find_layer(psd, layer_name)
    gt = np.array(layer.topil().convert("RGBA")).astype(np.float64)
    holed, mask = ie.punch_hole(gt, mode=mode, frac=0.12, seed=seed)

    scored = ie.score_candidates(holed, mask, methods)
    chosen, reason = ie.select_best(scored, priority=methods, applicable=(mode == "interior"))
    result = patch_layer_with_image(psd_path, layer_name, scored[chosen]["recon"], out_path)
    result["mode"] = mode
    result["chosen_method"] = chosen
    result["chosen_reason"] = reason
    result["candidate_1b_scores"] = {k: v["score"] for k, v in scored.items()}

    reveal_1a = ie.score(scored[chosen]["recon"], gt, mask)
    result["reveal_1a_score_of_chosen"] = reveal_1a
    result["reveal_1a_pass"] = ie.passes(reveal_1a)
    result["reveal_note"] = "此欄位僅自我測試用,真實補圖無 gt 可揭曉,不會出現在 patch_layer_auto() 的輸出"
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("psd")
    ap.add_argument("layer", help="要補的圖層名(需與 PSD 內可見 leaf 圖層名完全相符)")
    ap.add_argument("--mode", choices=["interior", "edge"], default="interior",
                     help="僅 --demo-hole 系列(合成挖洞)用")
    ap.add_argument("--method", choices=list(ie.METHODS.keys()), default="cv2_ns",
                     help="固定指定單一 baseline(合成挖洞示範用,見 demo_hole_patch)")
    ap.add_argument("--auto", action="store_true",
                     help="評分→採用→落地鏈路(自我測試):合成挖洞模擬無真值情境,"
                          "用 1b 分數盲選候選 baseline 後寫回,並揭曉盲選的 1a 分數驗證選得好不好")
    ap.add_argument("--mask", default=None,
                     help="真實情境:一張跟該圖層同尺寸的遮罩 PNG(非0=要補的洞),"
                          "用 1b 分數盲選候選 baseline 後寫回;與 --auto 互斥")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--out", required=True, help="輸出 PSD 路徑(不覆蓋原檔)")
    ap.add_argument("--eval", action="store_true",
                     help="patch 完後立刻跑 psd_slice.evaluate() 自驗座標系/重組是否一致")
    a = ap.parse_args()

    if a.mask and a.auto:
        raise SystemExit("--mask 與 --auto 互斥(前者真實情境,後者合成自測)")

    if a.mask:
        from PIL import Image as _Image
        mask = np.array(_Image.open(a.mask).convert("L")) > 8
        report = patch_layer_auto(a.psd, a.layer, mask, a.out, mode=a.mode)
    elif a.auto:
        report = demo_auto_patch(a.psd, a.layer, a.mode, a.seed, a.out)
    else:
        report = demo_hole_patch(a.psd, a.layer, a.mode, a.method, a.seed, a.out)
    if a.eval:
        report["slice_eval"] = slice_evaluate(a.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
