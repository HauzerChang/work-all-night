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
from gen_animation import add_animations


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


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


def build(psd_path, out_dir, genre="slot_bigwin", animate=False):
    os.makedirs(out_dir, exist_ok=True)
    parts_dir = os.path.join(out_dir, "_parts")
    psd, manifest, parts = slice_psd(psd_path, parts_dir)     # 切件 PNG(裁到 bbox)+ manifest
    W, H = psd.width, psd.height
    spec = analyze(psd_path, genre)
    geo = {r["part"]: r["geometry"] for r in spec["4_slicing_strategy"]["parts"]}

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
    # z 升序 = 由下而上繪製
    order = sorted(range(len(parts)), key=lambda i: metas[i]["z"])
    for i in order:
        e = metas[i]; nm = names[i]; w, h = sizes[i]
        ox, oy = offsets[i]
        cx = ox + w / 2.0
        cy = oy + h / 2.0
        bone = f"b_{nm}"
        bones.append({"name": bone, "parent": "root",
                      "x": round(cx, 2), "y": round(H - cy, 2)})
        slots.append({"name": nm, "bone": bone, "attachment": nm})
        use_mesh = geo.get(e["name"], "").startswith("mesh")
        if use_mesh:
            part_png = os.path.join(parts_dir, e["file"])
            m = gen_mesh(part_png, mode="auto")
            att = {"type": "mesh", "vertices": m["vertices"], "uvs": m["uvs"],
                   "triangles": m["triangles"], "hull": m["hull"],
                   "width": m["width"], "height": m["height"]}
        else:
            att = {"x": 0, "y": 0, "width": w, "height": h}   # region;bone 已在件中心
        skin[nm] = {nm: att}

    skeleton = {
        "skeleton": {"hash": "gen", "spine": "3.8.75", "x": 0, "y": 0,
                     "width": W, "height": H, "images": "./"},
        "bones": bones, "slots": slots,
        "skins": {"default": skin}, "animations": {},
    }
    if animate:
        add_animations(skeleton, spec)   # #3 分鏡 → In/Loop/Out timeline(見 gen_animation)
    json.dump(skeleton, open(os.path.join(out_dir, "skeleton.json"), "w"),
              ensure_ascii=False, indent=1)
    summary = {"out": out_dir, "canvas": [W, H], "atlas_page": [PW, PH],
               "parts": len(parts), "animations": list(skeleton["animations"].keys()),
               "mesh_parts": [names[i] for i in order if geo.get(metas[i]["name"], "").startswith("mesh")],
               "region_parts": [names[i] for i in order if not geo.get(metas[i]["name"], "").startswith("mesh")]}
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("--out", default=None)
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--animate", action="store_true", help="嵌入 #3 分鏡 → In/Loop/Out 動畫")
    a = ap.parse_args()
    out = a.out or os.path.join("specs", safe(os.path.splitext(os.path.basename(a.psd))[0]) + "_spine")
    s = build(a.psd, out, a.genre, a.animate)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
