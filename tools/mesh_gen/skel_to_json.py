#!/usr/bin/env python3
"""S4 下游:切件 → 完整 Spine 3.8 JSON skeleton 組裝(SkelToJson)。

把 PSD 切件(psd_slice 的 manifest)+ 每件的 mesh/region 決策,組裝成一份**可載入的 Spine 3.8
skeleton JSON**,其 **setup pose == PSD 平面 composite 佈局**(每件放回它在 PSD 的原位)。

固化自 knowledge/s4-psd-to-spine-real.md 揭示的真實生產慣例:
  - slot 命名 = `<namespace>/<圖層名>`(Award 用「機器人拆件」當 namespace 前綴)。
  - 一圖層 ⇄ 一 slot ⇄ 一 attachment;會柔性變形的件做 mesh、剛體件做 region(由 spec 指定)。
  - unweighted mesh 頂點已以件影像中心置中(generate_mesh)→ 把 slot 的 bone 放在該件的 PSD 中心,
    mesh/region 就落回原位。

⚠️ 座標:Spine y-up、以整份 PSD 畫布中心為原點。
   PSD 件中心(px) (l+w/2, t+h/2) → world (cx-W/2, H/2-cy)。bone 放此處、rotation=0。
   (Award 生產檔的 region 有非零 rotation/pose 位移 → 那是**打包/擺姿**決策,非還原平面佈局,屬 S5,不在此。)

驗收(--eval,純 CPU,不需 renderer):
  1. **位置 round-trip**:解析 skeleton,解析式重建每個 attachment 的 world bbox → 轉回 PSD px,
     與 manifest 的 offset/size 比對(中心誤差、尺寸誤差在容差內)。
  2. **結構有效**:每 slot 有合法 bone、skin 內有對應 attachment、JSON 可 json.load。
  3. **mesh 格式閘**:每個 mesh attachment 過 evaluate_mesh 的格式/孤兒/退化條件。
"""
import argparse, json, os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_slice import slice_psd, _premult_diff
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh

SPINE_VER = "3.8.99"


def _piece_center_world(entry, W, H):
    l, t = entry["offset"]; w, h = entry["size"]
    cx, cy = l + w / 2.0, t + h / 2.0
    return round(cx - W / 2.0, 2), round(H / 2.0 - cy, 2)


def build_skeleton(manifest, meshes, namespace, tmp_pieces_dir=None):
    """meshes: {layer_name: mesh_dict}(mesh 件);未列入者 → region。"""
    W, H = manifest["size"]
    bones = [{"name": "root"}]
    slots, atts = [], {}
    for entry in manifest["parts"]:
        name = entry["name"]
        w, h = entry["size"]
        bx, by = _piece_center_world(entry, W, H)
        bone_name = f"b_{name}"
        slot_name = f"{namespace}/{name}"
        bones.append({"name": bone_name, "parent": "root", "x": bx, "y": by})
        slots.append({"name": slot_name, "bone": bone_name, "attachment": slot_name})
        if name in meshes:
            m = meshes[name]
            atts[slot_name] = {slot_name: {
                "type": "mesh", "uvs": m["uvs"], "triangles": m["triangles"],
                "vertices": m["vertices"], "hull": m["hull"],
                "width": int(m["width"]), "height": int(m["height"])}}
        else:  # region:置中於自身 bone,還原平面佈局 rotation=0
            atts[slot_name] = {slot_name: {
                "x": 0, "y": 0, "rotation": 0, "width": int(w), "height": int(h)}}
    return {
        "skeleton": {"spine": SPINE_VER, "width": W, "height": H, "images": "./images/"},
        "bones": bones, "slots": slots,
        "skins": [{"name": "default", "attachments": atts}],
        "animations": {"setup": {}},
    }


def assemble(psd_path, spec, namespace, tmp_dir):
    """spec: {layer_name: 'mesh'|'region'}(未列 → region)。回傳 (skeleton, manifest)。"""
    _, manifest, sliced = slice_psd(psd_path, tmp_dir)
    meshes = {}
    for entry, _ in sliced:
        if spec.get(entry["name"]) == "mesh":
            png = os.path.join(tmp_dir, entry["file"])
            meshes[entry["name"]] = gen_v2(png, mode="auto")
    return build_skeleton(manifest, meshes, namespace), manifest


