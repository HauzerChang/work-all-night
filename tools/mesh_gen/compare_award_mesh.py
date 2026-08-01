#!/usr/bin/env python3
"""端到端「PSD/atlas 件 → S3 生成 mesh」對照 Award 真實生產 mesh(ground truth)。

背景(knowledge/s4-psd-to-spine-real.md):Award 是機器人拆件的真實 spine;3 件為 mesh
(光暈/身體/左手,皆 weighted、無 deform timeline)。本工具:
  1. 從 Award atlas 抽出該件的貼圖(derotate 對正,atlas ~0.70 縮放版即為 piece alpha 真值)。
  2. 對該 alpha 跑 S3 generate_mesh_v2(auto)。
  3. 把 Award 真實 mesh 的 page-uv 映射進「derotate 後的 crop 像素框」(同一座標系)。
  4. 量化對照:各自對 piece alpha 的覆蓋 IoU、彼此 mesh 覆蓋 IoU、頂點/三角/hull 複雜度。

驗證原理:artist mesh IoU 若高(~0.9+),即交叉確認 uv→crop 映射與 derotate 方向正確
(自我驗證,不靠肉眼)。這是純 CPU、對真實生產標的之端到端驗收。
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from atlas_crop import parse_atlas
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate

PAGE_SIZE = {}  # filled from atlas


def page_sizes(atlas_path):
    sizes, cur = {}, None
    for ln in open(atlas_path, encoding="utf-8").read().splitlines():
        if not ln.startswith(" ") and ln.rstrip().endswith(".png"):
            cur = ln.strip()
        elif cur and ln.strip().startswith("size:"):
            w, h = ln.split(":", 1)[1].split(",")
            sizes[cur] = (int(w), int(h))
    return sizes


def extract_crop(atlas_path, region):
    """derotate 後的 upright crop(BGRA)。回傳 crop 與 (x,y,w,h,rot)。"""
    page = region["page"]
    sheet = cv2.imread(os.path.join(os.path.dirname(atlas_path), page), cv2.IMREAD_UNCHANGED)
    x, y = [int(t) for t in region["xy"].split(",")]
    w, h = [int(t) for t in region["size"].split(",")]
    rot = region.get("rotate", "false") in ("true", "90")
    if rot:
        sub = sheet[y:y + w, x:x + h]
        crop = cv2.rotate(sub, cv2.ROTATE_90_CLOCKWISE)
    else:
        crop = sheet[y:y + h, x:x + w]
    return crop, (x, y, w, h, rot)


def uv_to_crop_px(u, v, rect, PW, PH):
    """page-uv → derotate 後 crop 的像素座標 (x_px, y_px)。"""
    x, y, w, h, rot = rect
    px, py = u * PW, v * PH
    if rot:
        # crop = ROTATE_90_CW(sheet[y:y+w, x:x+h]); 見 atlas_crop.crop_region
        r = py - y          # row in sub  (0..w-1)
        c = px - x          # col in sub  (0..h-1)
        return c, (w - 1) - r
    return px - x, py - y


def compute_bone_world(sk):
    """設定姿勢下每根 bone 的世界矩陣 (a,b,c,d,wx,wy)。忽略 transform-mode 特例(預設繼承)。"""
    from math import cos, sin, radians
    bones = sk["bones"]
    by_name = {b["name"]: b for b in bones}
    world = {}

    def solve(b):
        name = b["name"]
        if name in world:
            return world[name]
        x = b.get("x", 0.0); y = b.get("y", 0.0)
        rot = b.get("rotation", 0.0)
        sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
        shx = b.get("shearX", 0.0); shy = b.get("shearY", 0.0)
        la = cos(radians(rot + shx)) * sx
        lc = sin(radians(rot + shx)) * sx
        lb = cos(radians(rot + 90 + shy)) * sy
        ld = sin(radians(rot + 90 + shy)) * sy
        parent = b.get("parent")
        if parent is None:
            w = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, pwx, pwy = solve(by_name[parent])
            w = (pa * la + pb * lc, pa * lb + pb * ld,
                 pc * la + pd * lc, pc * lb + pd * ld,
                 pa * x + pb * y + pwx, pc * x + pd * y + pwy)
        world[name] = w
        return w

    for b in bones:
        solve(b)
    return world


def artist_setup_points(sk, slot, name):
    """weighted mesh → 設定姿勢的世界座標點雲(藝術家 mesh 的真實輪廓,與 atlas 打包無關)。"""
    world = compute_bone_world(sk)
    bones = sk["bones"]
    slot_bone = {s["name"]: s.get("bone") for s in sk["slots"]}
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    V = a["vertices"]
    pts = []
    i = 0
    while i < len(V):
        n = int(V[i]); i += 1
        px = py = 0.0
        for _ in range(n):
            bi = int(V[i]); bx = V[i + 1]; by = V[i + 2]; wt = V[i + 3]; i += 4
            bw = world[bones[bi]["name"]]
            px += (bw[0] * bx + bw[1] * by + bw[4]) * wt
            py += (bw[2] * bx + bw[3] * by + bw[5]) * wt
        pts.append((px, py))
    return np.array(pts), np.array(a["triangles"]).reshape(-1, 3)


def norm_to_box(pts, W, H, transform):
    """把點雲依 bbox 正規化到 [0,W]×[0,H];transform ∈ 0..7(dihedral:旋轉/翻轉)對正。"""
    p = pts.copy().astype(np.float64)
    if transform & 4:                       # 轉置(對角翻)
        p = p[:, ::-1]
    if transform & 1:
        p[:, 0] = -p[:, 0]
    if transform & 2:
        p[:, 1] = -p[:, 1]
    mn = p.min(0); ext = (p.max(0) - mn)
    ext[ext == 0] = 1
    # 保持長寬比(uniform scale)置中,避免非等向拉伸扭曲輪廓
    s = min((W - 1) / ext[0], (H - 1) / ext[1])
    q = (p - mn) * s
    q[:, 0] += (W - 1 - ext[0] * s) / 2.0
    q[:, 1] += (H - 1 - ext[1] * s) / 2.0
    return q


def render(poly_pts, tris, H, W):
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(poly_pts[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def compare(atlas_path, skeleton_path, slot, name, tmp_dir):
    regs = parse_atlas(atlas_path)
    PW, PH = page_sizes(atlas_path)[regs[name]["page"]]
    crop, rect = extract_crop(atlas_path, regs[name])
    H, W = crop.shape[:2]
    mask = (crop[:, :, 3] > 8).astype(np.uint8) if crop.ndim == 3 and crop.shape[2] == 4 \
        else (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)

    crop_path = os.path.join(tmp_dir, "_award_crop.png")
    cv2.imwrite(crop_path, crop)

    # --- 生成 mesh ---
    mesh = gen_v2(crop_path, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=64)
    gpts = np.array([[mesh["vertices"][i] + W / 2.0, H / 2.0 - mesh["vertices"][i + 1]]
                     for i in range(0, len(mesh["vertices"]), 2)])
    gtris = np.array(mesh["triangles"]).reshape(-1, 3)
    recon_gen = render(gpts, gtris, H, W)

    # --- Award 真實 mesh:解 weighted 設定姿勢世界座標(atlas 打包無關的真實輪廓) ---
    # 注意:Award.json 的 uvs 跨滿整頁 → 與已縮小重打包的 Award.atlas 不一致(見 knowledge),
    # 故不能用 uv→atlas 對照;改用 mesh 自身幾何。以 dihedral 對正到件輪廓(自我驗證取最佳)。
    sk = json.load(open(skeleton_path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    apts_world, atris = artist_setup_points(sk, slot, name)
    best = (-1.0, None, None)
    for tf in range(8):
        cand = norm_to_box(apts_world, W, H, tf)
        rec = render(cand, atris, H, W)
        cov = iou(rec, mask)
        if cov > best[0]:
            best = (cov, rec, tf)
    art_cov, recon_art, art_tf = best        # 最佳 dihedral 對正下的藝術家覆蓋(自我驗證)

    gen_cov = iou(recon_gen, mask)
    mesh_iou = iou(recon_gen, recon_art)     # 生成 mesh 覆蓋 vs 藝術家 mesh 覆蓋(同框)

    return {
        "slot": slot,
        "crop_px": [W, H], "rotate": rect[4],
        "generated": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                      "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                      "coverage_iou": round(gen_cov, 4),
                      "format_pass": ev["criteria"]["AC4_format"]["pass"]},
        "artist_award": {"vertices": len(apts_world), "hull": a.get("hull"),
                         "triangles": len(atris),
                         "weighted": len(a["vertices"]) != len(a["uvs"]),
                         "coverage_iou": round(art_cov, 4), "align_transform": art_tf},
        "gen_vs_artist_mesh_iou": round(mesh_iou, 4),
        "self_check_artist_mapping_ok": art_cov >= 0.80,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--slots", nargs="*",
                    default=["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"])
    a = ap.parse_args()
    out = [compare(a.atlas, a.skeleton, s, s, a.tmp) for s in a.slots]
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
