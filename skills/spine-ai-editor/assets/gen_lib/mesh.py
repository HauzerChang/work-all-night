#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**確定性 mesh 生成 + 變形自交閘**入口(MERGE_PLAN Phase C1)。

這支把 repo 半年累積的 **S3 mesh 生成引擎**(`generate_mesh_v2` strip/delaunay/boundary-dense)
與 **變形自交評估器**(`deform_eval` 真實位移場轉移)包成**一條 skill 層級的流程**:
給一個「拆件(part)影像」或「atlas region」→ 產出一份 **Spine 3.8 合法 mesh attachment**,
並用**真實 deform 位移場**驗證該拓樸「在動畫拉扯下不會自交/翻面/退化」。

== 為什麼存在(C1 的增量;結構軸的 mesh 分支)==
  v1.3.0 的 skill **只能檢查既有 mesh**(拓樸合法、頂點經濟),**不能生成 mesh**。
  B3 的 `pivot_axis.py`(繞關節 pivot 變換)是結構軸的「不動骨架、動 keyframe」分支;
  C1 的 `mesh.py` 是結構軸的「**生成可變形網格**」分支——當「結構性無法做到」是因為
  件沒有 mesh(只能整塊剛體位移、無法彎折/飄動)時,本入口從件影像**生成**一張耐變形的 mesh。
  併入後 2.0 就同時具備「生成 mesh」(本檔)與「把關 mesh 品質」(deform si 閘)兩面。

== 核心能力(對外契約)==
  1. `generate_part_mesh(image_path, ...)`  件影像 → strip/delaunay/boundary-dense mesh(auto 選模)。
  2. `deform_si_gate(mesh, skeleton, slot, name)`  把**真實動畫 deform 位移場**轉移到生成 mesh,
     量化 self-intersections / triangle_flips / degenerate / area_ratio → clean pass/fail。
     (CLAUDE.md 雷點 #3/#4:deform 直接逐頂點加偏移,attachment-local 空間,足判拓樸正確性。)
  3. `generate_and_gate_part(...)`  件 → 生成 → 靜態 IoU + 真實 deform 自交閘,一條龍自驗。

== strip 模式(窗簾類)vs auto(其他)==
  高瘦、row-convex(每掃描線單一 alpha 區段)的件 → **strip**(掃描線格點,邊界點順拉伸軸,耐變形);
  其餘 → 回退 delaunay-v1 / boundary-dense-v1(軟邊 blob)。詳見 repo `generate_mesh_v2` docstring。
  AC「對 robot/curtain 件生成 strip mesh」= 窗簾走 strip、機器人件走 auto(非高瘦,delaunay/boundary),
  兩者皆產**合法、拓樸乾淨、IoU 達藝術家基準**的 mesh;窗簾另過「真實 deform si=0」閘。

== 變形自交閘的真相來源 ==
  ⚠️ **不可用** `deform_eval.stress_field`(未校準合成場,mag 過大造假性失敗,見該函式註解)。
  本閘一律用 `real_deform_field()`(真實動畫逐頂點位移,取總位移最大幀)+ `transfer_deform_check()`
  (以 UV 為座標把位移場 griddata 內插到任一拓樸)→ 真值校準、可轉移。

== 過渡期相依(C1 → E1)==
  本檔目前**import repo 的 `tools/mesh_gen`**(透過 `_wire_repo_tools()` 路徑 shim),與 B2/B3/B4 一致。
  **Phase E1** 會把生成碼 bundle 進 `assets/`(self-contained,滿足 G5),屆時移除此 shim。
  在 repo 環境下(排程)本檔即可跑;純使用者端(無 repo tools)須等 E1 bundle 後才 standalone。
  依賴:numpy / opencv(cv2)/ scipy(griddata)—— 皆在 SessionStart hook 的 requirements.txt。

用法(CLI):
  python3 mesh.py --image region.png --out /tmp/mesh.json          # 件影像 → mesh
  python3 mesh.py --self-test                                      # 對 repo 真實 curtain/robot 件自檢

程式化:
  from gen_lib.mesh import generate_part_mesh, deform_si_gate, generate_and_gate_part
  mesh = generate_part_mesh("region.png")                          # dict(Spine mesh attachment)
  gate = deform_si_gate(mesh, "assets/main_draw.json",
                        "image/curtain_left", "image/curtain_left") # {clean, self_intersections, ...}
"""
from __future__ import annotations
import argparse
import json
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """把生成/評估碼掛上 sys.path,回傳 (generate_mesh_v2, deform_eval, atlas_crop)。

    **E1(self-contained)**:優先用 `_bundled/`(見 make_beat._wire_repo_tools 說明);
    `_bundled/` 不存在才退回 repo `tools/`。bundled 置最前 → 優先。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    bundled = os.path.join(here, "_bundled")                       # E1 self-contained 生成碼
    # repo 根(fallback):assets/gen_lib → assets → spine-ai-editor → skills → repo
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "mesh_gen"),
              os.path.join(repo, "tools", "analyzer")):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    if os.path.isdir(bundled) and bundled not in sys.path:
        sys.path.insert(0, bundled)
    try:
        import generate_mesh_v2 as GM
        import deform_eval as DE
        import atlas_crop as AC
    except ImportError as e:
        raise ImportError(
            "gen_lib.mesh 需要生成/評估碼 generate_mesh_v2 / deform_eval / atlas_crop"
            "(隨 skill 的 assets/gen_lib/_bundled 打包)。找不到 _bundled/ 且不在 repo 環境時"
            "會發生此錯。原始錯誤:{}".format(e))
    return GM, DE, AC


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


