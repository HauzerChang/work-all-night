#!/usr/bin/env python3
"""S4 補圖候選 14 —— `estimate_alpha_taper` 大樣本數下的獨立失敗模式(見 STATE_S4.md 候選 14,
`knowledge/s4-inpaint-alpha-taper-robustness.md` 末段的誠實範圍界定)。

背景:候選 13 修好了「ring_count 太小、中位數統計不穩」的縫隙(min_ring 5→20),但同一批
1233 筆量化資料裡,還有一批 `ring_count` 早已遠超任何合理門檻(50~700+)、樣本數本身足夠,
alpha_mae 卻依然崩壞到 90~140 的案例,`min_ring` 對這批完全無效。本檔追查這批案例的根因,
嘗試修法,並誠實記錄「哪些嘗試有效、哪些沒有」。

## 根因一:「材質內部紋理雜訊」污染 ring 中位數(以 `右手` edge 小洞為代表案例)

`fringe_known = (alpha>8)&(alpha<250)` 這個判定式假設「非全透明也非全不透明」就是「邊界漸縮
帶」,但真實美術圖的材質內部本身可能有輕微 alpha 紋理(高光/材質細節),局部 alpha 在 240~255
之間跳動而完全不在任何邊界漸縮帶上。對硬邊材質(如 `右手`),這種內部紋理雜訊在 15px 環內的
數量可能遠超真正的邊界 AA 像素(實測 271 個環內樣本裡,180 個是「離背景 8~15px 遠、grad≈0.75
的紋理雜訊」,只有 55 個是「離背景 1~1.4px、grad≈110~125 的真邊界像素」)——中位數被雜訊
支配,把應該 ell≈2 的硬邊誤判成 ell≈27 的軟邊。

診斷方法:`diagnose_case()` 印出 ring 內每個樣本的 grad 值與到背景的距離,可重現這個雙峰分布。

## 根因二:局部線性漸縮模型本身對非線性材質失效(以 `光暈` 特定橢圓洞為代表案例)

`光暈`(放射狀光暈)的真實 alpha 衰減本身是非線性、隨位置變化的(核心陡、外圈平緩,呼應候選
10 的發現)。`estimate_alpha_taper` 假設「整個洞用同一個常數 ell 做線性外推」,當洞夠大、
橫跨衰減曲線差異很大的區域時,不管用什麼統計量(median/percentile/filter)去讀 ring 內的
局部斜率,都只能反映 ring 附近那一小段的局部斜率,無法代表洞深處(可能落在衰減曲線完全不同
路段)該有的斜率。量化證據:這批失敗案例的 ring 內樣本 grad 值本身全部偏低且高度一致
(如 `光暈` ellipse frac=0.15 aspect=2.0 案例,ring 內 90 百分位數也只有 2.02,max 僅 2.46),
不是「被雜訊污染」的雙峰分布,而是整段 ring 本來就量不到深處該有的陡峭斜率——這是模型結構性
限制,不是統計量選擇問題。

## 嘗試過的 4 種修法,量化結果(見 `main()` 的 `--sweep`,對全部 1233 筆案例逐一比較)

跑 `estimate_alpha_taper`(現行 production,min_ring=20,median)當基準,分別跟下列 4 種
候選比較全部案例的 mae 變化(fixed = 原本 >20 現在 <=20;newly_broken = 原本 <=20 現在 >20):

| 候選 | 描述 | fixed | newly_broken | 結論 |
|---|---|---|---|---|
| A. 距背景固定半徑過濾(dilate bg_known 4px) | 只留「离背景 <=4px」的環內樣本 | 修好右手案例(ell 27→1.93) | **對光暈這類寬漸縮材質災難性錯誤**(ring 直接變空,ring_f=0,因為光暈真正的漸縮帶本身就有 8~15px+ 寬,被判定式全部濾掉退回無樣本) | 拒絕:固定半徑無法對「漸縮寬度未知」的材質泛化 |
| B. 只換統計量(median→percentile) | 環內 grad 直接取 p75/p90/p95/p99 而非 median | p90:13 fixed | p90:9 newly_broken(如 `光暈 edge circle` 家族從 8~13 惡化到 20~24) | 拒絕:全域改統計量對雜訊案例有效,但對「本來就一致偏低」的軟材質環,percentile 反而放大單一離群陡峭像素的影響,製造新的假陽性 |
| C. 只做方向濾波(梯度方向需與「離開背景」方向對齊,cos>0.5) | 過濾掉方向與漸縮方向不一致的雜訊像素 | 部分改善(右手案例 271→139 樣本,中位數 9.3→13.7,仍未到位) | 未見於本表(不足以獨立解決,見下) | 拒絕:單獨使用鑑別力不足,右手案例仍有大量方向一致但實為雜訊的像素通過 |
| D. C+B 組合(方向濾波後取 p90) | 見上 | **13 fixed**(含右手 edge 案例 115.6→2.6、多個右手/光暈 ellipse 案例大幅改善) | **9 newly_broken**(全部落在 `光暈 edge circle` 家族與 `symbol::臉部陰影 edge circle seed=2`,mae 從 10~19 惡化到 20~25,壓線但確實跨過門檔) | **淨提升但非零回歸**(mean_mae 2.668→1.978,n_mae_gt_20 39→35),不符合本專案「零回歸」的落地門檻,故本次不採用為 production 預設 |

## 誠實結論(本次未修改 `inpaint_eval.py` production 代碼)

候選 14 其實是兩個獨立根因的合併症狀,不是同一個修法能一起解的單一問題:
- 根因一(材質內部紋理雜訊污染 ring 統計)**有找到淨提升的修法(D)**,但會在另一批目前
  PASS 的案例引入新的 FAIL(9 例,皆為壓線惡化到 20~25,不是災難性數字),violates 本專案
  一貫要求的「零回歸」落地門檻,故不直接套用為新預設。
- 根因二(光暈類非線性材質的局部線性模型結構性失效)**目前找不到任何统计量层面的修法**——
  這類材質需要不同的模型(如按洞內每點到最近已知邊界的方向分段擬合、或放棄常數 ell 假設,
  改用洞周圍多點局部斜率的空間內插而非單一全域值),超出本次調查範圍。

## 後續建議(留給下一個 chunk 或使用者裁決)

1. **A 類岔路候選**:candidate D(組合修法)是否要接受「9 例壓線新增 fail 換 13 例大幅改善」
   的 trade-off?這是一個主觀的品質門檻取捨,建議下次交給使用者一次性裁決(附本文件的量化表)。
2. 若要繼續往「零回歸」修法方向鑽研,下一步可嘗試:只在偵測到「ring 內 grad 值呈雙峰分布」
   (如 IQR/雙峰檢定)時才啟用候選 D 的過濾,其餘案例維持現行 median,避免對本來良好的軟材質
   案例引入變動。本檔尚未實作這個「自適應開關」版本。
3. 根因二(光暈非線性材質)建議另開新的候選,不與根因一混在一起追蹤。

## 檔案

- 本檔(`s4_alpha_taper_candidate14.py`):`diagnose_case()` 重現雙峰污染診斷;`sweep()` /
  `estimate_combined()` 重現上表的量化比較,可重跑驗證任何未來嘗試。
- 未修改:`tools/mesh_gen/inpaint_eval.py`(`estimate_alpha_taper` production 代碼維持不變,
  因為沒有候選修法達到零回歸門檻)。
"""
import argparse, time
import numpy as np
from scipy import ndimage
from psd_tools import PSDImage
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import leaf_layers
from inpaint_eval import punch_hole, estimate_alpha_taper
from real_occlusion_eval import layer_full_canvas

