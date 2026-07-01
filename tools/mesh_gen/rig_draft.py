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


def build_rig(psd_path, mesh_layers, out_dir, prefix, root_layer=None, target_iou=0.97):
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

    # 重寫 bones 成父子鏈;bone local = 世界位置 - parent 世界位置(世界位置不變 → 版面保真)
    bones = [{"name": "root"}]
    rig_report = []
    for name in [n for n in masks]:                # 保持件順序
        slot = f"{stem}/{name}"
        bone = f"{slot}_bone"
        p = parent[name]
        cw = center_world(name)
        if p is None:                              # rig root 件 → 掛骨架 root
            pw = (0.0, 0.0); parent_bone = "root"; joint = None
        else:
            pw = center_world(p); parent_bone = f"{stem}/{p}_bone"
            jc = overlap_centroid(masks[name], masks[p])
            joint = None if jc is None else [round(jc[0] - W / 2.0, 2), round(H / 2.0 - jc[1], 2)]
        bones.append({"name": bone, "parent": parent_bone,
                      "x": round(cw[0] - pw[0], 2), "y": round(cw[1] - pw[1], 2),
                      # pivot 草案:重疊質心(世界座標);精確值待人微調
                      "_joint_pivot_draft": joint, "_needs_human_pivot": p is not None})
        rig_report.append({"part": name, "parent": p, "joint_pivot_draft": joint,
                           "isolated": name in isolated})

    skel["bones"] = bones   # slots/skins 不動(仍指向同名 bone)
    report = {"root": root, "root_auto_chosen": root_layer is None,
              "overlap_degree": degree, "hierarchy": rig_report, "isolated": isolated,
              "needs_human": ["確認 root 件選擇", "每關節 pivot 微調", "mesh 權重綁定(目前 unweighted)"]}
    return skel, manifest, part_meta, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--parts-dir", default=None)
    ap.add_argument("--mesh", nargs="*", default=DEFAULT_MESH)
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--root", default=None, help="指定 root 件(預設自動:重疊度最高)")
    a = ap.parse_args()
    parts_dir = a.parts_dir or tempfile.mkdtemp(prefix="rig_parts_")
    skel, manifest, part_meta, report = build_rig(a.psd, a.mesh, parts_dir, a.prefix, a.root)
    out = a.out or (os.path.splitext(a.psd)[0] + "_rig_draft.json")
    json.dump(skel, open(out, "w"), ensure_ascii=False, indent=1)

    ev = evaluate_skeleton(skel)   # 驗證 rig 草案仍是合法骨架樹
    print(json.dumps({"rig": report, "skeleton_valid": ev["overall_pass"],
                      "skeleton_summary": ev["summary"]}, ensure_ascii=False, indent=2))
    print(f"\n寫出 {out}")
    raise SystemExit(0 if ev["overall_pass"] else 1)


if __name__ == "__main__":
    main()
