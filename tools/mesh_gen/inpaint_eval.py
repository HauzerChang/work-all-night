#!/usr/bin/env python3
"""S4 補圖閘 v1 — 合成真值法(挖洞→補→比對),含正/負對照自校準,純 CPU。

方法(見 handoff_S4.md §4):取一個完整件(RGBA) 當真值 → 人工挖洞(模擬動畫露出被遮區後的破洞)
→ 用補圖 baseline 補 → 與真值比對。**先跑正/負對照校準指標本身,再信任 baseline 的 pass/fail**
(記取主排程 S2/S4 三次 miscalibration 教訓:premultiplied 比對、負對照先確認鑑別力)。

三項指標(洞區內):
  - premult_mae   : premultiplied-RGB 平均絕對誤差(0~255 尺度;透明區不誤判)
  - alpha_mae     : alpha 平均絕對誤差
  - seam_grad_diff: 洞邊界環狀帶的梯度強度差(補丁與真實接縫是否突兀)
  - ssim          : 洞區窗口化結構相似度(premultiplied 灰階,無 skimage 依賴,自實作)

正對照(補=真值本身)驗證指標無偏(應 ≈ 完美);負對照(洞維持透明 / 填隨機噪聲)驗證鑑別力
(應明顯劣化)。兩者都過才信任 baseline 的判定。
"""
import argparse, json, os
import numpy as np
import cv2
from scipy import ndimage


# ---------- I/O ----------

