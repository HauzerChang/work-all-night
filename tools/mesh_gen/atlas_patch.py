#!/usr/bin/env python3
"""atlas_crop.py 的逆操作:把補好的 region 貼回 atlas 貼圖頁(供候選16路徑(b)使用)。

同一份 xy/size/rotate 幾何規則(見 atlas_crop.py 開頭註解),只是方向相反:
  - rotate=false:canonical patched 影像(shape=(h,w,4))直接貼回 sheet[y:y+h, x:x+w]。
  - rotate=true :atlas_crop.crop_region 用『CW 還原』把 sheet 上 (w,h) 的存放方塊轉正成
    canonical (h,w)。貼回要做反方向:canonical (h,w) --CCW--> 存放方塊 (w,h),
    再寫回 sheet[y:y+w, x:x+h]。CCW 是 90° CW 的精確反旋轉(純像素重排、無插值),
    不會像一般縮放旋轉那樣產生誤差。
"""
import os
import cv2
import numpy as np

from atlas_crop import parse_atlas, crop_region


def paste_region(sheet, region, patched_canonical):
    """回傳貼回 patched_canonical 後的新 sheet(不修改原陣列)。

    patched_canonical: RGBA/BGRA ndarray,shape 必須等於該 region 的 canonical 尺寸
    (rotate=false 時 = (h,w,4);rotate=true 時 = (h,w,4),h,w 取自 region['size']
    的『原始(未旋轉)』寬高,即 atlas_crop.crop_region() 還原後的輸出 shape)。
    """
    x, y = [int(t) for t in region["xy"].split(",")]
    w, h = [int(t) for t in region["size"].split(",")]
    rot = region.get("rotate", "false") in ("true", "90")
    out = sheet.copy()
    if rot:
        expect = (h, w)
        if patched_canonical.shape[:2] != expect:
            raise ValueError(f"rotate region 需要 canonical shape {expect},收到 {patched_canonical.shape[:2]}")
        stored = cv2.rotate(patched_canonical, cv2.ROTATE_90_COUNTERCLOCKWISE)  # (h,w)->(w,h),CW 的精確反旋轉
        out[y:y + w, x:x + h] = stored
    else:
        expect = (h, w)
        if patched_canonical.shape[:2] != expect:
            raise ValueError(f"region 需要 canonical shape {expect},收到 {patched_canonical.shape[:2]}")
        out[y:y + h, x:x + w] = patched_canonical
    return out


def patch(atlas_path, page_dir, name, patched_canonical, out_page_path):
    """讀 region 所屬的 page(page_dir 找檔),貼回 patched_canonical,寫到 out_page_path。
    回傳實際讀取的來源 page 路徑,供呼叫端確認貼對頁。"""
    regions = parse_atlas(atlas_path)
    if name not in regions:
        raise SystemExit(f"region 不存在: {name}")
    r = regions[name]
    page = r.get("page")
    src = os.path.join(page_dir, page) if page else None
    if not src or not os.path.exists(src):
        raise SystemExit(f"找不到來源 page: {src}")
    sheet = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    if sheet is None:
        raise SystemExit(f"無法讀取 page: {src}")
    if sheet.shape[2] == 3:
        sheet = cv2.cvtColor(sheet, cv2.COLOR_BGR2BGRA)
    out = paste_region(sheet, r, patched_canonical)
    cv2.imwrite(out_page_path, out)
    return src


def _selftest(atlas_path, page_dir, names, out_dir):
    """自我驗證(不需要 spine 渲染):extract → 原封不動貼回 → 整頁與原檔逐位元比對,
    應為 0 差異(rotate=false/true 兩種幾何都測,證明 paste_region 是 crop_region 的精確逆操作)。"""
    os.makedirs(out_dir, exist_ok=True)
    regions = parse_atlas(atlas_path)
    all_ok = True
    for name in names:
        r = regions[name]
        page = r["page"]
        src = os.path.join(page_dir, page)
        sheet = cv2.imread(src, cv2.IMREAD_UNCHANGED)
        if sheet.shape[2] == 3:
            sheet = cv2.cvtColor(sheet, cv2.COLOR_BGR2BGRA)
        crop = crop_region(sheet, r)
        roundtrip = paste_region(sheet, r, crop)
        diff = np.abs(roundtrip.astype(np.int32) - sheet.astype(np.int32))
        max_diff = int(diff.max())
        ok = max_diff == 0
        all_ok = all_ok and ok
        print(f"{name}: rotate={r.get('rotate')} size={r['size']} page={page} "
              f"round-trip max_diff={max_diff} {'PASS' if ok else 'FAIL'}")
        out_path = os.path.join(out_dir, name.replace('/', '_') + "_roundtrip.png")
        cv2.imwrite(out_path, roundtrip)
    print("ALL PASS" if all_ok else "SOME FAILED")
    return all_ok


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        atlas_path, page_dir, out_dir = sys.argv[2], sys.argv[3], sys.argv[4]
        names = sys.argv[5:] or list(parse_atlas(atlas_path).keys())
        ok = _selftest(atlas_path, page_dir, names, out_dir)
        sys.exit(0 if ok else 1)
    atlas_path, page_dir, name, patched_png, out_page_path = sys.argv[1:6]
    canonical = cv2.imread(patched_png, cv2.IMREAD_UNCHANGED)
    if canonical.shape[2] == 3:
        canonical = cv2.cvtColor(canonical, cv2.COLOR_BGR2BGRA)
    src = patch(atlas_path, page_dir, name, canonical, out_page_path)
    print(f"{name}: 貼回 {src} 的內容 -> {out_page_path}")
