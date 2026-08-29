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


def _axis_bones(world_pts, k=2):
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


def build(psd_path, out_dir, genre="slot_bigwin", weighted=False, animate=False,
          articulate=False):
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

    # ---- 運動學父子樹 + 關節 pivot(articulate 模式;S5 接觸縫推斷寫入 rig)----
    #  角色來源:分析器 #2 的 struct_role(body/head/limb)。body=子 rig 根;head/limb 掛 body;
    #  特效件/其他 掛 root(不articulate)。關節 pivot = 父子件世界輪廓的接觸縫質心。
    role_of = {}
    for ef in spec["2_effects"]:
        role_of[ef["name"]] = "effect" if ef.get("is_effect") else ef.get("struct_role")
    idx_of = {metas[i]["name"]: i for i in range(len(metas))}
    body_part = next((nm for nm in idx_of if role_of.get(nm) == "body"), None)
    tree = {}   # child_part -> parent_part(結構肢體)
    if articulate and body_part is not None:
        for nm in idx_of:
            if nm != body_part and role_of.get(nm) in ("head", "limb"):
                tree[nm] = body_part
    joints = {}  # child_part -> 世界關節 pivot (x,y)
    if tree:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
        from infer_pivots import contact_seam_joint
        wpoly = {}
        for nm, i in idx_of.items():
            ox_, oy_ = offsets[i]
            wpoly[nm] = _boundary_world(os.path.join(parts_dir, metas[i]["file"]), ox_, oy_, H)[0]
        for child, parent in tree.items():
            j, _ = contact_seam_joint(wpoly[parent], wpoly[child], q=0.2)
            joints[child] = j

    # Spine skeleton JSON
    bones = [{"name": "root"}]
    slots, skin = [], {}
    build_meta = {}   # slot_safe -> {"kind": effect|structural}(供 weighted 閘依語意分類)
    rig_meta = {}     # slot_safe -> {parent_bone, joint_world, role}(關節鏈紀錄)
    # z 升序 = 由下而上繪製(slot 繪製順序);bone 生成順序在 articulate 時需父先於子
    z_order = sorted(range(len(parts)), key=lambda i: metas[i]["z"])
    if tree:
        bone_order = [i for i in z_order if metas[i]["name"] not in tree] + \
                     [i for i in z_order if metas[i]["name"] in tree]
    else:
        bone_order = z_order   # 無 articulate → 與舊輸出完全一致

    part_bone = {}       # part_name -> bone name
    bone_world_xy = {}   # part_name -> (wx, wy) 世界位置
    att_of = {}          # part_name -> attachment dict
    for i in bone_order:
        e = metas[i]; nm = names[i]; pn = e["name"]; w, h = sizes[i]
        ox, oy = offsets[i]
        Cworld = (ox + w / 2.0, H - (oy + h / 2.0))        # 件中心世界座標
        bone = f"b_{nm}"; part_bone[pn] = bone
        parent_part = tree.get(pn)
        use_mesh = geo.get(pn, "").startswith("mesh")
        articulated_child = parent_part is not None and not (use_mesh and weighted)
        if articulated_child:
            J = joints[pn]
            Pw = bone_world_xy[parent_part]                # 父骨世界位置
            bones.append({"name": bone, "parent": part_bone[parent_part],
                          "x": round(J[0] - Pw[0], 2), "y": round(J[1] - Pw[1], 2)})
            bone_world_xy[pn] = (J[0], J[1])               # 子骨原點 = 關節 pivot
            off = (Cworld[0] - J[0], Cworld[1] - J[1])     # attachment 需偏移回件中心
            rig_meta[nm] = {"parent_bone": part_bone[parent_part], "role": role_of.get(pn),
                            "joint_world": [round(J[0], 2), round(J[1], 2)]}
        else:                                              # 根件(body/特效/無父)= 掛 root、骨在件中心
            bones.append({"name": bone, "parent": "root",
                          "x": round(Cworld[0], 2), "y": round(Cworld[1], 2)})
            bone_world_xy[pn] = Cworld
            off = (0.0, 0.0)
        part_png = os.path.join(parts_dir, e["file"])
        if use_mesh and weighted:
            base = len(bones)                              # 控制骨的全域起始 index
            att, ctrl = _weighted_attachment(part_png, ox, oy, W, H, w, h, base, bone)
            bones += ctrl
        elif use_mesh:
            m = gen_mesh(part_png, mode="auto")
            verts = list(m["vertices"])
            if off != (0.0, 0.0):                          # 骨移到關節 → 平移 mesh 回件中心
                verts = [verts[k] + (off[0] if k % 2 == 0 else off[1]) for k in range(len(verts))]
            att = {"type": "mesh", "vertices": verts, "uvs": m["uvs"],
                   "triangles": m["triangles"], "hull": m["hull"],
                   "width": m["width"], "height": m["height"]}
        else:
            att = {"x": round(off[0], 2), "y": round(off[1], 2), "width": w, "height": h}
        att_of[pn] = att
        build_meta[nm] = {"kind": kind_of(pn), "mesh": use_mesh}

    for i in z_order:                                      # slots 依繪製順序(z 升序)
        pn = metas[i]["name"]; nm = names[i]
        slots.append({"name": nm, "bone": part_bone[pn], "attachment": nm})
        skin[nm] = {nm: att_of[pn]}

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
    json.dump(rig_meta, open(os.path.join(out_dir, "rig_meta.json"), "w"), ensure_ascii=False, indent=1)
    summary = {"out": out_dir, "canvas": [W, H], "atlas_page": [PW, PH],
               "parts": len(parts), "articulated_joints": sorted(rig_meta.keys()),
               "mesh_parts": [names[i] for i in z_order if geo.get(metas[i]["name"], "").startswith("mesh")],
               "region_parts": [names[i] for i in z_order if not geo.get(metas[i]["name"], "").startswith("mesh")]}
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--out", default=None)
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--weighted", action="store_true", help="mesh 件產 weighted(骨綁)mesh + 自動控制骨")
    ap.add_argument("--animate", action="store_true", help="同時由 #3 分鏡生成 animations(candidate 0d)")
    ap.add_argument("--rig", action="store_true",
                    help="依 struct_role + 接觸縫 pivot 建關節鏈(head/limb 掛 body,骨在關節);S5")
    a = ap.parse_args()
    out = a.out or os.path.join("specs", safe(os.path.splitext(os.path.basename(a.psd))[0]) + "_spine")
    s = build(a.psd, out, a.genre, weighted=a.weighted, animate=a.animate, articulate=a.rig)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