# --------------------------------------------------------------------- demo 件(repo 真實資產)
# C1 自檢用的真實件:窗簾(main_draw,有真實 deform → 過 si 閘)+ 機器人件(Award,weighted 無 deform
# → 靜態 IoU + 拓樸)。路徑相對 repo 根,_self_test() 會解析成絕對路徑。
CURTAIN_DEMO_PARTS = [
    {"skeleton": "assets/main_draw.json", "atlas": "assets/main_draw.atlas",
     "png": "assets/main_draw.png", "slot": "image/curtain_left",  "name": "image/curtain_left"},
    {"skeleton": "assets/main_draw.json", "atlas": "assets/main_draw.atlas",
     "png": "assets/main_draw.png", "slot": "image/curtain_right", "name": "image/curtain_right"},
]
ROBOT_DEMO_PARTS = [
    {"skeleton": "assets/Award.json", "atlas": "assets/Award.atlas", "png": "assets/Award.png",
     "slot": "機器人拆件/光暈", "name": "機器人拆件/光暈"},
    {"skeleton": "assets/Award.json", "atlas": "assets/Award.atlas", "png": "assets/Award.png",
     "slot": "機器人拆件/左手", "name": "機器人拆件/左手"},
    {"skeleton": "assets/Award.json", "atlas": "assets/Award.atlas", "png": "assets/Award.png",
     "slot": "機器人拆件/身體", "name": "機器人拆件/身體"},
]


# --------------------------------------------------------------------- 1. mesh 生成
def generate_part_mesh(image_path, rows=10, cols=3, mode="auto"):
    """件影像(含 alpha 的 PNG)→ Spine 3.8 mesh attachment dict。

    mode="auto":高瘦+row-convex → strip(窗簾類);軟邊 blob → boundary-dense-v1;其餘 → delaunay-v1。
    回傳 dict 含:type/vertices/uvs/triangles/hull/width/height/_mode。
      - unweighted:len(vertices) == len(uvs)(頂點數×2);hull 頂點排最前(Spine 格式)。
    """
    GM, _, _ = _wire_repo_tools()
    mesh = GM.generate(image_path, rows=rows, cols=cols, mode=mode)
    if isinstance(mesh, tuple):          # 相容 v1 的 (mesh, meta) 回傳
        mesh = mesh[0]
    return mesh


