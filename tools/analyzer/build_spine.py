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


# ---------------- S5 rig:pivot→bone 父子樹(--rig)----------------
def _part_role(note):
    """由分析器 note 判部位角色。body=rig 根;head/limb=結構子件;effect=特效(非關節)。"""
    if "特效" in note:
        return "effect"
    for r in ("body", "head", "limb"):
        if r in note:
            return r
    return "other"


def rig_layout(metas, names, sizes, offsets, H, notes, parts_dir):
    """S5:把各件排成骨骼父子樹,結構子件的 bone 原點落在「與**其父件**的接觸縫」pivot。

    回傳 (out, body, order)。out={name:{role, parent_bone, parent_name, world(x,y骨世界原點),
                 center(件中心世界), delta(件中心-骨原點,供 attachment 位移保 setup pose), joint}};
                 order = 階層拓樸序(父必先於子)。
    純確定性:**父子樹(root + parent 邊)由拆件相鄰幾何自動推斷**(`infer_tree`,支援多跳鏈),
    不再假設星形先驗;結構子件用 `contact_seam_joint` 對**其推得的父件**取縫;
    effect 件(role 由 note 分類)掛 root 下,不視為關節(原點=件中心)。
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
    from infer_pivots import contact_seam_joint  # noqa: E402
    from infer_tree import infer_tree            # noqa: E402

    info = {}
    for i in range(len(names)):
        nm = names[i]; w, h = sizes[i]; ox, oy = offsets[i]
        center = np.array([ox + w / 2.0, H - (oy + h / 2.0)])
        role = _part_role(notes.get(metas[i]["name"], ""))
        part_png = os.path.join(parts_dir, metas[i]["file"])
        world_sil, _ = _boundary_world(part_png, ox, oy, H)
        info[nm] = dict(role=role, center=center, sil=world_sil, area=w * h)

    # 結構件(effect 由 note 語意分類為輸入,honest boundary);root + 父子樹由幾何推斷
    structs = [nm for nm in names if info[nm]["role"] != "effect"]
    tree, body = {}, None
    if structs:
        sparts = {nm: info[nm]["sil"] for nm in structs}
        body, tree, _ = infer_tree(sparts)
    body_bone = f"b_{body}" if body else None

    out = {}
    for nm, d in info.items():
        if nm == body:                          # rig 根:parent=root,原點=件中心
            out[nm] = dict(role=d["role"], parent_bone="root", parent_name=None,
                           world=d["center"].copy(), center=d["center"],
                           delta=np.zeros(2), joint=False)
        elif nm in tree:                         # 結構子件:parent=推得父件,原點=與父件接觸縫 pivot
            par = tree[nm]
            j, _ = contact_seam_joint(info[par]["sil"], d["sil"])
            out[nm] = dict(role=d["role"], parent_bone=f"b_{par}", parent_name=par,
                           world=np.asarray(j, float), center=d["center"],
                           delta=d["center"] - np.asarray(j, float), joint=True)
        else:                                    # 特效件(或無 root):掛 root 下,原點=件中心,非關節
            out[nm] = dict(role=d["role"], parent_bone=body_bone or "root",
                           parent_name=body, world=d["center"].copy(), center=d["center"],
                           delta=np.zeros(2), joint=False)

    # 階層拓樸序(父必先於子):從 root 起 BFS,effect/孤兒殿後
    order, seen = [], set()
    if body:
        queue = [body]
        while queue:
            cur = queue.pop(0)
            if cur in seen:
                continue
            order.append(cur); seen.add(cur)
            queue += [c for c, p in tree.items() if p == cur and c not in seen]
    order += [nm for nm in names if nm not in seen]
    return out, body, order


def _weighted_attachment(part_png, ox, oy, W, H, w, h, bone_base_idx, bone_names_start,
                         max_area=1500.0, k_bones=2, parent_bone="root", parent_world=None):
    """生成 weighted mesh attachment + 該件的控制骨定義。
    回傳 (attachment, new_bones)。控制骨預設為 root 子骨(絕對世界座標、rotation 0),
    故 setup skinning 用簡單 bind = 世界頂點 - 骨原點,partition of unity → 完美重建。

    S5 rig×weighted:給 `parent_bone`(該件的關節骨 b_{nm})+ `parent_world`(其世界原點)後,
    控制骨改掛關節骨、座標轉為**相對關節骨的局部座標**(local = 控制骨世界 − 關節骨世界)。
    setup 下父鏈皆純平移 → 控制骨世界位置不變 → **bind 偏移完全不變、setup pose 精確保留**;
    但關節骨(及其祖先)旋轉時,控制骨(連同 weighted mesh)沿關節鏈剛性帶動 → weighted 件真正接進 rig。"""
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
    # 控制骨座標:預設世界(掛 root);rig×weighted 時轉為相對關節骨的局部座標(保 setup 不動)
    pwx, pwy = (parent_world[0], parent_world[1]) if parent_world is not None else (0.0, 0.0)
    new_bones = [{"name": f"{bone_names_start}_c{j}", "parent": parent_bone,
                  "x": round(bone_pos[j][0] - pwx, 2), "y": round(bone_pos[j][1] - pwy, 2)}
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


def build(psd_path, out_dir, genre="slot_bigwin", weighted=False, animate=False, rig=False,
          deform=False, deform_src=("assets/main_draw.json", "image/curtain_left", "image/curtain_left")):
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

    # Spine skeleton JSON
    bones = [{"name": "root"}]
    slots, skin = [], {}
    build_meta = {}   # slot_safe -> {"kind": effect|structural}(供 weighted 閘依語意分類)
    # z 升序 = 由下而上繪製
    order = sorted(range(len(parts)), key=lambda i: metas[i]["z"])

    # --rig:先算好 pivot→bone 父子樹,結構子件 bone 原點落在接觸縫;attachment 以 delta 位移保 setup pose。
    # rig×weighted(2026-08-31):weighted mesh 的控制骨改掛該件的關節骨 b_{nm}(接進關節鏈),
    #   非 mesh 結構件仍走 rig 的 delta 位移路徑。兩者可併用。
    if rig:
        rlay, body, rig_order = rig_layout(metas, names, sizes, offsets, H, note, parts_dir)
        wo = {nm: rlay[nm]["world"] for nm in rlay}
        for nm in rig_order:                   # 拓樸序:父必先於子(支援多跳鏈)
            r = rlay[nm]
            pw = wo[r["parent_name"]] if r["parent_name"] else np.zeros(2)
            lx, ly = np.asarray(r["world"]) - pw
            bones.append({"name": f"b_{nm}", "parent": r["parent_bone"],
                          "x": round(float(lx), 2), "y": round(float(ly), 2)})
        delta_of = {nm: np.asarray(rlay[nm]["delta"], float) for nm in rlay}
    else:
        delta_of = {nm: np.zeros(2) for nm in names}

    for i in order:
        e = metas[i]; nm = names[i]; w, h = sizes[i]
        ox, oy = offsets[i]
        cx = ox + w / 2.0
        cy = oy + h / 2.0
        bone = f"b_{nm}"
        if not rig:                            # 非 rig:每件綁 root、bone 置件中心(原行為)
            bones.append({"name": bone, "parent": "root",
                          "x": round(cx, 2), "y": round(H - cy, 2)})
        dx, dy = float(delta_of[nm][0]), float(delta_of[nm][1])   # 件中心 - bone 原點
        slots.append({"name": nm, "bone": bone, "attachment": nm})
        use_mesh = geo.get(e["name"], "").startswith("mesh")
        part_png = os.path.join(parts_dir, e["file"])
        if use_mesh and weighted:
            base = len(bones)                              # 控制骨的全域起始 index
            if rig:                                        # 控制骨掛該件關節骨 b_{nm}(接進關節鏈)
                att, ctrl = _weighted_attachment(part_png, ox, oy, W, H, w, h, base, bone,
                                                 parent_bone=bone, parent_world=wo[nm])
            else:                                          # 原行為:控制骨掛 root(絕對世界座標)
                att, ctrl = _weighted_attachment(part_png, ox, oy, W, H, w, h, base, bone)
            bones += ctrl
        elif use_mesh:
            m = gen_mesh(part_png, mode="auto")
            verts = m["vertices"]
            if rig and (dx or dy):             # bone 移到 pivot → mesh 頂點加 delta 保原位
                verts = [round(v + (dx if k % 2 == 0 else dy), 4) for k, v in enumerate(verts)]
            att = {"type": "mesh", "vertices": verts, "uvs": m["uvs"],
                   "triangles": m["triangles"], "hull": m["hull"],
                   "width": m["width"], "height": m["height"]}
        else:
            att = {"x": round(dx, 2), "y": round(dy, 2), "width": w, "height": h}  # region;bone 在 pivot,att 偏移回件中心
        skin[nm] = {nm: att}
        build_meta[nm] = {"kind": kind_of(e["name"]), "mesh": use_mesh}
        if rig:
            build_meta[nm]["bone_parent"] = rlay[nm]["parent_bone"]
            build_meta[nm]["joint"] = bool(rlay[nm]["joint"])
            build_meta[nm]["role"] = rlay[nm]["role"]

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
        if deform:
            # candidate 0e:再讓軟件/特效 mesh 本身 deform(真實布料律動場轉移),非只被控制骨搬動
            from gen_deform import build_deform, load_source_field
            us, fl, _ = load_source_field(*deform_src)
            build_deform(skeleton, spec["3_motion_storyboard"], us, fl)
    json.dump(skeleton, open(os.path.join(out_dir, "skeleton.json"), "w"),
              ensure_ascii=False, indent=1)
    json.dump(build_meta, open(os.path.join(out_dir, "build_meta.json"), "w"), ensure_ascii=False, indent=1)
    summary = {"out": out_dir, "canvas": [W, H], "atlas_page": [PW, PH],
               "parts": len(parts),
               "mesh_parts": [names[i] for i in order if geo.get(metas[i]["name"], "").startswith("mesh")],
               "region_parts": [names[i] for i in order if not geo.get(metas[i]["name"], "").startswith("mesh")]}
    if rig:
        summary["rig_root"] = f"b_{body}"
        summary["rig_joints"] = {f"b_{nm}": [round(float(rlay[nm]['world'][0]), 1),
                                            round(float(rlay[nm]['world'][1]), 1)]
                                 for nm in rlay if rlay[nm]["joint"]}
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--out", default=None)
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--weighted", action="store_true", help="mesh 件產 weighted(骨綁)mesh + 自動控制骨")
    ap.add_argument("--animate", action="store_true", help="同時由 #3 分鏡生成 animations(candidate 0d)")
    ap.add_argument("--deform", action="store_true", help="candidate 0e:mesh 件產真實律動 deform timeline(需 --animate)")
    ap.add_argument("--rig", action="store_true", help="S5:pivot→bone 父子樹(結構子件綁 body、關節落接觸縫)")
    a = ap.parse_args()
    out = a.out or os.path.join("specs", safe(os.path.splitext(os.path.basename(a.psd))[0]) + "_spine")
    s = build(a.psd, out, a.genre, weighted=a.weighted, animate=a.animate, rig=a.rig, deform=a.deform)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
