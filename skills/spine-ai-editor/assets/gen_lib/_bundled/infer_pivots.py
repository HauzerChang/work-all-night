"""S5 rig pivot 推斷器(第一版,確定性、純 CPU)。

問題(S5 唯一卡死環節的**可客觀化子問題**):
  給定已拆好的各部位幾何(mask/polygon,置於同一 composite 世界座標)+ 運動學父子樹
  (誰是誰的子件,由 S1 分析器 / genre_priors 給),**推斷每根子骨的關節 pivot 應該放哪**。

界定(誠實):
  - 可客觀推斷者 = **關節位於「子件與父件的接觸縫」**(shoulder/neck/hip 都在此)。本器只做這件。
  - 不可客觀者 = pivot 沿肢體軸的精確落點、以及「該不該偏離接觸縫幾像素以取得手感」——
    這屬美術微調(RULES A 類),留給使用者;本器輸出接觸縫質心作為**草案**。

演算法(deterministic contact-seam):
  對每個 (parent, child) 部位對:
    1. 取兩件的世界點雲(mesh hull 世界頂點,或 region 4 角)。
    2. 對每個 child 點算到 parent 點雲的最近距離 d。
    3. 接觸縫 = d 落在最小 q 分位(預設 q=0.2)的 child 點集合。
    4. joint = 接觸縫質心。
  重疊件(d=0 的 child 點在 parent 內)自然落在重疊區質心 —— 仍是合理的肩內 pivot。

此檔同時提供從真實 Award 資產抽「機器人 5 件世界多邊形 + 真值 pivot」的 loader,供 validate 用。
"""
import sys, os, math, json
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import weighted_deform_eval as wde  # noqa: E402


# ---------------- 幾何核心 ----------------
def _poly_points(poly):
    return np.asarray(poly, dtype=np.float64).reshape(-1, 2)


def contact_seam_joint(parent_poly, child_poly, q=0.2):
    """回傳 (joint_xy, seam_pts)。joint = child 最靠近 parent 的 q 分位點質心。"""
    P = _poly_points(parent_poly)
    C = _poly_points(child_poly)
    # child 每點到 parent 點雲最近距離
    d = np.min(np.linalg.norm(C[:, None, :] - P[None, :, :], axis=2), axis=1)
    thr = np.quantile(d, q)
    seam = C[d <= thr + 1e-9]
    if len(seam) == 0:
        seam = C[np.argmin(d)][None, :]
    return seam.mean(axis=0), seam


def infer_pivots(parts, tree, q=0.2):
    """parts: {name: Nx2 世界多邊形}; tree: {child: parent}。
    回傳 {child: joint_xy(np.array)}。root(無父)不推斷。"""
    out = {}
    for child, parent in tree.items():
        if parent is None or parent not in parts or child not in parts:
            continue
        j, _ = contact_seam_joint(parts[parent], parts[child], q=q)
        out[child] = j
    return out


def centroid_baseline(parts, tree):
    """天真 baseline:用子件質心當 pivot(接觸縫法要顯著贏過它)。"""
    return {c: _poly_points(parts[c]).mean(axis=0)
            for c, p in tree.items() if p is not None and c in parts}


# ---------------- 從 Award 抽真值 ----------------
# 機器人子 rig:身體為根,頭/左手/右手為其子;bone 世界位置 = 真值 pivot。
ROBOT_SLOT_BONE = {
    "機器人拆件/身體": "4_LEG3",
    "機器人拆件/頭":   "4_LEG4",
    "機器人拆件/左手": "4_LEG5",
    "機器人拆件/右手": "4_LEG6",
    "機器人拆件/光暈": "4_LEG",   # 光暈是背光特效件,非結構肢體(對照用,不列入結構關節)
}
ROBOT_TREE = {          # child_slot -> parent_slot(結構肢體;光暈不列)
    "機器人拆件/頭":   "機器人拆件/身體",
    "機器人拆件/左手": "機器人拆件/身體",
    "機器人拆件/右手": "機器人拆件/身體",
}


def _region_local_to_world(att, bone_world, unit_pts):
    """unit_pts: Nx2,以 region 中心為原點的正規化座標(u,v ∈ [-0.5,0.5],v 上為正)。
    → 世界座標(套 region rotation + (x,y) + bone world)。"""
    x = att.get("x", 0.0); y = att.get("y", 0.0)
    w = att.get("width", 0.0); h = att.get("height", 0.0)
    rot = math.radians(att.get("rotation", 0.0))
    ca, sa = math.cos(rot), math.sin(rot)
    out = []
    for u, v in unit_pts:
        sx, sy = u * w, v * h
        lx = x + sx * ca - sy * sa
        ly = y + sx * sa + sy * ca
        out.append(wde.transform_point(bone_world, lx, ly))
    return np.array(out, dtype=np.float64)


