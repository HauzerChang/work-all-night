#!/usr/bin/env python3
"""S5(可自動部分)— 由件的 alpha 重疊推出**骨架階層草案** + 關節(pivot)候選。

PLAN.md 明示:**骨架 pivot 是唯一真正卡死、需人微調處**。因此本工具只做「可確定性自動化」的部分,
把主觀決策明確標記為待人:

  自動(確定性):
    1. 件重疊圖 — 兩件的畫布 alpha 是否重疊(重疊像素數)。
    2. 生成樹 — 從 root 件 BFS,每件的 parent = 通往 root 路徑上與它重疊的件。
    3. 關節候選 — 每件與其 parent 的**重疊區質心** = pivot 草案(肢體接到軀幹的接點)。
    4. 重寫 bones 成父子鏈,bone local x/y 由 parent 世界位置反推 → **世界位置不變、版面保真**。

  待人(A 類岔路,明確 flag):
    - root 件的選擇(預設取重疊度最高者;背景件如光暈可能誤選 → 可 --root 覆寫)。
    - 每個關節的**精確 pivot 微調**(草案給重疊質心,`_needs_human_pivot=true`)。
    - mesh **權重綁定**(目前 attachment 仍 unweighted;BBW 綁定為後續步驟)。

產出的 rig 草案骨架用 `evaluate_skeleton` 驗證仍是合法骨架樹(單一 root/無環)。
"""
import argparse, json, os, sys, tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from skel_to_json import assemble, DEFAULT_MESH
from evaluate_skeleton import evaluate_skeleton


def part_masks(manifest, parts_dir):
    """每件放到畫布(WxH)的二值 alpha。"""
    W, H = manifest["size"]
    masks = {}
    for e in manifest["parts"]:
        img = cv2.imread(os.path.join(parts_dir, e["file"]), cv2.IMREAD_UNCHANGED)
        a = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
            (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img)
        canvas = np.zeros((H, W), np.uint8)
        l, t = e["offset"]; w, h = e["size"]
        canvas[t:t + h, l:l + w] = (a > 8).astype(np.uint8)
        masks[e["name"]] = canvas
    return masks


def overlap_graph(masks):
    names = list(masks)
    ov = {n: {} for n in names}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            inter = int(np.logical_and(masks[names[i]], masks[names[j]]).sum())
            if inter > 0:
                ov[names[i]][names[j]] = inter
                ov[names[j]][names[i]] = inter
    return ov


def overlap_centroid(mask_a, mask_b):
    inter = np.logical_and(mask_a, mask_b)
    ys, xs = np.where(inter)
    if not len(xs):
        return None
    return float(xs.mean()), float(ys.mean())


def spanning_tree(ov, root):
    """BFS:parent[child] = 先發現它的、與它重疊的節點。回傳 parent map(root->None)。"""
    parent = {root: None}
    frontier = [root]
    while frontier:
        nxt = []
        for u in frontier:
            for v, w in sorted(ov[u].items(), key=lambda kv: -kv[1]):  # 重疊大者優先
                if v not in parent:
                    parent[v] = u; nxt.append(v)
        frontier = nxt
    return parent