# ---------- 驗收:位置 round-trip(解析式,無 renderer) ----------

def _bones_xy(skeleton):
    return {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in skeleton["bones"]}


def _attachment_world_bbox(att, bx, by):
    """回傳 attachment **影像框**(image frame)的 world (minX,minY,maxX,maxY)。
    量的是「這件的來源影像被放回哪」— mesh 與 region 皆以 width/height 為影像框、置中於 bone
    (mesh 頂點以影像中心置中、region x/y=0),故兩者一致:框 = 中心 ± (w/2,h/2)。
    ⚠️ 不用 mesh 頂點外接框:那是 alpha 輪廓形狀,本就 ≤ 矩形框,非組裝誤差。bone rotation 假設 0。"""
    w, h = att["width"], att["height"]
    cx, cy = bx + att.get("x", 0), by + att.get("y", 0)
    r = math.radians(att.get("rotation", 0))
    xs, ys = [], []
    for lx, ly in [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]:
        xs.append(cx + lx * math.cos(r) - ly * math.sin(r))
        ys.append(cy + lx * math.sin(r) + ly * math.cos(r))
    xs, ys = np.array(xs), np.array(ys)
    return xs.min(), ys.min(), xs.max(), ys.max()


def evaluate(skeleton, manifest, pos_tol=1.5, size_tol=2.0,
             psd_path=None, pieces_dir=None, render_out=None, raster_mae_tol=2.0):
    W, H = manifest["size"]
    by_slot_bone = {s["name"]: s["bone"] for s in skeleton["slots"]}
    bones = _bones_xy(skeleton)
    atts = skeleton["skins"][0]["attachments"]
    ns = skeleton["slots"][0]["name"].rsplit("/", 1)[0] if skeleton["slots"] else ""

    pos_rows, worst_center, worst_size = [], 0.0, 0.0
    mesh_fmt_pass, mesh_checked = True, 0
    for entry in manifest["parts"]:
        slot = f"{ns}/{entry['name']}"
        att = atts[slot][slot]
        bx, by = bones[by_slot_bone[slot]]
        minx, miny, maxx, maxy = _attachment_world_bbox(att, bx, by)
        # world → PSD px
        px_l, px_r = minx + W/2, maxx + W/2
        py_t, py_b = H/2 - maxy, H/2 - miny   # y 上翻
        rec_off = (px_l, py_t); rec_size = (px_r - px_l, py_b - py_t)
        exp_off, exp_size = entry["offset"], entry["size"]
        # 中心誤差
        rec_c = (rec_off[0] + rec_size[0]/2, rec_off[1] + rec_size[1]/2)
        exp_c = (exp_off[0] + exp_size[0]/2, exp_off[1] + exp_size[1]/2)
        cerr = math.hypot(rec_c[0]-exp_c[0], rec_c[1]-exp_c[1])
        serr = max(abs(rec_size[0]-exp_size[0]), abs(rec_size[1]-exp_size[1]))
        worst_center = max(worst_center, cerr); worst_size = max(worst_size, serr)
        pos_rows.append({"slot": slot, "type": att.get("type", "region"),
                         "center_err_px": round(cerr, 3), "size_err_px": round(serr, 3)})
        if att.get("type") == "mesh":
            mesh_checked += 1
            m = {"vertices": att["vertices"], "uvs": att["uvs"], "triangles": att["triangles"],
                 "hull": att["hull"], "width": att["width"], "height": att["height"]}
            mask = np.zeros((att["height"], att["width"]), np.uint8)  # 只查格式,不需真 mask
            r = eval_mesh(m, mask, vertex_budget=256)["criteria"]
            ok = r["AC4_format"]["pass"] and r["AC2c_orphans"]["pass"] and r["AC2b_degenerate"]["pass"]
            mesh_fmt_pass = mesh_fmt_pass and ok
            pos_rows[-1]["mesh_fmt_ok"] = ok

    # 結構有效
    bone_names = {b["name"] for b in skeleton["bones"]}
    struct = {
        "all_slots_have_bone": all(s["bone"] in bone_names for s in skeleton["slots"]),
        "all_slots_have_attachment": all(f"{ns}/{e['name']}" in atts for e in manifest["parts"]),
        "json_serializable": True,
    }
    try:
        json.dumps(skeleton, ensure_ascii=False)
    except Exception:
        struct["json_serializable"] = False

    pos_pass = worst_center <= pos_tol and worst_size <= size_tol
    struct_pass = all(struct.values())

    # AC 光柵重建:由 skeleton 位置重合成 → 對 PSD composite premult-MAE(可選,需 psd+pieces)
    raster = None
    if psd_path and pieces_dir:
        recon = render_setup(skeleton, manifest, pieces_dir, render_out)
        ref = PSDImage.open(psd_path).composite().convert("RGBA").resize((W, H))
        rgb_mae, alpha_mae = _premult_diff(recon, ref)
        raster = {"pass": rgb_mae < raster_mae_tol and alpha_mae < raster_mae_tol,
                  "premult_rgb_mae": round(rgb_mae, 4), "alpha_mae": round(alpha_mae, 4),
                  "thresh": raster_mae_tol, "render": render_out}

    overall = pos_pass and struct_pass and mesh_fmt_pass and (raster is None or raster["pass"])
    out = {
        "overall_pass": overall,
        "AC_position": {"pass": pos_pass, "worst_center_err_px": round(worst_center, 3),
                        "worst_size_err_px": round(worst_size, 3),
                        "pos_tol": pos_tol, "size_tol": size_tol, "rows": pos_rows},
        "AC_structure": {"pass": struct_pass, **struct,
                         "bones": len(skeleton["bones"]), "slots": len(skeleton["slots"])},
        "AC_mesh_format": {"pass": mesh_fmt_pass, "mesh_attachments": mesh_checked},
    }
    if raster is not None:
        out["AC_raster_reconstruction"] = raster
    return out