def load_rgba(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    if im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    b, g, r, a = cv2.split(im)
    return cv2.merge([r, g, b, a]).astype(np.float64)


def save_rgba(path, rgba):
    r, g, b, a = cv2.split(np.clip(rgba, 0, 255).astype(np.uint8))
    cv2.imwrite(path, cv2.merge([b, g, r, a]))


# ---------- 挖洞(合成真值的破洞) ----------

def punch_hole(rgba, mode="interior", frac=0.12, seed=0):
    """在 alpha>8 的內容區挖洞,回傳 (holed_rgba, mask)。
    mode=interior: 洞完全落在內容內部(模擬件中段被別的件遮住,露出時要補『內插』)。
    mode=edge:     洞咬到內容輪廓邊界(模擬邊緣被裁掉,補圖要『外推』,較難)。"""
    H, W = rgba.shape[:2]
    content = rgba[..., 3] > 8
    ys, xs = np.where(content)
    if len(ys) == 0:
        raise ValueError("empty alpha, cannot punch hole")
    rng = np.random.RandomState(seed)
    area = content.sum()
    r = max(3, int(np.sqrt(area * frac / np.pi)))
    yy, xx = np.mgrid[0:H, 0:W]

    if mode == "interior":
        # 距輪廓 >= r 的內部點才當圓心,確保洞不碰邊界
        dist = ndimage.distance_transform_edt(content)
        cand_y, cand_x = np.where(dist >= r * 1.15)
        if len(cand_y) == 0:
            # 材質太薄(環形/細長件),原本這裡退化成「用任意內容點當圓心」(cand_y,cand_x=ys,xs),
            # 但這樣完全不保證洞真的落在內部——挖出來的洞其實貼著/跨過輪廓,卻被標成
            # "interior",汙染下游校準(見 knowledge/s4-inpaint-tone-gap-limits.md,框.png 案例)。
            # 改法:先試著縮小洞去符合真正的 margin;縮到底仍不夠,就明確報錯而非產出假的 interior 洞。
            max_margin = float(dist.max())
            r = max(3, int(max_margin / 1.15))
            cand_y, cand_x = np.where(dist >= r * 1.15)
            if max_margin < 4.5 or len(cand_y) == 0:
                raise ValueError(
                    f"content too thin for a fair interior hole (max margin {max_margin:.1f}px "
                    f"< required {r * 1.15:.1f}px) — this material's interior is too thin/ring-shaped "
                    f"for interior-mode punch_hole; use mode='edge' or skip this case")
        i = rng.randint(len(cand_y))
        oy, ox = cand_y[i], cand_x[i]
        mask = ((yy - oy) ** 2 + (xx - ox) ** 2) <= r * r
    elif mode == "edge":
        # 從輪廓上的點當圓心,洞會跨進跨出邊界(邊界外的部分自然被 & content 濾掉)
        boundary = content & ~ndimage.binary_erosion(content, iterations=2)
        by, bx = np.where(boundary)
        i = rng.randint(len(by))
        oy, ox = by[i], bx[i]
        mask = ((yy - oy) ** 2 + (xx - ox) ** 2) <= (r * 1.4) ** 2
    else:
        raise ValueError(f"unknown mode {mode}")

    mask = mask & content
    holed = rgba.copy()
    holed[mask] = 0
    return holed, mask


# ---------- 補圖 baseline ----------

def fill_ground_truth(rgba_holed, gt, mask):
    """正對照:直接拿真值填洞(驗證指標本身應給出近乎完美分數)。"""
    out = rgba_holed.copy()
    out[mask] = gt[mask]
    return out


def fill_none(rgba_holed, gt, mask):
    """負對照 A:完全不補,洞維持透明。"""
    return rgba_holed.copy()


def fill_random(rgba_holed, gt, mask, seed=1):
    """負對照 B:洞內填隨機噪聲(不透明),驗證指標能抓出『亂補』。"""
    rng = np.random.RandomState(seed)
    out = rgba_holed.copy()
    n = int(mask.sum())
    out[..., :3][mask] = rng.randint(0, 256, size=(n, 3))
    out[..., 3][mask] = 255
    return out


def estimate_alpha_taper(alpha_holed, mask):
    """洞區 alpha 漸縮估計(距離場×局部量測寬度),取代「洞內強制拉滿不透明」。

    背景(見 knowledge/s4-inpaint-evaluator.md「額外發現」):`edge` 洞跨出真實輪廓時,強制
    alpha=255 對柔和邊緣(如光暈的放射漸層)明顯錯誤(alpha_mae 28~42)。但直接嘗試的兩個替代
    方案都更差:(1) 對 alpha 通道整顆跑 `cv2.inpaint` 會把附近背景的 0 值大範圍擴散進洞內,連
    洞中段本該不透明的像素都被拉低(光暈 edge alpha_mae 41.8→72.5,硬邊材質身體/左手更慘,
    4~6→122~137);(2) 對 alpha 做單點最近鄰外推(`fill_nearest` 原本的作法)會抓到緊貼真實
    輪廓的極薄 AA 邊緣像素(alpha 9~30)當「最近有效值」,把洞中段其實該接近 255 的硬邊材質
    像素誤判為接近透明(身體 edge alpha_mae 4.18→21.9,反而更差)。

    這裡改用「距離場 × 局部量測的漸縮寬度」:
    1. 洞外「已知背景」(alpha<=8)當 0 端錨點,量每個洞內像素到最近已知背景的距離 `d_bg`。
    2. 局部漸縮寬度 `ell` 不猜、從洞周圍**看得到的**真實邊緣量:在洞外環狀帶找「已知的
       AA 邊緣像素」(8<alpha<250),取它們的 alpha 空間梯度幅值中位數,`ell = 255/中位梯度`
       —— 材質邊緣本來就硬(身體/左手)量出的 ell≈2px,材質邊緣本來就軟(光暈)量出 ell≈32px,
       是量出來的材質屬性而非固定假設。
    3. `alpha_est = clip(255 * d_bg / ell, 0, 255)`——深入內部(遠離背景)飽和到 255,
       貼近背景線性衰減到 0,衰減快慢跟隨量到的 `ell`。
    量化驗證(3 真實件 × interior/edge,見 log/s4-2026-08-28-008.md):interior 全 0 誤差
    (與舊法打平);edge 三件 alpha_mae 全面改善(光暈 41.8→8.6、身體 4.18→2.27、左手 5.55→2.98)。
    """
    known = ~mask
    bg_known = (alpha_holed <= 8) & known
    fringe_known = known & (alpha_holed > 8) & (alpha_holed < 250)

    # 洞內先用最近鄰暫填,只為了讓 sobel 梯度在洞邊界不因洞內恆 0 產生假邊緣;真正的洞內值
    # 之後整個被下面的距離場估計覆蓋,這裡的暫填值不會被採用。
    a_fill = alpha_holed.astype(np.float64).copy()
    if mask.any() and known.any():
        _, ind = ndimage.distance_transform_edt(~known, return_distances=True, return_indices=True)
        a_fill[mask] = alpha_holed[tuple(ind)][mask]

    grad = np.sqrt(ndimage.sobel(a_fill, axis=0) ** 2 + ndimage.sobel(a_fill, axis=1) ** 2) / 8.0
    ring = ndimage.binary_dilation(mask, iterations=15) & fringe_known
    if ring.sum() < 5:
        ring = fringe_known
    local_grad = float(np.median(grad[ring])) if ring.sum() else 255.0
    ell = 255.0 / max(local_grad, 1.0)

    d_bg = ndimage.distance_transform_edt(~bg_known) if bg_known.any() else np.full_like(alpha_holed, 1e6)
    return np.clip(255.0 * d_bg / ell, 0, 255)


def fill_nearest(rgba_holed, gt, mask):
    """Level 1:邊緣外擴 — 用最近有效像素(distance-transform nearest-fill)延伸填補,
    RGB 與 alpha 共用同一個最近鄰索引(不拆開來源)。純 CPU 最省,適合純色/漸層/規則紋理的小缺口。

    曾試過把 alpha 改成 `estimate_alpha_taper`(和 `fill_cv2_inpaint` 一樣),但會讓 RGB 與 alpha
    來自不同來源像素,對複雜拓樸(如 `框` 這種環形鏤空件)出現「RGB 對但 alpha 系統性偏移」的
    premultiplied 誤差,實測 `Symbol_Ww.psd::框` 的 `ssim` 從 0.775(PASS)掉到 0.452(FAIL)——
    真實的判定翻盤,故 Level 1 保留原本 RGB/alpha 同源的作法,taper 修正只用在
    `fill_cv2_inpaint`(該處 RGB 本就走獨立的 `cv2.inpaint` 通道,不存在「同源」可保留)。
    量化見 log/s4-2026-08-28-008.md。"""
    valid = (rgba_holed[..., 3] > 8) & (~mask)
    if not valid.any():
        return rgba_holed.copy()
    _, ind = ndimage.distance_transform_edt(~valid, return_distances=True, return_indices=True)
    filled = np.empty_like(rgba_holed)
    for c in range(4):
        filled[..., c] = rgba_holed[..., c][tuple(ind)]
    out = rgba_holed.copy()
    out[mask] = filled[mask]
    return out


def fill_cv2_inpaint(rgba_holed, mask, method="telea", radius=3):
    """Level 2:cv2.inpaint(Telea / Navier-Stokes)補 RGB,純 CPU,中等缺口/非結構性紋理。
    alpha 改用 `estimate_alpha_taper`(理由與量化見該函式 docstring;原本洞內強制拉滿不透明,
    對柔和邊緣材質明顯錯誤)。"""
    rgb = np.clip(rgba_holed[..., :3], 0, 255).astype(np.uint8)
    m = (mask.astype(np.uint8)) * 255
    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    inpainted = cv2.inpaint(rgb, m, radius, flag)
    out = rgba_holed.copy()
    out[..., :3][mask] = inpainted[mask].astype(np.float64)
    out[..., 3][mask] = estimate_alpha_taper(rgba_holed[..., 3], mask)[mask]
    return out


METHODS = {
    "gt": fill_ground_truth,           # 正對照
    "none": fill_none,                 # 負對照 A
    "random": fill_random,             # 負對照 B
    "nearest": fill_nearest,           # Level 1
    "cv2_telea": lambda h, gt, m: fill_cv2_inpaint(h, m, "telea"),
    "cv2_ns": lambda h, gt, m: fill_cv2_inpaint(h, m, "ns"),
}


# ---------- 指標 ----------

def _premult(rgba):
    return rgba[..., :3] * (rgba[..., 3:4] / 255.0)


def premult_mae(a, b, region):
    if region.sum() == 0:
        return 0.0
    return float(np.abs(_premult(a) - _premult(b))[region].mean())


def alpha_mae(a, b, region):
    if region.sum() == 0:
        return 0.0
    return float(np.abs(a[..., 3] - b[..., 3])[region].mean())


def boundary_ring(mask, width=3):
    dil = ndimage.binary_dilation(mask, iterations=width)
    ero = ndimage.binary_erosion(mask, iterations=width)
    return dil & ~ero


def seam_gradient_diff(recon, gt, mask, width=3):
    """洞邊界環狀帶:補丁重建 vs 真值的梯度強度差。突兀接縫 → 值大。"""
    ring = boundary_ring(mask, width)
    if ring.sum() == 0:
        return 0.0

    def gradmag(img):
        gray = _premult(img).mean(axis=2)
        gx = ndimage.sobel(gray, axis=1)
        gy = ndimage.sobel(gray, axis=0)
        return np.sqrt(gx ** 2 + gy ** 2)

    g_recon = gradmag(recon)
    g_gt = gradmag(gt)
    return float(np.abs(g_recon - g_gt)[ring].mean())


def ssim_region(a, b, region, win=7):
    """窗口化 SSIM(premultiplied 灰階),自實作(環境無 skimage)。"""
    if region.sum() == 0:
        return 1.0
    ag = _premult(a).mean(axis=2)
    bg = _premult(b).mean(axis=2)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a = ndimage.uniform_filter(ag, win)
    mu_b = ndimage.uniform_filter(bg, win)
    va = ndimage.uniform_filter(ag * ag, win) - mu_a ** 2
    vb = ndimage.uniform_filter(bg * bg, win) - mu_b ** 2
    cov = ndimage.uniform_filter(ag * bg, win) - mu_a * mu_b
    num = (2 * mu_a * mu_b + C1) * (2 * cov + C2)
    den = (mu_a ** 2 + mu_b ** 2 + C1) * (va + vb + C2)
    ssim_map = num / den
    return float(ssim_map[region].mean())


def score(recon, gt, mask):
    return {
        "premult_mae": round(premult_mae(recon, gt, mask), 3),
        "alpha_mae": round(alpha_mae(recon, gt, mask), 3),
        "seam_grad_diff": round(seam_gradient_diff(recon, gt, mask), 3),
        "ssim": round(ssim_region(recon, gt, mask), 4),
    }


# ---------- 1b 防穿幫指標(自我參照,不比對真值內容 — 見 knowledge/s4-inpaint-taxonomy.md) ----------
#
# 1a(score/passes 上面那組)問「補得像不像真值」;1b 問「動態下會不會露餡」——
# 露餡不需要知道洞裡『本來』是什麼,只需要看:(1)洞內還有沒有透明殘留、(2)洞邊界的接縫
# 是否比這件『本來就有』的邊緣強度更突兀、(3)洞邊界內外的色調是否銜接。三者都是拿 recon
# 自己(以及它跟同一張圖其他正常區域的比較)算,不需要 gt 的洞內真實內容。

def _gradmag(img):
    gray = _premult(img).mean(axis=2)
    gx = ndimage.sobel(gray, axis=1)
    gy = ndimage.sobel(gray, axis=0)
    return np.sqrt(gx ** 2 + gy ** 2)


def boundary_bands(mask, width=3):
    """回傳緊貼洞邊界的內側帶(洞內)、外側帶(洞外,真實像素)。"""
    dil = ndimage.binary_dilation(mask, iterations=width)
    inside_band = mask & ~ndimage.binary_erosion(mask, iterations=width)
    outside_band = dil & ~mask
    return inside_band, outside_band


def score_1b(recon, mask, content, width=3):
    """1b 防穿幫指標(自我參照,無需真值洞內內容):
      - alpha_gap : 洞內仍是透明的像素比例(殘留破洞 → 一定穿幫)
      - seam_ratio: 洞邊界梯度強度 / 這件其餘正常區域(扣掉洞與邊界帶)的梯度基準
                    (該材質本來的邊緣強度)—— 遠高於 1 代表接縫比正常紋理邊緣更突兀。
      - tone_gap  : 洞邊界內帶 vs 外帶的平均 premultiplied 色差(銜接處色調斷不斷)。
    """
    if mask.sum() == 0:
        return {"alpha_gap": 0.0, "seam_ratio": 0.0, "tone_gap": 0.0}
    hole_alpha = recon[..., 3][mask]
    # 門檻沿用全檔一致的「content」定義(alpha>8),不能用較高的門檻(如 200)——
    # 天然軟邊素材(如光暈的放射漸層)在洞的邊界本就有 alpha 9~255 的漸層,曾誤把這種
    # 合法半透明當成「還沒補好的破洞」,靠 gt 正對照校準抓到後修正。
    alpha_gap = float((hole_alpha <= 8).mean())

    inside_band, outside_band = boundary_bands(mask, width)
    g = _gradmag(recon)
    band = inside_band | outside_band
    seam_grad = float(g[band].mean()) if band.sum() else 0.0
    normal_region = content & ~ndimage.binary_dilation(mask, iterations=width)
    baseline_grad = float(g[normal_region].mean()) if normal_region.sum() else 1e-6
    seam_ratio = seam_grad / max(baseline_grad, 1e-6)

    in_pix = _premult(recon)[inside_band]
    out_pix = _premult(recon)[outside_band]
    tone_gap = float(np.abs(in_pix.mean(axis=0) - out_pix.mean(axis=0)).mean()) \
        if len(in_pix) and len(out_pix) else 0.0

    return {"alpha_gap": round(alpha_gap, 4), "seam_ratio": round(seam_ratio, 3),
            "tone_gap": round(tone_gap, 3)}


# ---------- AC 判定(先校準,見 §main) ----------

# 校準後閾值(見 knowledge/s4-inpaint-evaluator.md):正對照必須遠優於此、負對照必須遠劣於此,
# baseline 落在中間帶依此判定「CPU 補得動」。
THRESH = {"premult_mae": 18.0, "ssim": 0.75, "seam_grad_diff": 12.0}

# 1b 閾值(見 knowledge/s4-inpaint-1b-lenient-gate.md,以正對照=gt 自身/負對照=none/random 校準):
# alpha_gap 用嚴格 0(殘留透明就是看得見的洞,無寬鬆空間);seam/tone 給比 1a 寬鬆的容忍帶。
THRESH_1B = {"alpha_gap": 0.02, "seam_ratio": 2.2, "tone_gap": 28.0}


def passes(s):
    return s["premult_mae"] < THRESH["premult_mae"] and s["ssim"] > THRESH["ssim"] \
        and s["seam_grad_diff"] < THRESH["seam_grad_diff"]


def passes_1b(s):
    return s["alpha_gap"] <= THRESH_1B["alpha_gap"] and s["seam_ratio"] < THRESH_1B["seam_ratio"] \
        and s["tone_gap"] < THRESH_1B["tone_gap"]


# ---------- 評分→採用(供 psd_inplace_patch.py 落地鏈路呼叫) ----------
#
# 真實補圖(非本檔的合成校準流程)沒有真值可比 —— 這正是 1b 自我參照指標存在的理由
# (見上面 taxonomy 說明)。這裡提供「拿候選 baseline 跑過 → 用 1b 分數盲選」的共用邏輯,
# 讓 psd_inplace_patch.py 不必重新發明選擇規則,也讓校準(demo,盲選後才用 gt 算 1a 驗證
# 選得好不好)與真實落地走同一套函式。

CANDIDATE_METHODS = ("nearest", "cv2_telea", "cv2_ns")  # 不含 gt/none/random(僅供對照,不可採用)


def score_candidates(holed_rgba, mask, methods=CANDIDATE_METHODS):
    """對『已存在缺洞、無真值』的件跑每個候選 baseline,各自算 1b 自我參照分數。
    回傳 {method: {"recon": ndarray, "score": {...,"pass":bool}}}。
    注意:1b 分數本身不知道這個洞是 interior 還是 edge——`pass` 欄位一律照 THRESH_1B 算出,
    呼叫端(select_best)必須自己傳 applicable 旗標做 gating,不能對 edge 洞照單全收。"""
    content = holed_rgba[..., 3] > 8
    out = {}
    for name in methods:
        fn = METHODS[name]
        recon = fn(holed_rgba, None, mask)  # 真實情境無 gt;三個候選 baseline 本就不吃 gt 參數
        s = score_1b(recon, mask, content)
        s["pass"] = passes_1b(s)
        out[name] = {"recon": recon, "score": s}
    return out


def select_best(scored, priority=CANDIDATE_METHODS, applicable=True):
    """從 score_candidates() 結果挑一個採用。

    `applicable`:1b 的自我參照假設(洞周圍本來沒有接縫)只在洞完全落在件內部(interior)
    時成立——若洞跨在件的真實輪廓邊界上(edge,如遮擋件本身定義部分輪廓),輪廓天然的
    tone/alpha 漸變會讓正對照自己都被誤判成『有接縫』(見 knowledge/s4-inpaint-1b-lenient-gate.md
    校準記錄)。呼叫端必須依情境明確傳入這個旗標(自動判斷不可靠,故不在此處猜測)——
    `applicable=False` 時,即使個別候選的 score["pass"]==True 也一律忽略,不會回傳 "pass_1b"
    (那個 True 在 edge 情境下沒有校準過的意義),永遠走 fallback。

    優先序中第一個 1b pass 的入選;若全 fail 或 applicable=False,退而求其次選
    seam_ratio(接縫突兀度)最低者,並標記 no_pass_fallback,讓呼叫端知道這不是有信心的判定。"""
    if applicable:
        for name in priority:
            if scored[name]["score"]["pass"]:
                return name, "pass_1b"
    best = min(scored, key=lambda n: scored[n]["score"]["seam_ratio"])
    reason = "no_pass_fallback_lowest_seam_ratio" if applicable \
        else "1b_not_applicable_edge_mode_fallback_lowest_seam_ratio"
    return best, reason


# ---------- 主流程 ----------

def run_one(path, mode, seed, out_dir=None):
    gt = load_rgba(path)
    try:
        holed, mask = punch_hole(gt, mode=mode, frac=0.12, seed=seed)
    except ValueError as e:
        # 材質太薄/太小裝不下合乎規範的洞(見 punch_hole 的 margin 檢查)——標成 skipped
        # 而非讓整批評測 crash,也不要偽造一個不合規範的洞去產出誤導性數字。
        return {"skipped": True, "reason": str(e)}
    base = os.path.splitext(os.path.basename(path))[0]
    files = {}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        files["original"] = f"{base}_{mode}_original.png"
        files["holed"] = f"{base}_{mode}_holed.png"
        save_rgba(os.path.join(out_dir, files["original"]), gt)
        save_rgba(os.path.join(out_dir, files["holed"]), holed)
    content = gt[..., 3] > 8
    # 1b(防穿幫)的自我參照假設是「洞周圍本來就沒有接縫」,只在 interior 洞成立——
    # edge 洞刻意跨在真實輪廓上,輪廓本身天然就有 tone/alpha 漸變,正對照(gt)在此處
    # 會被自己的判定誤判為「有接縫」(見 knowledge/s4-inpaint-1b-lenient-gate.md 校準記錄)。
    # 故 1b 判定只在 interior 模式下啟用;edge 模式僅記錄分數供參考,pass 標 None(不適用)。
    b1_applicable = (mode == "interior")
    results = {}
    for name, fn in METHODS.items():
        recon = fn(holed, gt, mask)
        s = score(recon, gt, mask)
        s["pass"] = passes(s)
        s_1b = score_1b(recon, mask, content)
        s_1b["pass"] = passes_1b(s_1b) if b1_applicable else None
        s_1b["applicable"] = b1_applicable
        s["1b"] = s_1b
        if out_dir:
            fname = f"{base}_{mode}_{name}.png"
            save_rgba(os.path.join(out_dir, fname), recon)
            s["file"] = fname
        results[name] = s
    return {"hole_px": int(mask.sum()), "content_px": int((gt[..., 3] > 8).sum()),
            "files": files, "methods": results}


def calibration_check(report):
    """正對照必須近乎完美(驗證指標無偏);兩個負對照必須明顯 fail(驗證鑑別力)。
    1a、1b 各自校準(1b 正對照 = gt 的 1b 分數本身應接近完美 —— 因為真實內容『本來就沒有接縫』;
    1b 負對照沿用同一組 none/random)。未通過 → 整份報告不可信(呼應 RULES.md 教訓:先校準才能信判定)。"""
    ok = True
    notes = []
    for case_name, case in report["cases"].items():
        if case.get("skipped"):
            notes.append(f"{case_name}: 略過(材質不適用,見 reason)— {case['reason']}")
            continue
        gt_s = case["methods"]["gt"]
        if gt_s["premult_mae"] > 0.5 or gt_s["ssim"] < 0.999:
            ok = False
            notes.append(f"{case_name}: 正對照(gt)1a 未達完美,指標可能有偏 — {gt_s}")
        gt_1b = gt_s["1b"]
        if gt_1b["applicable"] and not gt_1b["pass"]:
            ok = False
            notes.append(f"{case_name}: 正對照(gt)1b 竟然 fail(真實內容不該有接縫)— {gt_1b}")
        for neg in ("none", "random"):
            neg_s = case["methods"][neg]
            if neg_s["pass"]:
                ok = False
                notes.append(f"{case_name}: 負對照 {neg} 1a 竟然 pass — 鑑別力不足,閾值需重調")
            if neg_s["1b"]["applicable"] and neg_s["1b"]["pass"]:
                ok = False
                notes.append(f"{case_name}: 負對照 {neg} 1b 竟然 pass — 鑑別力不足,閾值需重調")
    return ok, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("images", nargs="+", help="RGBA PNG 件(如切件輸出)")
    ap.add_argument("--modes", nargs="+", default=["interior", "edge"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--out", default=None, help="輸出補圖結果 PNG 的目錄(選填)")
    a = ap.parse_args()

    report = {"cases": {}}
    for path in a.images:
        for mode in a.modes:
            key = f"{os.path.basename(path)}::{mode}"
            report["cases"][key] = run_one(path, mode, a.seed, a.out)

    calib_ok, calib_notes = calibration_check(report)
    report["calibration"] = {"pass": calib_ok, "notes": calib_notes}
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(report, open(os.path.join(a.out, "manifest.json"), "w"),
                  ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if calib_ok else 1)


if __name__ == "__main__":
    main()