ROBOT_MATERIALS = ["光暈", "右手", "頭", "身體", "左手"]
SYMBOL_MATERIALS = ["底", "頭", "身體", "框", "臉部陰影", "wild", "墨鏡"]
CIRCLE_FRACS = [0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
ELLIPSE_ASPECTS = [1.5, 2.0, 2.5, 3.0]
ELLIPSE_FRACS = [0.06, 0.10, 0.15]
ELLIPSE_ANGLES = [0.0, np.pi / 4, np.pi / 2]


def load_materials():
    out = {}
    robot = PSDImage.open("assets/robot_parts.psd")
    for l in leaf_layers(robot):
        if l.name in ROBOT_MATERIALS:
            out[f"robot::{l.name}"] = layer_full_canvas(robot, l)
    symbol = PSDImage.open("assets/Symbol_Ww.psd")
    for l in leaf_layers(symbol):
        if l.name in SYMBOL_MATERIALS:
            out[f"symbol::{l.name}"] = layer_full_canvas(symbol, l)
    return out


def estimate_combined(alpha_holed, mask, min_ring=20, cos_thresh=0.5, pct=90):
    """候選 D:方向濾波(梯度方向須與「離開背景」方向對齊)後取 p90,而非全域中位數。
    見 module docstring 表格——淨提升但非零回歸,本次未採用為 production 預設。"""
    known = ~mask
    bg_known = (alpha_holed <= 8) & known
    fringe_known = known & (alpha_holed > 8) & (alpha_holed < 250)
    a_fill = alpha_holed.astype(np.float64).copy()
    if mask.any() and known.any():
        _, ind = ndimage.distance_transform_edt(~known, return_distances=True, return_indices=True)
        a_fill[mask] = alpha_holed[tuple(ind)][mask]
    gy = ndimage.sobel(a_fill, axis=0) / 8.0
    gx = ndimage.sobel(a_fill, axis=1) / 8.0
    grad_mag = np.sqrt(gy ** 2 + gx ** 2)
    ring = ndimage.binary_dilation(mask, iterations=15) & fringe_known
    if ring.sum() < min_ring:
        ring = fringe_known
    ry, rx = np.nonzero(ring)
    if bg_known.any() and len(ry):
        _, bg_ind = ndimage.distance_transform_edt(~bg_known, return_distances=True, return_indices=True)
        bgy = bg_ind[0][ry, rx]; bgx = bg_ind[1][ry, rx]
        dy = (ry - bgy).astype(np.float64); dx = (rx - bgx).astype(np.float64)
        n = np.sqrt(dy ** 2 + dx ** 2) + 1e-9; dy /= n; dx /= n
        gmag = grad_mag[ry, rx] + 1e-9
        cos_align = (gy[ry, rx] * dy + gx[ry, rx] * dx) / gmag
    else:
        cos_align = np.ones(len(ry))
    gvals = grad_mag[ry, rx]
    keep = cos_align > cos_thresh
    sel = gvals[keep] if keep.sum() >= 5 else gvals
    local_grad = float(np.percentile(sel, pct)) if len(sel) else 255.0
    ell = 255.0 / max(local_grad, 1.0)
    d_bg = ndimage.distance_transform_edt(~bg_known) if bg_known.any() else np.full_like(alpha_holed, 1e6)
    return np.clip(255.0 * d_bg / ell, 0, 255)


def estimate_percentile(alpha_holed, mask, min_ring=20, pct=90):
    """候選 B:只換統計量(median→percentile),不做方向濾波。"""
    known = ~mask
    bg_known = (alpha_holed <= 8) & known
    fringe_known = known & (alpha_holed > 8) & (alpha_holed < 250)
    a_fill = alpha_holed.astype(np.float64).copy()
    if mask.any() and known.any():
        _, ind = ndimage.distance_transform_edt(~known, return_distances=True, return_indices=True)
        a_fill[mask] = alpha_holed[tuple(ind)][mask]
    grad = np.sqrt(ndimage.sobel(a_fill, axis=0) ** 2 + ndimage.sobel(a_fill, axis=1) ** 2) / 8.0
    ring = ndimage.binary_dilation(mask, iterations=15) & fringe_known
    if ring.sum() < min_ring:
        ring = fringe_known
    gvals = grad[ring]
    local_grad = float(np.percentile(gvals, pct)) if gvals.size else 255.0
    ell = 255.0 / max(local_grad, 1.0)
    d_bg = ndimage.distance_transform_edt(~bg_known) if bg_known.any() else np.full_like(alpha_holed, 1e6)
    return np.clip(255.0 * d_bg / ell, 0, 255)


def mae_in_mask(est, gt_alpha, mask):
    return float(np.mean(np.abs(est[mask] - gt_alpha[mask])))


def diagnose_case(materials, mat, mode, shape, frac, seed, aspect=1.0, angle=None):
    """重現根因一的雙峰污染診斷(預設案例 = 右手 edge circle frac=0.06 seed=1)。"""
    gt = materials[mat]
    holed, mask = punch_hole(gt, mode=mode, frac=frac, seed=seed, shape=shape, aspect=aspect, angle=angle)
    alpha_holed = holed[..., 3]
    known = ~mask
    bg_known = (alpha_holed <= 8) & known
    fringe_known = known & (alpha_holed > 8) & (alpha_holed < 250)
    a_fill = alpha_holed.astype(np.float64).copy()
    _, ind = ndimage.distance_transform_edt(~known, return_distances=True, return_indices=True)
    a_fill[mask] = alpha_holed[tuple(ind)][mask]
    grad = np.sqrt(ndimage.sobel(a_fill, axis=0) ** 2 + ndimage.sobel(a_fill, axis=1) ** 2) / 8.0
    ring = ndimage.binary_dilation(mask, iterations=15) & fringe_known
    ry, rx = np.nonzero(ring)
    gvals = grad[ry, rx]
    d_to_bg = ndimage.distance_transform_edt(~bg_known)[ry, rx]
    print(f"{mat} {mode} {shape} frac={frac} seed={seed}: ring={len(gvals)}")
    print(f"  grad: min={gvals.min():.2f} median={np.median(gvals):.2f} p90={np.percentile(gvals,90):.2f} max={gvals.max():.2f}")
    low = gvals < 2.0
    high = gvals > 50.0
    print(f"  low-grad(<2) samples: {low.sum()}, mean dist-to-bg={d_to_bg[low].mean() if low.any() else float('nan'):.2f}")
    print(f"  high-grad(>50) samples: {high.sum()}, mean dist-to-bg={d_to_bg[high].mean() if high.any() else float('nan'):.2f}")
    old_mae = mae_in_mask(estimate_alpha_taper(alpha_holed, mask), gt[..., 3], mask)
    new_mae = mae_in_mask(estimate_combined(alpha_holed, mask), gt[..., 3], mask)
    print(f"  mae: production(median)={old_mae:.3f}  candidate-D(direction+p90)={new_mae:.3f}")


def sweep(materials, estimator):
    rows = {}
    for mat_name, gt in materials.items():
        for mode in ("interior", "edge"):
            for frac in CIRCLE_FRACS:
                for seed in range(3):
                    try:
                        holed, mask = punch_hole(gt, mode=mode, frac=frac, seed=seed, shape="circle")
                    except ValueError:
                        continue
                    est = estimator(holed[..., 3], mask)
                    rows[(mat_name, mode, "circle", frac, 1.0, None, seed)] = mae_in_mask(est, gt[..., 3], mask)
        for aspect in ELLIPSE_ASPECTS:
            for frac in ELLIPSE_FRACS:
                for angle in ELLIPSE_ANGLES:
                    for seed in range(3):
                        try:
                            holed, mask = punch_hole(gt, mode="interior", frac=frac, seed=seed, shape="ellipse",
                                                      aspect=aspect, angle=angle)
                        except ValueError:
                            continue
                        est = estimator(holed[..., 3], mask)
                        rows[(mat_name, "interior", "ellipse", frac, aspect, round(angle, 3), seed)] = \
                            mae_in_mask(est, gt[..., 3], mask)
    return rows


def compare(old, new, label):
    n_high_old = sum(1 for v in old.values() if v > 20)
    n_high_new = sum(1 for v in new.values() if v > 20)
    print(f"\n=== {label} vs production ===")
    print(f"n_mae_gt_20: old={n_high_old} new={n_high_new}; "
          f"mean_mae old={np.mean(list(old.values())):.3f} new={np.mean(list(new.values())):.3f}")
    fixed = [(k, old[k], new[k]) for k in old if old[k] > 20 and new[k] <= 20]
    broken = [(k, old[k], new[k]) for k in old if old[k] <= 20 and new[k] > 20]
    print(f"fixed (was>20 now<=20): {len(fixed)}")
    for f in sorted(fixed, key=lambda x: -x[1])[:20]:
        print("   ", f)
    print(f"newly broken (was<=20 now>20): {len(broken)}")
    for b in sorted(broken, key=lambda x: -x[2])[:20]:
        print("   ", b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="跑全部 1233 案例,比較 percentile/combined 兩候選 vs production")
    ap.add_argument("--diagnose", action="store_true", help="重現右手 edge 案例的雙峰污染診斷")
    args = ap.parse_args()

    materials = load_materials()

    if args.diagnose or not args.sweep:
        diagnose_case(materials, "robot::右手", "edge", "circle", 0.06, 1)

    if args.sweep:
        t0 = time.time()
        rows_old = sweep(materials, estimate_alpha_taper)
        print(f"production sweep done in {time.time()-t0:.1f}s, n={len(rows_old)}")
        t0 = time.time()
        rows_pct = sweep(materials, estimate_percentile)
        print(f"percentile(B) sweep done in {time.time()-t0:.1f}s")
        t0 = time.time()
        rows_combined = sweep(materials, estimate_combined)
        print(f"combined(D) sweep done in {time.time()-t0:.1f}s")

        compare(rows_old, rows_pct, "candidate B (percentile only)")
        compare(rows_old, rows_combined, "candidate D (direction filter + percentile)")


if __name__ == "__main__":
    main()