def render_setup(skeleton, manifest, pieces_dir, out_png=None):
    """由 skeleton 的 setup pose 位置(非 manifest)把各件 PNG 重新合成平面佈局。
    件影像框 = bone ± (w/2,h/2) → 還原 PSD px 的左上角 → 依 z 序 alpha-over 疊圖。
    這獨立於 manifest 重算位置,證明 skeleton 已編碼正確佈局。回傳合成 RGBA。"""
    W, H = manifest["size"]
    by_slot_bone = {s["name"]: s["bone"] for s in skeleton["slots"]}
    bones = _bones_xy(skeleton)
    atts = skeleton["skins"][0]["attachments"]
    ns = skeleton["slots"][0]["name"].rsplit("/", 1)[0] if skeleton["slots"] else ""
    fmap = {e["name"]: e for e in manifest["parts"]}          # z / file
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for entry in sorted(manifest["parts"], key=lambda e: e["z"]):
        slot = f"{ns}/{entry['name']}"
        att = atts[slot][slot]
        bx, by = bones[by_slot_bone[slot]]
        minx, miny, maxx, maxy = _attachment_world_bbox(att, bx, by)
        left = int(round(minx + W/2)); top = int(round(H/2 - maxy))  # world→px 左上
        im = Image.open(os.path.join(pieces_dir, entry["file"])).convert("RGBA")
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(im, (left, top))
        canvas = Image.alpha_composite(canvas, layer)
    if out_png:
        canvas.save(out_png)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--namespace", default="機器人拆件")
    ap.add_argument("--mesh-parts", nargs="*", default=["光暈", "身體", "左手"],
                    help="做成 mesh 的圖層名;其餘為 region")
    ap.add_argument("--out", default=None, help="寫出 skeleton JSON 路徑")
    ap.add_argument("--tmp", default="/tmp/robot_parts")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--render", default=None, help="輸出 setup-pose 重建 PNG 路徑(啟用光柵重建 AC)")
    a = ap.parse_args()
    spec = {p: "mesh" for p in a.mesh_parts}
    skeleton, manifest = assemble(a.psd, spec, a.namespace, a.tmp)
    if a.out:
        json.dump(skeleton, open(a.out, "w"), ensure_ascii=False)
    if a.eval:
        rep = evaluate(skeleton, manifest, psd_path=a.psd, pieces_dir=a.tmp, render_out=a.render)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)
    print(json.dumps({"bones": len(skeleton["bones"]), "slots": len(skeleton["slots"]),
                      "out": a.out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
