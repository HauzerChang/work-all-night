#!/usr/bin/env python3
"""S3×S4 — SkelToJson:分層 PSD → 各部位件 → 生成 mesh/region → **完整 Spine 3.8 skeleton JSON**。

補齊 pipeline 缺的最後一環:先前能「切件(psd_slice)」+「件→mesh(generate_mesh)」,
但沒有把件自動組裝成可被 Spine runtime 載入的完整骨架 JSON。本工具固化 Award 真實慣例:

  1. **slot 命名 = `<PSD檔名>/<圖層名>`**(Award 用 PSD 名當 namespace 前綴,見 s4-psd-to-spine-real.md)。
  2. **一圖層 ⇄ 一 slot ⇄ 一 attachment**(同名);draw order = slots 陣列順序 = PSD 由下而上(z)。
  3. **mesh vs region 由呼叫端指定**(美術決定):mesh 件跑 generate_mesh(覆蓋率驅動 auto-epsilon);
     region 件放矩形 attachment。
  4. **每件一根骨**,置於該件在畫布的世界中心(offset+size/2 → 中心原點、y-up),root 在畫布中心。
     → mesh 頂點是件-local 置中(generate_mesh 既有格式),加骨骼平移即還原原圖版面。

⚠️ Spine 3.8 格式雷點(見 CLAUDE.md):unweighted mesh `len(vertices)==len(uvs)`、hull 頂點排最前、
   三角索引在範圍;skins 為 list `[{"name":"default","attachments":{slot:{name:{...}}}}]`;y 上翻。

⚠️ +2px 是 **atlas packer padding**(runtime 打包產物),非 authoring 尺寸 → attachment width/height
   採件的真實像素尺寸;對 Award 真值做 parity 時容忍 ±2px。
"""
import argparse, json, os, sys, tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh import generate_auto
from evaluate_mesh import evaluate, load_mask

DEFAULT_MESH = ["光暈", "身體", "左手"]   # Award 機器人拆件的 mesh 分配(其餘為 region)


def region_attachment(w, h):
    return {"type": "region", "x": 0.0, "y": 0.0, "rotation": 0.0,
            "width": int(w), "height": int(h)}


def assemble(psd_path, mesh_layers, out_dir, target_iou=0.97, prefix=None):
    # namespace 前綴是 authoring 選擇(美術對件群的命名),未必等於檔名。
    # Award 真值用中文群名 `機器人拆件`;repo 檔名為 robot_parts → 需可覆寫。
    stem = prefix or os.path.splitext(os.path.basename(psd_path))[0]
    psd, manifest, parts = slice_psd(psd_path, out_dir)  # 寫出各件 PNG + manifest
    manifest["prefix"] = stem                            # 供 validator 用實際前綴
    W, H = manifest["size"]

    bones = [{"name": "root"}]
    slots = []
    attachments = {}   # {slot: {name: attachment}}
    part_meta = {}     # slot -> {type, iou, eps}

    for entry, _ in parts:      # parts 依 z 由下而上 → slots 順序即 draw order
        layer = entry["name"]
        slot_name = f"{stem}/{layer}"
        ox, oy = entry["offset"]; pw, ph = entry["size"]
        cx, cy = ox + pw / 2.0, oy + ph / 2.0
        bone_name = f"{slot_name}_bone"
        bones.append({"name": bone_name, "parent": "root",
                      "x": round(cx - W / 2.0, 2), "y": round(H / 2.0 - cy, 2)})
        slots.append({"name": slot_name, "bone": bone_name, "attachment": slot_name})

        if layer in mesh_layers:
            png = os.path.join(out_dir, entry["file"])
            mesh, meta = generate_auto(png, target_iou=target_iou)   # 覆蓋率驅動(單一真相來源)
            att = {k: mesh[k] for k in ("type", "uvs", "triangles", "vertices", "hull", "width", "height")}
            attachments[slot_name] = {slot_name: att}
            part_meta[slot_name] = {"type": "mesh", **meta}
        else:
            attachments[slot_name] = {slot_name: region_attachment(pw, ph)}
            part_meta[slot_name] = {"type": "region"}

    skel = {
        "skeleton": {"hash": "", "spine": "3.8.99", "x": round(-W / 2.0, 2), "y": round(-H / 2.0, 2),
                     "width": W, "height": H, "images": "./", "audio": ""},
        "bones": bones,
        "slots": slots,
        "skins": [{"name": "default", "attachments": attachments}],
        "animations": {},
    }
    return skel, manifest, part_meta