def mesh_is_schema_valid(mesh):
    """Spine mesh attachment 的最小 schema 檢查(可機讀)。回傳 (ok, problems[])。"""
    probs = []
    if mesh.get("type") != "mesh":
        probs.append("type != mesh")
    v, u = mesh.get("vertices", []), mesh.get("uvs", [])
    nv = len(u) // 2
    if len(v) != len(u):
        probs.append("unweighted 期待 len(vertices)==len(uvs)(本件可能 weighted);len={}/{}".format(len(v), len(u)))
    if nv < 3:
        probs.append("頂點數 < 3")
    h = mesh.get("hull", 0)
    if not (0 < h <= nv):
        probs.append("hull={} 不在 (0, nv={}]".format(h, nv))
    tris = mesh.get("triangles", [])
    if len(tris) == 0 or len(tris) % 3 != 0:
        probs.append("triangles 長度非 3 的倍數或空")
    if tris and (min(tris) < 0 or max(tris) >= nv):
        probs.append("triangle 索引越界 [0,{})".format(nv))
    return (len(probs) == 0, probs)


# --------------------------------------------------------------------- 2. 變形自交閘(真實位移場)
def _load_skeleton(skeleton):
    if isinstance(skeleton, str):
        return json.load(open(skeleton, encoding="utf-8"))
    return skeleton


def has_real_deform(skeleton, slot, name):
    """該 skeleton 是否對此 slot/attachment 有 deform timeline(→ 可做真實 si 閘)。"""
    _, DE, _ = _wire_repo_tools()
    sk = _load_skeleton(skeleton)
    for anim in sk.get("animations", {}):
        if DE.deform_frames(sk, anim, slot, name):
            return True
    return False


def _static_topology_check(mesh):
    """生成 mesh 在 setup pose 的幾何合法性(self-intersections / degenerate)。
    用於**無 deform timeline** 的件(如 Award 機器人件 weighted,靠骨骼變形、無逐頂點 deform):
    真實位移場轉移不適用,改驗生成拓樸本身乾淨。生成 mesh 為 unweighted → vertices 可直接 reshape。"""
    import numpy as np
    _, DE, _ = _wire_repo_tools()
    v = np.array(mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [DE.signed_area(v, t) > 0 for t in tris]
    area = sum(abs(DE.signed_area(v, t)) for t in tris)
    return DE.eval_pose(v, tris, signs, area)


def deform_si_gate(mesh, skeleton, slot, name):
    """把**真實動畫 deform 位移場**(總位移最大幀)轉移到生成 mesh,量化幾何品質。

    回傳 dict:
      has_real_deform  : 此 slot/name 在 skeleton 是否有 deform timeline。
                         有 → 用真實位移場轉移(= AC「真實 deform si=0」);
                         無 → 退回生成 mesh 的 setup 靜態拓樸檢查(真實場不適用,如 weighted 件)。
      frame            : 取用的最大位移幀(無 deform → None)。
      self_intersections / triangle_flips / degenerate / area_ratio
      clean            : si==0 且 flips==0 且 degenerate==0。

    ⚠️ 用 real_deform_field + transfer_deform_check(真值校準),**不用** stress_field。
    """
    _, DE, _ = _wire_repo_tools()
    sk = _load_skeleton(skeleton)
    if not has_real_deform(sk, slot, name):
        res = _static_topology_check(mesh)
        return {
            "has_real_deform": False, "frame": None,
            "self_intersections": res["self_intersections"],
            "triangle_flips": res["triangle_flips"],
            "degenerate": res["degenerate"],
            "area_ratio": res["area_ratio"],
            "clean": bool(res["clean"]),
        }
    uvs_src, field, frame = DE.real_deform_field(sk, slot, name)
    res = DE.transfer_deform_check(mesh, uvs_src, field)
    return {
        "has_real_deform": True,
        "frame": frame,
        "self_intersections": res["self_intersections"],
        "triangle_flips": res["triangle_flips"],
        "degenerate": res["degenerate"],
        "area_ratio": res["area_ratio"],
        "clean": bool(res["clean"]),
    }


# --------------------------------------------------------------------- 3. 靜態覆蓋率 + 一條龍
def _crop_region(atlas_path, png_path, name, tmp_dir=None):
    """用 atlas_crop 取 region(derotate+縮放)→ 寫暫存 PNG,回傳 (mask uint8 HxW, crop_path)。"""
    import tempfile
    import numpy as np
    import cv2
    _, _, AC = _wire_repo_tools()
    sub = AC.extract(atlas_path, png_path, name)
    tmp_dir = tmp_dir or tempfile.mkdtemp(prefix="c1mesh_")
    crop_path = os.path.join(tmp_dir, "_region.png")
    cv2.imwrite(crop_path, sub)
    alpha = sub[:, :, 3] if (sub.ndim == 3 and sub.shape[2] == 4) else \
        (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    mask = (alpha > 8).astype(np.uint8)
    return mask, crop_path


def static_iou(mesh, mask):
    """生成 mesh 在 region 框的覆蓋率 IoU(uvs 為 region-local [0,1],vflip=False)。"""
    import numpy as np
    import cv2
    uvs = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / max(union, 1))


def artist_baseline_iou(skeleton, slot, name, mask):
    """同一 region 框下,美術 mesh 的覆蓋率(作為 IoU 達標基準)。"""
    import numpy as np
    import cv2
    sk = _load_skeleton(skeleton)
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / max(union, 1))


