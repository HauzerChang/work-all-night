#!/usr/bin/env python3
"""SkelToJson 端到端 — 目標圖(分層 PSD)→ 可載入的 Spine 3.8 素材(json + atlas + png)。

串起前面能力:
  analyze_target(規格:件/mesh-vs-region/z序/pivot) + psd_slice(切件 PNG)
  + generate_mesh_v2(mesh 件拓樸) → 打包 atlas + 組 Spine skeleton JSON。

輸出 setup-pose 可載入素材(bones/slots/skin/attachments);動畫先留空(分鏡由 #3 規格描述,
自動生 keyframe 屬後續)。可用 validate_build.py 做 round-trip(重建 setup pose == 原圖)驗證。

座標約定(builder / validator 必須一致):
  影像左上原點、y 向下;Spine root 置畫布左下、y 向上。
  某件影像中心 (cx, cy) → bone(x=cx, y=H-cy),parent=root。
  region/mesh 的頂點/uv 皆相對該 bone(generate_mesh_v2 已置中+y上翻,直接吻合)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_mesh
from analyze_target import analyze
import generate_weighted_mesh as gwm


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _boundary_world(part_png, ox, oy, H, approx_frac=0.012):
    """由件 alpha 取外輪廓 → 簡化多邊形 → 轉 Spine 世界座標(y 上翻)。回傳 Nx2。"""
    img = cv2.imread(part_png, cv2.IMREAD_UNCHANGED)
    alpha = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    mask = (alpha > 8).astype(np.uint8)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    eps = approx_frac * cv2.arcLength(c, True)
    poly = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(np.float64)
    # part-local (px,py,y-down) → world (ox+px, H-(oy+py))
    world = np.column_stack([ox + poly[:, 0], H - (oy + poly[:, 1])])
    return world, poly  # world 供三角化/骨;poly(part-local)供 uv


def _alpha_area(part_png):
    """件的不透明像素數(真實面積代理;比 bbox 面積可靠 —— 大框但稀疏的件不會被誤判為最大)。"""
    img = cv2.imread(part_png, cv2.IMREAD_UNCHANGED)
    if img is None:
        return 0
    alpha = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        np.full(img.shape[:2], 255, np.uint8)
    return int((alpha > 8).sum())


# ---------------- S5 rig:接觸縫關節 pivot 併入骨階層 ----------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
from infer_pivots import contact_seam_joint  # noqa: E402


def infer_rig_tree(struct_parts, areas):
    """星狀 rig 先驗:結構件中面積(不透明像素)最大者為 root(通常是身體/軀幹),
    其餘結構件皆為其子。回傳 (root_key, {child_key: root_key})。
    ⚠️ 這是**類型先驗**(big-win 單角色符號的常見拓樸),非從幾何推肢體樹;
    完整肢體拓樸推斷屬另一子問題(見 knowledge)。"""
    if not struct_parts:
        return None, {}
    root_key = max(struct_parts, key=lambda k: areas[k])
    tree = {k: root_key for k in struct_parts if k != root_key}
    return root_key, tree
    """沿 PCA 主軸放 k 根控制骨(世界座標)。回傳 [(x,y),...]。"""
    c = world_pts.mean(0)
    u, s, vt = np.linalg.svd(world_pts - c, full_matrices=False)
    axis = vt[0]
    proj = (world_pts - c) @ axis
    lo, hi = proj.min(), proj.max()
    return [tuple(c + axis * (lo + (hi - lo) * (0.5 if k == 1 else (0.2 + 0.6 * j / (k - 1)))))
            for j in range(k)]


def _weighted_attachment(part_png, ox, oy, W, H, w, h, bone_base_idx, bone_names_start,
                         max_area=1500.0, k_bones=2):
    """生成 weighted mesh attachment + 該件的控制骨定義。
    回傳 (attachment, new_bones)。new_bones 為 root 子骨(絕對世界座標、rotation 0),
    故 setup skinning 用簡單 bind = 世界頂點 - 骨原點,partition of unity → 完美重建。"""
    world, poly = _boundary_world(part_png, ox, oy, H)
    V, F = gwm.triangulate_polygon(world, max_area=max_area, boundary_steiner=False)
    n_hull = len(world)                                  # 前 N 頂點 == 邊界(Y 選項保證)
    bone_pos = _axis_bones(world, k=k_bones)
    segs = [(p, p) for p in bone_pos]                    # 點骨
    Wg = gwm.prune_topk(gwm.heat_weights(V, F, segs), k=4)
    # 組 weighted vertices(全域骨 index = bone_base_idx + j)+ uvs(part-local, top-left, v下)
    verts, uvs = [], []
    for i, (wx, wy) in enumerate(V):
        entries = [(j, wx - bone_pos[j][0], wy - bone_pos[j][1], float(Wg[i, j]))
                   for j in range(k_bones) if Wg[i, j] > 1e-6]
        if not entries:
            j = int(Wg[i].argmax())
            entries = [(j, wx - bone_pos[j][0], wy - bone_pos[j][1], 1.0)]
        s = sum(e[3] for e in entries)
        verts.append(len(entries))
        for (j, bx, by, wt) in entries:
            verts += [bone_base_idx + j, round(bx, 3), round(by, 3), round(wt / s, 5)]
        # uv:世界 → part-local px,py
        px = wx - ox; py = H - wy - oy
        uvs += [round(px / w, 5), round(py / h, 5)]
    att = {"type": "mesh", "vertices": verts, "uvs": uvs,
           "triangles": [int(x) for t in F for x in t],
           "hull": int(n_hull), "width": int(w), "height": int(h)}
    new_bones = [{"name": f"{bone_names_start}_c{j}", "parent": "root",
                  "x": round(bone_pos[j][0], 2), "y": round(bone_pos[j][1], 2)}
                 for j in range(k_bones)]
    return att, new_bones


def shelf_pack(sizes, pad=2, max_w=2048):
    """簡單 shelf 打包:回傳每件 (x,y) 左上 + page (W,H)。sizes=[(w,h),...]。"""
    placements = []
    x = y = row_h = 0
    W = 0
    for (w, h) in sizes:
        if x + w + pad > max_w and x > 0:
            x = 0
            y += row_h + pad
            row_h = 0
        placements.append((x, y))
        x += w + pad
        row_h = max(row_h, h)
        W = max(W, x)
    H = y + row_h
    return placements, (W, H)


def build(psd_path, out_dir, genre="slot_bigwin", weighted=False, animate=False, rig=False):
    os.makedirs(out_dir, exist_ok=True)
    parts_dir = os.path.join(out_dir, "_parts")
    psd, manifest, parts = slice_psd(psd_path, parts_dir)     # 切件 PNG(裁到 bbox)+ manifest
    W, H = psd.width, psd.height
    spec = analyze(psd_path, genre)
    geo = {r["part"]: r["geometry"] for r in spec["4_slicing_strategy"]["parts"]}
    note = {r["part"]: r.get("note", "") for r in spec["4_slicing_strategy"]["parts"]}
    def kind_of(part_name):  # 特效件=軟性加成(si 容忍);其餘=不透明結構件
        return "effect" if "特效" in note.get(part_name, "") else "structural"

    # atlas 打包
    imgs, names, sizes, offsets, metas = [], [], [], [], []
    for e, im in parts:
        rgba = cv2.cvtColor(np.array(im), cv2.COLOR_RGBA2BGRA)
        h, w = rgba.shape[:2]
        imgs.append(rgba); names.append(safe(e["name"]))
        sizes.append((w, h)); offsets.append(e["offset"])
        metas.append(e)
    placements, (PW, PH) = shelf_pack(sizes)
    PW = max(PW, 1); PH = max(PH, 1)
    page = np.zeros((PH, PW, 4), np.uint8)
    atlas_regions = {}
    for (rgba, (px, py), (w, h), nm) in zip(imgs, placements, sizes, names):
        page[py:py + h, px:px + w] = rgba
        atlas_regions[nm] = {"xy": (px, py), "size": (w, h)}
    png_name = "skeleton.png"
    cv2.imwrite(os.path.join(out_dir, png_name), page)

    # .atlas(libgdx)
    lines = [png_name, f"size: {PW},{PH}", "format: RGBA8888",
             "filter: Linear,Linear", "repeat: none"]
    for nm in names:
        r = atlas_regions[nm]
        lines += [nm, "  rotate: false",
                  f"  xy: {r['xy'][0]}, {r['xy'][1]}",
                  f"  size: {r['size'][0]}, {r['size'][1]}",
                  f"  orig: {r['size'][0]}, {r['size'][1]}",
                  "  offset: 0, 0", "  index: -1"]
    open(os.path.join(out_dir, "skeleton.atlas"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    def center_world(i):
        ox, oy = offsets[i]; w, h = sizes[i]
        return (ox + w / 2.0, H - (oy + h / 2.0))

    # ---- S5 rig:預先推 star tree + 每結構子件的接觸縫關節(世界座標)----
    rig_joint, rig_parent, rig_meta = {}, {}, {}
    if rig:
        sil_w, area, struct = {}, {}, []
        for i in range(len(parts)):
            e = metas[i]; ox, oy = offsets[i]
            if kind_of(e["name"]) == "structural":
                part_png = os.path.join(parts_dir, e["file"])
                sil_w[i], _ = _boundary_world(part_png, ox, oy, H)
                area[i] = _alpha_area(part_png)
                struct.append(i)
        root_i, tree_i = infer_rig_tree(struct, area)
        for child_i, par_i in tree_i.items():
            j, _ = contact_seam_joint(sil_w[par_i], sil_w[child_i], q=0.2)
            rig_joint[child_i] = (float(j[0]), float(j[1]))
            rig_parent[child_i] = par_i
        rig_meta = {"root_part": names[root_i] if root_i is not None else None,
                    "children": {names[c]: names[p] for c, p in rig_parent.items()}}

    # Spine skeleton JSON
    bones = [{"name": "root"}]
    slots, skin = [], {}
    build_meta = {}   # slot_safe -> {"kind": effect|structural}(供 weighted 閘依語意分類)
    # z 升序 = 由下而上繪製
    order = sorted(range(len(parts)), key=lambda i: metas[i]["z"])
    for i in order:
        e = metas[i]; nm = names[i]; w, h = sizes[i]
        ox, oy = offsets[i]
        cxw, cyw = center_world(i)
        bone = f"b_{nm}"
        use_mesh = geo.get(e["name"], "").startswith("mesh")
        part_png = os.path.join(parts_dir, e["file"])
        # 是否以接觸縫關節作 pivot 並掛到父件骨下(weighted mesh 走控制骨,不套 rig 關節)
        jointed = rig and (i in rig_parent) and not (use_mesh and weighted)
        if jointed:
            jx, jy = rig_joint[i]
            par_bone = f"b_{names[rig_parent[i]]}"
            pcx, pcy = center_world(rig_parent[i])
            bones.append({"name": bone, "parent": par_bone,           # 父件骨在其件中心、rot 0
                          "x": round(jx - pcx, 2), "y": round(jy - pcy, 2)})
            off = (cxw - jx, cyw - jy)      # 使件影像中心仍落在原位(pivot 移到關節後的補償)
        else:
            bones.append({"name": bone, "parent": "root",
                          "x": round(cxw, 2), "y": round(cyw, 2)})
            off = (0.0, 0.0)
        slots.append({"name": nm, "bone": bone, "attachment": nm})
        if use_mesh and weighted:
            base = len(bones)                              # 控制骨的全域起始 index
            att, ctrl = _weighted_attachment(part_png, ox, oy, W, H, w, h, base, bone)
            bones += ctrl
        elif use_mesh:
            m = gen_mesh(part_png, mode="auto")
            verts = list(m["vertices"])
            if off != (0.0, 0.0):          # pivot 移到關節 → 頂點同步平移以保持世界位置不變
                verts = [verts[k] + (off[0] if k % 2 == 0 else off[1]) for k in range(len(verts))]
            att = {"type": "mesh", "vertices": verts, "uvs": m["uvs"],
                   "triangles": m["triangles"], "hull": m["hull"],
                   "width": m["width"], "height": m["height"]}
        else:
            att = {"x": round(off[0], 2), "y": round(off[1], 2),
                   "width": w, "height": h}   # region;off=0 時 bone 即件中心
        skin[nm] = {nm: att}
        build_meta[nm] = {"kind": kind_of(e["name"]), "mesh": use_mesh,
                          "rig_parent": rig_meta.get("children", {}).get(nm)}

    if rig:      # 拓樸排序:rig 重親後 child 骨的 z 序可能早於父件骨,Spine 要求 parent 先於 child
        bmap = {b["name"]: b for b in bones}
        ordered, seen = [], set()
        def _emit(bn):
            if bn in seen:
                return
            p = bmap[bn].get("parent")
            if p and p in bmap:
                _emit(p)
            seen.add(bn); ordered.append(bmap[bn])
        for b in bones:
            _emit(b["name"])
        bones = ordered

    skeleton = {
        "skeleton": {"hash": "gen", "spine": "3.8.75", "x": 0, "y": 0,
                     "width": W, "height": H, "images": "./"},
        "bones": bones, "slots": slots,
        "skins": {"default": skin}, "animations": {},
    }
    if animate:
        # candidate 0d:把 #3 分鏡具體化為 Spine timeline,讓素材「會動」
        from gen_animations import build_animations
        skeleton["animations"] = build_animations(skeleton, spec["3_motion_storyboard"])
    json.dump(skeleton, open(os.path.join(out_dir, "skeleton.json"), "w"),
              ensure_ascii=False, indent=1)
    json.dump(build_meta, open(os.path.join(out_dir, "build_meta.json"), "w"), ensure_ascii=False, indent=1)
    summary = {"out": out_dir, "canvas": [W, H], "atlas_page": [PW, PH],
               "parts": len(parts),
               "mesh_parts": [names[i] for i in order if geo.get(metas[i]["name"], "").startswith("mesh")],
               "region_parts": [names[i] for i in order if not geo.get(metas[i]["name"], "").startswith("mesh")]}
    if rig:
        summary["rig"] = rig_meta
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--out", default=None)
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--weighted", action="store_true", help="mesh 件產 weighted(骨綁)mesh + 自動控制骨")
    ap.add_argument("--animate", action="store_true", help="同時由 #3 分鏡生成 animations(candidate 0d)")
    ap.add_argument("--rig", action="store_true",
                    help="結構件依接觸縫關節建骨階層(pivot 在關節、掛父件骨下),而非全部平掛 root")
    a = ap.parse_args()
    out = a.out or os.path.join("specs", safe(os.path.splitext(os.path.basename(a.psd))[0]) + "_spine")
    s = build(a.psd, out, a.genre, weighted=a.weighted, animate=a.animate, rig=a.rig)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