def build_rig(psd_path, mesh_layers, out_dir, prefix, root_layer=None, target_iou=0.97,
              pivot_overrides=None):
    skel, manifest, part_meta = assemble(psd_path, mesh_layers, out_dir, target_iou, prefix)
    stem = prefix or os.path.splitext(os.path.basename(psd_path))[0]
    W, H = manifest["size"]
    masks = part_masks(manifest, out_dir)
    ov = overlap_graph(masks)

    # root:預設取重疊度(連接數)最高者,tie 取 alpha 面積最大 → 通常是軀幹/主體
    degree = {n: len(ov[n]) for n in masks}
    area = {n: int(masks[n].sum()) for n in masks}
    root = root_layer or max(masks, key=lambda n: (degree[n], area[n]))
    if root not in masks:
        raise SystemExit(f"root 件不存在: {root}; 可選: {list(masks)}")

    parent = spanning_tree(ov, root)
    # 孤立件(與 root 連通分量外)→ 掛 root,flag
    isolated = [n for n in masks if n not in parent]
    for n in isolated:
        parent[n] = root

    # 件中心(世界座標,y-up,原點畫布中心)
    def center_world(name):
        e = next(e for e in manifest["parts"] if e["name"] == name)
        cx = e["offset"][0] + e["size"][0] / 2.0
        cy = e["offset"][1] + e["size"][1] / 2.0
        return (cx - W / 2.0, H / 2.0 - cy)

    def px_to_world(px, py):
        return (float(px) - W / 2.0, H / 2.0 - float(py))

    pivot_overrides = pivot_overrides or {}

    # 每件的 pivot(世界):人為覆寫(圖素座標)> 重疊質心草案。root 無 pivot。
    def pivot_world(name):
        if name in pivot_overrides:
            return px_to_world(*pivot_overrides[name]), "human"
        jc = overlap_centroid(masks[name], masks[parent[name]])
        if jc is None:
            return center_world(name), "fallback_center"
        return (jc[0] - W / 2.0, H / 2.0 - jc[1]), "draft_centroid"

    # bone 原點(世界):**非 root 件 = pivot(旋轉中心)**;root 件 = 件中心。
    origin_w, pivots, pivot_src = {}, {}, {}
    for name in masks:
        if parent[name] is None:
            origin_w[name] = center_world(name); pivots[name] = None; pivot_src[name] = None
        else:
            pv, src = pivot_world(name)
            origin_w[name] = pv; pivots[name] = pv; pivot_src[name] = src

    # 重寫 bones:local = 自身原點 - parent 原點;attachment 幾何平移 (件中心 - 自身原點)
    # → bone 旋轉繞 pivot,且 θ=0 時世界版面不變。
    bones = [{"name": "root"}]
    skin = skel["skins"][0]["attachments"]
    rig_report = []
    for name in masks:
        slot = f"{stem}/{name}"; bone = f"{slot}_bone"; p = parent[name]
        po = (0.0, 0.0) if p is None else origin_w[p]
        pb = "root" if p is None else f"{stem}/{p}_bone"
        bones.append({"name": bone, "parent": pb,
                      "x": round(origin_w[name][0] - po[0], 2),
                      "y": round(origin_w[name][1] - po[1], 2),
                      "_pivot": None if pivots[name] is None else
                                [round(pivots[name][0], 2), round(pivots[name][1], 2)],
                      "_pivot_source": pivot_src[name]})
        # attachment 幾何相對 bone 原點平移(保住世界位置)
        sx = center_world(name)[0] - origin_w[name][0]
        sy = center_world(name)[1] - origin_w[name][1]
        att = skin[slot][slot]
        if abs(sx) > 1e-6 or abs(sy) > 1e-6:
            if att.get("type") == "mesh":
                v = att["vertices"]
                att["vertices"] = [round(v[i] + (sx if i % 2 == 0 else sy), 3) for i in range(len(v))]
            else:  # region:x/y 為相對 bone 的位移
                att["x"] = round(att.get("x", 0.0) + sx, 2)
                att["y"] = round(att.get("y", 0.0) + sy, 2)
        rig_report.append({"part": name, "parent": p,
                           "pivot": bones[-1]["_pivot"], "pivot_source": pivot_src[name],
                           "isolated": name in isolated})

    skel["bones"] = bones
    report = {"root": root, "root_auto_chosen": root_layer is None,
              "overlap_degree": degree, "hierarchy": rig_report, "isolated": isolated,
              "pivots_overridden": sorted(pivot_overrides), "canvas": [W, H],
              "needs_human": ["pivot 微調(可用 --rig-config 覆寫)", "mesh 權重綁定(目前 unweighted)"]}
    return skel, manifest, part_meta, report


def load_rig_config(path):
    """rig-config(人為調整):{"root": 件名, "pivots": {件名: [px, py](圖素座標), ...}}。"""
    if not path or not os.path.exists(path):
        return None, {}
    cfg = json.load(open(path))
    return cfg.get("root"), (cfg.get("pivots") or {})


def emit_config_template(report, out_path):
    """輸出可人為編輯的 rig-config 範本(預填 root + 草案 pivot 的圖素座標)。"""
    W, H = report["canvas"]
    pivots = {}
    for h in report["hierarchy"]:
        if h["pivot"] is not None:   # world → 圖素(供人依圖調整)
            pivots[h["part"]] = [round(h["pivot"][0] + W / 2.0, 1), round(H / 2.0 - h["pivot"][1], 1)]
    tmpl = {"_note": "pivots 為圖素座標[px,py](原點左上);改數值即人為微調 pivot;root 可改件名",
            "root": report["root"], "pivots": pivots}
    json.dump(tmpl, open(out_path, "w"), ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--parts-dir", default=None)
    ap.add_argument("--mesh", nargs="*", default=DEFAULT_MESH)
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--root", default=None, help="指定 root 件(預設自動:重疊度最高)")
    ap.add_argument("--rig-config", default=None,
                    help="人為調整設定 JSON(root + pivots 圖素座標);覆蓋 --root")
    ap.add_argument("--emit-config", default=None, help="輸出可編輯的 rig-config 範本到此路徑")
    a = ap.parse_args()
    cfg_root, cfg_pivots = load_rig_config(a.rig_config)
    root = cfg_root or a.root
    parts_dir = a.parts_dir or tempfile.mkdtemp(prefix="rig_parts_")
    skel, manifest, part_meta, report = build_rig(a.psd, a.mesh, parts_dir, a.prefix, root,
                                                  pivot_overrides=cfg_pivots)
    out = a.out or (os.path.splitext(a.psd)[0] + "_rig_draft.json")
    json.dump(skel, open(out, "w"), ensure_ascii=False, indent=1)
    if a.emit_config:
        emit_config_template(report, a.emit_config)
        print(f"寫出可編輯 rig-config 範本 → {a.emit_config}")

    ev = evaluate_skeleton(skel)   # 驗證 rig 仍是合法骨架樹
    print(json.dumps({"rig": report, "skeleton_valid": ev["overall_pass"],
                      "skeleton_summary": ev["summary"]}, ensure_ascii=False, indent=2))
    print(f"\n寫出 {out}")
    raise SystemExit(0 if ev["overall_pass"] else 1)


if __name__ == "__main__":
    main()
