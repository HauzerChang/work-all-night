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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
from infer_pivots import contact_seam_joint


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _role_of(note):
    """由分析器 note 判件角色:body / limb(含 head)/ effect / other。"""
    if "特效" in note:
        return "effect"
    if "body" in note:
        return "body"
    if "limb" in note or "head" in note:
        return "limb"
    return "other"


def _plan_rig_tree(metas, offsets, sizes, parts_dir, H):
    """由 role note 建結構父子樹 + 接觸縫關節 pivot。
    回傳 (tree, pivots, body_part_name):
      tree   —— {child_part_name: parent_part_name}(僅結構肢體 → body)。
      pivots —— {child_part_name: (x,y) spine 世界關節}(contact-seam)。
      body   —— 結構根件名(role=body,無則取面積最大結構件)。
    無 body 或無結構肢體時回 (None,None,None) → 呼叫端退回 flat。
    """
    role = {e["name"]: _role_of(e.get("note", "")) for e in metas}
    # role note 來自 analyzer;若 metas 無 note,呼叫端會補
    struct = [e["name"] for e in metas if role.get(e["name"]) in ("body", "limb")]
    bodies = [e["name"] for e in metas if role.get(e["name"]) == "body"]
    if bodies:
        body = bodies[0]
    else:
        # fallback:面積最大的結構件當 body
        area = {e["name"]: sizes[i][0] * sizes[i][1] for i, e in enumerate(metas)}
        cand = struct or [e["name"] for e in metas]
        body = max(cand, key=lambda n: area[n])
    limbs = [n for n in struct if n != body]
    if not limbs:
        return None, None, None
    # 各件世界輪廓多邊形(spine 座標:y 上翻)
    idx = {e["name"]: i for i, e in enumerate(metas)}
    world_poly = {}
    for n in [body] + limbs:
        e = metas[idx[n]]; ox, oy = offsets[idx[n]]
        w, _ = _boundary_world(os.path.join(parts_dir, e["file"]), ox, oy, H)
        world_poly[n] = w
    tree = {n: body for n in limbs}
    pivots = {}
    for n in limbs:
        j, _ = contact_seam_joint(world_poly[body], world_poly[n])
        pivots[n] = (float(j[0]), float(j[1]))
    return tree, pivots, body


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


def build(psd_path, out_dir, genre="slot_bigwin", weighted=False, animate=False, rig_tree=False):
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
        e["note"] = note.get(e["name"], "")        # 供 rig 樹 role 判定
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

    # Spine skeleton JSON
    bones = [{"name": "root"}]
    slots, skin = [], {}
    build_meta = {}   # slot_safe -> {"kind": effect|structural}(供 weighted 閘依語意分類)
    # z 升序 = 由下而上繪製
    order = sorted(range(len(parts)), key=lambda i: metas[i]["z"])

    # ── rig 樹規劃(S5(b)):子件骨落在關節 pivot、parent 到父件骨 ──
    tree = pivots = body_part = None
    if rig_tree:
        tree, pivots, body_part = _plan_rig_tree(metas, offsets, sizes, parts_dir, H)
        if tree is None:
            print("  [rig-tree] 無 body/肢體結構,退回 flat rig")
    rig_on = bool(tree)
    if rig_on and weighted:
        print("  [rig-tree] weighted+jointed 尚未整合 → 本次以 unweighted mesh 接關節鏈")
        weighted = False

    def _part_world_origin(i):
        """該件骨的世界原點(spine 座標):結構子件=關節 pivot,其餘=件中心。"""
        e = metas[i]; w, h = sizes[i]; ox, oy = offsets[i]
        cxw, cyw = ox + w / 2.0, H - (oy + h / 2.0)
        if rig_on and e["name"] in tree:
            return pivots[e["name"]]
        return (cxw, cyw)

    # 骨陣列(拓樸序:root → 根件群 → 子件);子件 parent 為 body 骨。
    body_bone = f"b_{safe(body_part)}" if rig_on else None
    bworld = {}                                            # part_name -> (x,y) 世界原點
    root_group = [i for i in order if not (rig_on and metas[i]["name"] in tree)]
    child_group = [i for i in order if rig_on and metas[i]["name"] in tree]
    for i in root_group:
        e = metas[i]; nm = names[i]
        wo = _part_world_origin(i); bworld[e["name"]] = wo
        b = {"name": f"b_{nm}", "parent": "root", "x": round(wo[0], 2), "y": round(wo[1], 2)}
        bones.append(b)
        if geo.get(e["name"], "").startswith("mesh") and weighted:
            ox, oy = offsets[i]; w, h = sizes[i]
            base = len(bones)
            att, ctrl = _weighted_attachment(os.path.join(parts_dir, e["file"]),
                                             ox, oy, W, H, w, h, base, f"b_{nm}")
            bones += ctrl
            e["_weighted_att"] = att                       # 暫存,pass S 取用
    for i in child_group:
        e = metas[i]; nm = names[i]
        wo = _part_world_origin(i); bworld[e["name"]] = wo
        bp = bworld[body_part]
        bones.append({"name": f"b_{nm}", "parent": body_bone,
                      "x": round(wo[0] - bp[0], 3), "y": round(wo[1] - bp[1], 3)})

    # slots + attachments(z 序 = 繪製序);attachment 以「件中心 − 骨原點」補償偏移。
    for i in order:
        e = metas[i]; nm = names[i]; w, h = sizes[i]
        ox, oy = offsets[i]
        cxw, cyw = ox + w / 2.0, H - (oy + h / 2.0)
        wo = bworld[e["name"]]
        dx, dy = cxw - wo[0], cyw - wo[1]                  # 件中心相對骨原點(setup rot=0)
        slots.append({"name": nm, "bone": f"b_{nm}", "attachment": nm})
        use_mesh = geo.get(e["name"], "").startswith("mesh")
        part_png = os.path.join(parts_dir, e["file"])
        if use_mesh and weighted:
            att = e.pop("_weighted_att")                   # 根件群已生成
        elif use_mesh:
            m = gen_mesh(part_png, mode="auto")
            verts = list(m["vertices"])
            if dx or dy:                                   # 子件 mesh:平移頂點補償骨移到關節
                for k in range(0, len(verts), 2):
                    verts[k] = round(verts[k] + dx, 3)
                    verts[k + 1] = round(verts[k + 1] + dy, 3)
            att = {"type": "mesh", "vertices": verts, "uvs": m["uvs"],
                   "triangles": m["triangles"], "hull": m["hull"],
                   "width": m["width"], "height": m["height"]}
        else:
            att = {"x": round(dx, 3), "y": round(dy, 3), "width": w, "height": h}
        skin[nm] = {nm: att}
        build_meta[nm] = {"kind": kind_of(e["name"]), "mesh": use_mesh,
                          "parent": (body_part if (rig_on and e["name"] in tree) else None)}

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
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--out", default=None)
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--weighted", action="store_true", help="mesh 件產 weighted(骨綁)mesh + 自動控制骨")
    ap.add_argument("--animate", action="store_true", help="同時由 #3 分鏡生成 animations(candidate 0d)")
    ap.add_argument("--rig-tree", dest="rig_tree", action="store_true",
                    help="S5(b):子件骨落在推斷關節 pivot 並 parent 到父件骨(關節鏈)")
    a = ap.parse_args()
    out = a.out or os.path.join("specs", safe(os.path.splitext(os.path.basename(a.psd))[0]) + "_spine")
    s = build(a.psd, out, a.genre, weighted=a.weighted, animate=a.animate, rig_tree=a.rig_tree)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
