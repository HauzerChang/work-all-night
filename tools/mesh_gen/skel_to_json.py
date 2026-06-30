#!/usr/bin/env python3
"""S4→S3 銜接:SkelToJson —— 切件(psd_slice manifest)→ 可載入的 Spine 3.8 資產集。

把已對真實生產檔(Award)驗證過的慣例固化成寫出工具:
  - slot/attachment 命名 = `<PSD檔名(去副檔名)>/<圖層名>`(namespace 前綴,見 s4-psd-to-spine-real)。
  - 一件 → 一 slot → 一 bone(置於該件中心)→ 一 attachment(置中於該 bone,世界位置正確)。
  - draw order = PSD z(由下而上)。
  - **mesh vs region**:預設 region;`--mesh <圖層名>` 的件改用 S3 `generate_mesh_v2` 生成 mesh attachment。
  - 同時打包一份**簡單 shelf atlas(+2px gap = padding,無旋轉/無縮放,無損)**+ 合成 sheet PNG,
    使 json+atlas+png 成為**可載入的整組**(生產 packer 的 ~0.70 縮放/旋轉非正確性所需,故從略)。

座標:PSD y-down、原點左上;Spine y-up、原點畫布中心。
  件中心(px) cx=l+w/2, cy=t+h/2 → bone (cx-W/2, H/2-cy);attachment 置中(region x=y=0;
  mesh 頂點已是「件中心為原點、y 上翻」與 bone 對齊)。

自驗閘(AC):重新載回輸出 → ① 結構/數量/命名 ② attachment 尺寸==件 ③ 每 attachment 有對應
atlas region 且尺寸吻合 ④ 從產出的 atlas+png 切回各件 alpha-IoU vs 原件 ≈1(端到端無損 round-trip)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from PIL import Image
from atlas_crop import parse_atlas, extract


def slot_name(psd_stem, layer):
    return f"{psd_stem}/{layer}"


def shelf_pack(sizes, pad=2, max_w=2048):
    """簡單 shelf packer:回傳 {idx:(x,y)} 與 sheet (W,H)。無旋轉。pad = 各件間隙(= padding)。"""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])  # 高的先放
    placements = {}
    x = pad; y = pad; shelf_h = 0; sheet_w = pad
    for i in order:
        w, h = sizes[i]
        if x + w + pad > max_w and x > pad:      # 換層
            y += shelf_h + pad; x = pad; shelf_h = 0
        placements[i] = (x, y)
        x += w + pad
        shelf_h = max(shelf_h, h)
        sheet_w = max(sheet_w, x)
    sheet_h = y + shelf_h + pad
    return placements, int(sheet_w), int(sheet_h)


def build(manifest_path, mesh_layers=None, gen_fn=None):
    mesh_layers = set(mesh_layers or [])
    mdir = os.path.dirname(manifest_path)
    man = json.load(open(manifest_path))
    psd_stem = os.path.splitext(man["source"])[0]
    W, H = man["size"]
    parts = man["parts"]

    bones = [{"name": "root"}]
    slots = []
    attachments = {}
    sizes = [tuple(p["size"]) for p in parts]
    placements, sheet_w, sheet_h = shelf_pack(sizes)

    atlas_regions = []          # (name, x, y, w, h)
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    for i, p in enumerate(sorted(parts, key=lambda e: e["z"])):
        layer = p["name"]; w, h = p["size"]; l, t = p["offset"]
        sn = slot_name(psd_stem, layer)
        bx = round((l + w / 2.0) - W / 2.0, 2)
        by = round(H / 2.0 - (t + h / 2.0), 2)
        bones.append({"name": sn, "parent": "root", "x": bx, "y": by})
        slots.append({"name": sn, "bone": sn, "attachment": sn})

        if layer in mesh_layers and gen_fn is not None:
            png = os.path.join(mdir, p["file"])
            m = gen_fn(png)
            att = {"type": "mesh", "uvs": m["uvs"], "triangles": m["triangles"],
                   "vertices": m["vertices"], "hull": m["hull"],
                   "width": int(w), "height": int(h)}
        else:
            att = {"x": 0, "y": 0, "rotation": 0, "width": int(w), "height": int(h)}
        attachments[sn] = {sn: att}

    # 打包 atlas region + 貼到 sheet(原始件,無縮放/旋轉)
    idx_by_z = {id(p): i for i, p in enumerate(parts)}
    for i, p in enumerate(parts):
        layer = p["name"]; w, h = p["size"]
        x, y = placements[i]
        sn = slot_name(psd_stem, layer)
        atlas_regions.append((sn, x, y, w, h))
        im = Image.open(os.path.join(mdir, p["file"])).convert("RGBA")
        sheet.paste(im, (x, y))

    skel = {
        "skeleton": {"spine": "3.8.99", "width": int(W), "height": int(H), "images": "./"},
        "bones": bones,
        "slots": slots,
        "skins": [{"name": "default", "attachments": attachments}],
        "animations": {"animation": {}},
    }
    return skel, atlas_regions, sheet, (sheet_w, sheet_h)


def write_atlas(path, png_name, regions, sheet_size):
    sw, sh = sheet_size
    lines = [png_name, f"size: {sw},{sh}", "format: RGBA8888",
             "filter: Linear,Linear", "repeat: none"]
    for (name, x, y, w, h) in regions:
        lines += [name, f"  rotate: false", f"  xy: {x}, {y}", f"  size: {w}, {h}",
                  f"  orig: {w}, {h}", f"  offset: 0, 0", f"  index: -1"]
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def write_set(skel, atlas_regions, sheet, sheet_size, out_dir, name="skel"):
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, f"{name}.json")
    ap = os.path.join(out_dir, f"{name}.atlas")
    pp = os.path.join(out_dir, f"{name}.png")
    json.dump(skel, open(jp, "w"), ensure_ascii=False, indent=1)
    sheet.save(pp)
    write_atlas(ap, f"{name}.png", atlas_regions, sheet_size)
    return jp, ap, pp


def verify(jp, ap, pp, manifest_path):
    """端到端自驗:結構/命名/尺寸 + atlas region 對應 + 切回各件 alpha-IoU ≈1。"""
    man = json.load(open(manifest_path)); mdir = os.path.dirname(manifest_path)
    psd_stem = os.path.splitext(man["source"])[0]
    parts = man["parts"]
    sk = json.load(open(jp))
    regions = parse_atlas(ap)
    res = {}

    # AC0 結構完整性(可載入性):slot.bone 存在、mesh 三角索引在頂點界內、uvs 偶數長
    bone_names = {b["name"] for b in sk["bones"]}
    integ = True; problems = []
    for s in sk["slots"]:
        if s["bone"] not in bone_names:
            integ = False; problems.append(f"slot {s['name']} bone 缺失")
    for sn, atts in sk["skins"][0]["attachments"].items():
        for an, att in atts.items():
            if att.get("type") == "mesh":
                nv = len(att["uvs"]) // 2
                if len(att["uvs"]) % 2 or len(att["triangles"]) % 3:
                    integ = False; problems.append(f"{sn} uvs/tris 長度不整除")
                if att["triangles"] and max(att["triangles"]) >= nv:
                    integ = False; problems.append(f"{sn} 三角索引越界")
    res["AC0_integrity"] = {"pass": integ, "problems": problems}

    # AC1 結構/數量/命名
    want = [slot_name(psd_stem, p["name"]) for p in parts]
    slot_names = [s["name"] for s in sk["slots"]]
    skin_att = sk["skins"][0]["attachments"]
    res["AC1_structure"] = {
        "pass": (len(sk["bones"]) == len(parts) + 1 and sorted(slot_names) == sorted(want)
                 and sorted(skin_att.keys()) == sorted(want)),
        "bones": len(sk["bones"]), "slots": len(slot_names), "expect_slots": len(want),
    }

    # AC2 attachment 尺寸 == 件
    size_ok = True; size_detail = []
    for p in parts:
        sn = slot_name(psd_stem, p["name"]); w, h = p["size"]
        att = skin_att[sn][sn]
        ok = int(att["width"]) == int(w) and int(att["height"]) == int(h)
        size_ok &= ok
        size_detail.append({"slot": sn, "type": att.get("type", "region"),
                            "wh": [att["width"], att["height"]], "ok": ok})
    res["AC2_attach_size"] = {"pass": size_ok, "parts": size_detail}

    # AC3 每 attachment 有對應 atlas region 且尺寸吻合
    reg_ok = True
    for p in parts:
        sn = slot_name(psd_stem, p["name"]); w, h = p["size"]
        r = regions.get(sn)
        if not r:
            reg_ok = False; continue
        rw, rh = [int(t) for t in r["size"].split(",")]
        reg_ok &= (rw == int(w) and rh == int(h))
    res["AC3_atlas_region"] = {"pass": reg_ok, "regions": len(regions)}

    # AC4 端到端:從產出 atlas+png 切回各件,alpha-IoU vs 原件 ≈1(無損 round-trip)
    ious = []
    for p in parts:
        sn = slot_name(psd_stem, p["name"])
        sub = extract(ap, pp, sn)
        a_re = (sub[:, :, 3] > 8) if sub.ndim == 3 and sub.shape[2] == 4 else None
        src = cv2.imread(os.path.join(mdir, p["file"]), cv2.IMREAD_UNCHANGED)
        a_src = (src[:, :, 3] > 8)
        if a_re.shape != a_src.shape:
            ious.append(0.0); continue
        inter = np.logical_and(a_re, a_src).sum(); uni = np.logical_or(a_re, a_src).sum()
        ious.append(float(inter / max(uni, 1)))
    res["AC4_roundtrip_iou"] = {"pass": all(v >= 0.99 for v in ious),
                                "min_iou": round(min(ious), 4), "per_part": [round(v, 4) for v in ious]}

    overall = all(v["pass"] for v in res.values())
    return {"overall_pass": overall, "criteria": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help="psd_slice -o 產出的 manifest.json")
    ap.add_argument("-o", "--out", default="skel_out")
    ap.add_argument("--name", default="skel")
    ap.add_argument("--mesh", nargs="*", default=[], help="這些圖層名改用 S3 mesh(其餘 region)")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    gen = None
    if a.mesh:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")
    skel, regions, sheet, ssz = build(a.manifest, a.mesh, gen)
    jp, atp, pp = write_set(skel, regions, sheet, ssz, a.out, a.name)
    print(f"寫出: {jp}\n      {atp}\n      {pp}  sheet {ssz[0]}x{ssz[1]}")
    if a.verify:
        rep = verify(jp, atp, pp, a.manifest)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