def _region_world_corners(att, bone_world):
    """region attachment → 4 角世界座標(粗略 bounding-rect 代理)。"""
    corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
    return _region_local_to_world(att, bone_world, corners)


def _region_world_silhouette(att, bone_world, slot, atlas_path, asset_dir, approx_eps=0.01):
    """從 atlas 頁裁出 region 的真實 alpha 輪廓 → 世界點雲。無 PNG 時回傳 None。"""
    try:
        import cv2
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
        import atlas_crop as ac
    except Exception:
        return None
    try:
        regs = ac.parse_atlas(atlas_path)
    except Exception:
        return None
    r = regs.get(slot)
    if r is None:
        return None
    page = os.path.join(asset_dir, r["page"])
    if not os.path.exists(page):
        return None
    sheet = cv2.imread(page, cv2.IMREAD_UNCHANGED)
    if sheet is None or sheet.ndim < 3 or sheet.shape[2] < 4:
        return None
    sub = ac.crop_region(sheet, r)          # 已 derotate 至 orig 方向
    ih, iw = sub.shape[:2]
    alpha = sub[:, :, 3]
    cnts, _ = cv2.findContours((alpha > 10).astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    peri = cv2.arcLength(c, True)
    c = cv2.approxPolyDP(c, approx_eps * peri, True).reshape(-1, 2).astype(np.float64)
    # 影像像素(px 右、py 下)→ 正規化(u 右、v 上,中心原點)
    u = c[:, 0] / iw - 0.5
    v = 0.5 - c[:, 1] / ih
    return _region_local_to_world(att, bone_world, np.column_stack([u, v]))


def _mesh_world_hull(att, bone_world, bones, byname, order):
    """mesh attachment → hull 頂點世界座標(weighted 走 skinning,unweighted 走單骨)。"""
    pv, tris, hull, uvs, weighted = wde.parse_weighted(att)
    bidx_to_name = order
    if weighted:
        world = wde.bone_world_transforms(bones, byname, order, {})
        V = wde.skin_vertices(pv, world, bidx_to_name)
    else:
        # unweighted:頂點為相對「該 slot 綁定骨」的局部座標
        V = np.array([wde.transform_point(bone_world, e[0][1], e[0][2]) for e in pv])
    nhull = hull if hull else len(V)
    return V[:nhull]


def load_award_robot(award_path="assets/Award.json", use_alpha=True):
    """回傳 (parts_world, truth_pivots, tree, fidelity)。
       parts_world: {slot: Nx2 世界多邊形};truth_pivots: {slot: bone 世界位置};
       fidelity: {slot: 'mesh'|'alpha'|'rect'} —— 該件幾何代理的保真度。
       use_alpha=True 時 region 件優先用 atlas alpha 真實輪廓(需 Award.png/Award2.png)。"""
    sk, bones, byname, order = wde.load_skeleton(award_path)
    atts = wde.get_skin_attachments(sk)
    world = wde.bone_world_transforms(bones, byname, order, {})
    asset_dir = os.path.dirname(os.path.abspath(award_path))
    atlas_path = os.path.splitext(award_path)[0] + ".atlas"

    parts, truth, fidelity = {}, {}, {}
    for slot, bone in ROBOT_SLOT_BONE.items():
        bw = world[bone]
        truth[slot] = np.array([bw[4], bw[5]], dtype=np.float64)  # bone world (x,y)
        adict = atts.get(slot, {})
        if not adict:
            continue
        att = next(iter(adict.values()))
        t = att.get("type", "region")
        if t == "mesh":
            parts[slot] = _mesh_world_hull(att, bw, bones, byname, order)
            fidelity[slot] = "mesh"
        else:
            sil = _region_world_silhouette(att, bw, slot, atlas_path, asset_dir) if use_alpha else None
            if sil is not None and len(sil) >= 3:
                parts[slot] = sil
                fidelity[slot] = "alpha"
            else:
                parts[slot] = _region_world_corners(att, bw)
                fidelity[slot] = "rect"
    return parts, truth, ROBOT_TREE, fidelity


if __name__ == "__main__":
    use_alpha = "--no-alpha" not in sys.argv
    parts, truth, tree, fid = load_award_robot(use_alpha=use_alpha)
    print(f"parts loaded (use_alpha={use_alpha}):")
    for s, p in parts.items():
        c = p.mean(0)
        print(f"  {s:<18} [{fid[s]:<5}] verts={len(p):<4} centroid=({c[0]:8.2f},{c[1]:8.2f})")
    print("\ninferred vs truth pivots:")
    inf = infer_pivots(parts, tree)
    for c in tree:
        j = inf[c]; t = truth[c]
        print(f"  {c:<18} [{fid[c]:<5}] infer=({j[0]:8.2f},{j[1]:8.2f})  "
              f"truth=({t[0]:8.2f},{t[1]:8.2f})  err={np.linalg.norm(j-t):6.2f}")