# ---------------- 自驗閘 ----------------
def validate_skeleton(skel, manifest, part_meta, out_dir, award_path=None):
    stem_parts = {s["name"]: s for s in skel["slots"]}
    skin = skel["skins"][0]["attachments"]
    bone_names = {b["name"] for b in skel["bones"]}
    W, H = manifest["size"]
    issues = []

    # AC1 schema:slot→bone/attachment 存在;mesh/region 欄位有效
    for slot in skel["slots"]:
        if slot["bone"] not in bone_names:
            issues.append(f"{slot['name']}: bone 不存在")
        name = slot["attachment"]
        if slot["name"] not in skin or name not in skin[slot["name"]]:
            issues.append(f"{slot['name']}: attachment 缺失"); continue
        a = skin[slot["name"]][name]
        if a.get("type") == "mesh":
            nv = len(a["uvs"]) // 2
            if len(a["vertices"]) != len(a["uvs"]):
                issues.append(f"{name}: 非 unweighted(len(vertices)!=len(uvs))")
            if not (0 < a["hull"] <= nv):
                issues.append(f"{name}: hull 越界 {a['hull']}/{nv}")
            tris = np.array(a["triangles"]).reshape(-1, 3)
            if tris.max() >= nv or tris.min() < 0:
                issues.append(f"{name}: 三角索引越界")
            used = set(int(i) for i in tris.flatten())
            if len(used) != nv:
                issues.append(f"{name}: 有孤兒頂點 {nv-len(used)}")
        else:
            if not (a["width"] > 0 and a["height"] > 0):
                issues.append(f"{name}: region 尺寸非法")
    ac1 = {"pass": not issues, "issues": issues,
           "bones": len(skel["bones"]), "slots": len(skel["slots"]),
           "spine": skel["skeleton"]["spine"]}

    # AC2 loader round-trip:用「讀真實資產」的存取路徑重載 mesh,跑覆蓋率(對件自身 alpha)
    rt = {}
    rt_pass = True
    for slot, meta in part_meta.items():
        if meta["type"] != "mesh":
            continue
        a = skin[slot][slot]                        # skins[0].attachments[slot][name] — 同真實資產路徑
        mesh = {k: a[k] for k in ("vertices", "uvs", "triangles", "hull", "width", "height")}
        fn = next(e["file"] for e in manifest["parts"] if f"{manifest_stem(manifest)}/{e['name']}" == slot)
        mask = load_mask(os.path.join(out_dir, fn))
        iou = evaluate(mesh, mask, vertex_budget=len(mesh["uvs"]) // 2 + 1)["criteria"]["AC1_iou"]["value"]
        rt[slot] = {"reloaded_iou": round(iou, 4), "pass": iou >= 0.95}
        rt_pass = rt_pass and iou >= 0.95
    ac2 = {"pass": rt_pass, "per_mesh": rt}

    # AC3 layout:骨骼世界位置還原件 PSD 中心(構造正確性)
    layout_ok = True
    stem = manifest_stem(manifest)
    bmap = {b["name"]: b for b in skel["bones"]}
    for e in manifest["parts"]:
        slot = f"{stem}/{e['name']}"
        b = bmap[f"{slot}_bone"]
        cx = b["x"] + W / 2.0; cy = H / 2.0 - b["y"]
        exp = (e["offset"][0] + e["size"][0] / 2.0, e["offset"][1] + e["size"][1] / 2.0)
        if abs(cx - exp[0]) > 0.5 or abs(cy - exp[1]) > 0.5:
            layout_ok = False
    ac3 = {"pass": layout_ok, "note": "每件骨骼世界中心 == PSD 版面中心(±0.5px)"}

    res = {"AC1_schema": ac1, "AC2_roundtrip": ac2, "AC3_layout": ac3}

    # AC4(可選)對 Award 真值結構 parity
    if award_path and os.path.exists(award_path):
        aw = json.load(open(award_path)); ask = aw["skins"]; ask = ask[0] if isinstance(ask, list) else ask
        aatts = ask.get("attachments", ask)
        parity = []; par_pass = True
        for slot, meta in part_meta.items():
            if slot not in aatts or slot not in aatts.get(slot, {}) and slot not in aatts:
                pass
            awa = aatts.get(slot, {}).get(slot)
            if awa is None:
                parity.append({"slot": slot, "pass": False, "why": "Award 無此 slot"}); par_pass = False; continue
            aw_type = awa.get("type", "region")
            our = skin[slot][slot]; our_type = our.get("type", "region")
            type_ok = aw_type == our_type
            dw = abs(our["width"] - awa["width"]); dh = abs(our["height"] - awa["height"])
            size_ok = dw <= 2 and dh <= 2
            parity.append({"slot": slot, "type": f"{our_type}=={aw_type}? {type_ok}",
                           "size_ours": [our["width"], our["height"]], "size_award": [awa["width"], awa["height"]],
                           "size_within_2px": size_ok, "pass": type_ok and size_ok})
            par_pass = par_pass and type_ok and size_ok
        res["AC4_award_parity"] = {"pass": par_pass, "per_slot": parity}

    overall = all(v["pass"] for v in res.values())
    return {"overall_pass": overall, "criteria": res}


def manifest_stem(manifest):
    return manifest.get("prefix") or os.path.splitext(manifest["source"])[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("-o", "--out", default=None, help="輸出 skeleton JSON 路徑")
    ap.add_argument("--parts-dir", default=None, help="切件 PNG 輸出目錄(預設用暫存)")
    ap.add_argument("--mesh", nargs="*", default=DEFAULT_MESH, help="要做成 mesh 的圖層名")
    ap.add_argument("--prefix", default=None, help="slot namespace 前綴(預設用檔名;Award 真值為 機器人拆件)")
    ap.add_argument("--target-iou", type=float, default=0.97)
    ap.add_argument("--award", default="assets/Award.json", help="對照真值(parity 檢查)")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()

    parts_dir = a.parts_dir or tempfile.mkdtemp(prefix="skel_parts_")
    skel, manifest, part_meta = assemble(a.psd, a.mesh, parts_dir, a.target_iou, a.prefix)
    out = a.out or (os.path.splitext(a.psd)[0] + "_skeleton.json")
    json.dump(skel, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"寫出 {out}: {len(skel['bones'])} bones / {len(skel['slots'])} slots / "
          f"{sum(1 for m in part_meta.values() if m['type']=='mesh')} mesh")

    if not a.no_validate:
        rep = validate_skeleton(skel, manifest, part_meta, parts_dir, a.award)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