def generate_and_gate_part(skeleton, atlas_path, png_path, slot, name,
                           rows=10, cols=3, mode="auto", tmp_dir=None, iou_margin=0.0):
    """件 → 生成 mesh → 靜態 IoU(vs 藝術家基準)+ 真實 deform 自交閘,一條龍自驗。

    回傳 dict:mesh(摘要)/ schema / iou / deform_gate / overall_pass。
    overall_pass = schema 合法 AND iou>=baseline-margin AND (無 deform 時只看前兩者,否則加 deform clean)。
    """
    sk = _load_skeleton(skeleton)
    mask, crop_path = _crop_region(atlas_path, png_path, name, tmp_dir)
    mesh = generate_part_mesh(crop_path, rows=rows, cols=cols, mode=mode)
    schema_ok, schema_probs = mesh_is_schema_valid(mesh)
    iou = static_iou(mesh, mask)
    base = artist_baseline_iou(sk, slot, name, mask)
    gate = deform_si_gate(mesh, sk, slot, name)
    iou_ok = iou >= base - iou_margin
    deform_ok = (not gate["has_real_deform"]) or gate["clean"]
    nv = len(mesh["uvs"]) // 2
    return {
        "slot": slot,
        "mesh": {"mode": mesh.get("_mode"), "vertices": nv, "hull": mesh["hull"],
                 "triangles": len(mesh["triangles"]) // 3},
        "schema": {"pass": schema_ok, "problems": schema_probs},
        "iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                "margin": iou_margin, "pass": iou_ok},
        "deform_gate": gate,
        "overall_pass": schema_ok and iou_ok and deform_ok,
    }


# --------------------------------------------------------------------- 自檢
def _self_test():
    root = _repo_root()

    def _abs(p):
        return {k: (os.path.join(root, v) if k in ("skeleton", "atlas", "png") else v)
                for k, v in p.items()}

    out = {"curtain": [], "robot": []}
    for grp, parts in (("curtain", CURTAIN_DEMO_PARTS), ("robot", ROBOT_DEMO_PARTS)):
        for p in parts:
            ap = _abs(p)
            rep = generate_and_gate_part(ap["skeleton"], ap["atlas"], ap["png"],
                                         ap["slot"], ap["name"], iou_margin=0.03)
            out[grp].append(rep)
    allpass = all(r["overall_pass"] for g in out.values() for r in g)
    return {"overall_pass": allpass, "parts": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="件影像(含 alpha)→ 生成 mesh")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    ap.add_argument("--self-test", action="store_true", help="對 repo 真實 curtain/robot 件自檢")
    a = ap.parse_args()
    if a.self_test:
        rep = _self_test()
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        sys.exit(0 if rep["overall_pass"] else 1)
    if not a.image:
        ap.error("需 --image 或 --self-test")
    mesh = generate_part_mesh(a.image, a.rows, a.cols, a.mode)
    ok, probs = mesh_is_schema_valid(mesh)
    out = a.out or (a.image.rsplit(".", 1)[0] + "_mesh.json")
    json.dump(mesh, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("[{}] {}: 頂點 {} (hull {}), 三角 {}, schema_ok={}".format(
        mesh.get("_mode"), out, len(mesh["uvs"]) // 2, mesh["hull"],
        len(mesh["triangles"]) // 3, ok))
    if not ok:
        print("  schema problems:", probs)


if __name__ == "__main__":
    main()
