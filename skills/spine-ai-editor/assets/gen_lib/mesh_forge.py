# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**mesh 生成 + 變形自交閘**入口(MERGE_PLAN Phase C1)。

== 這支解決什麼(為何是「mesh/rig 併接」的第一塊)==
  v1.3.0 只**檢查**既有 mesh(viewer A/B、拓樸可視化),**不生成**、也沒有「會不會在動畫拉扯下撕裂」
  的機讀閘。repo 半年累積了兩件 v1.3.0 缺的東西,本模組把它們抽成一條 skill 層級流程:
    1. **確定性 strip mesh 生成**(`generate_mesh_v2`):對高瘦、row-convex(每掃描線單一 alpha 區段)
       的件(窗簾 / 肢體),用「掃描線邊界格點」三角化成規則梯狀——邊界點為主、順拉伸軸 → 耐變形;
       頂點數=rows×cols 可控、接近藝術家精簡度;hull 排 vertices 最前(Spine 格式)。
       非 strip 件(blob,如機器人身體 / 光暈)auto 模式自動回退 Delaunay(v1),**不硬塞 strip**。
    2. **真實位移場轉移閘**(`deform_eval.transfer_deform_check`):把真實資產(main_draw 窗簾)在所有
       動畫中「總位移最大幀」的逐頂點位移,以 **UV 座標**內插轉移到**任一拓樸**的生成 mesh,施加後檢查
       self-intersection / triangle-flip / degenerate → **si=0 ⇔ 生成的網格在真實 deform 幅度下不撕裂**。

  ⚠️ 用**真實位移場轉移**,不要用未校準的合成 `stress_field`(教訓 2026-06-24:合成 mag=315 面積比 2.0
  >> 真實 1.13,造成假性失敗;見 `deform_eval.py` docstring)。

== G 護欄(見 MERGE_PLAN §1)==
  - **G5 self-contained(過渡期)**:同 make_beat,透過 `_mb._wire_repo_tools()` 掛 repo `tools/mesh_gen`
    (`generate_mesh_v2` / `deform_eval` / `evaluate_mesh` / `atlas_crop`)。E1 會 bundle 進 assets 移除相依。
  - 生成的是 **unweighted mesh**(`vertices.length == uvs.length`);weighted mesh + rig 推斷是 **C2**。
  - 本模組只**生成素材 + 把關品質**,不碰動畫 timeline(那是 B 階段 make_beat/sequence 的事)。

用法(程式化):
  from gen_lib.mesh_forge import generate_strip_mesh, load_real_deform_field, deform_safety_check
  mesh = generate_strip_mesh("curtain_crop.png")                 # strip(或 blob 回退 delaunay)
  uvs, field, frame = load_real_deform_field()                   # 真實窗簾位移場(可轉移到任一拓樸)
  gate = deform_safety_check(mesh, uvs, field)                   # {self_intersections, clean, ...}
  assert gate["clean"]                                           # si=0 / flips=0 / degen=0

用法(CLI):
  python3 mesh_forge.py --image curtain_crop.png                 # 生成 + 對真實窗簾場跑閘
  python3 mesh_forge.py --self-test                              # 不寫檔,跑內建自檢(真實 main_draw 窗簾)
"""
from __future__ import annotations
import argparse
import json
import os
import sys

# 取用 make_beat 的過渡期路徑 shim(package 或 path-added 兩種 import 皆可)。
try:
    from . import make_beat as _mb
except ImportError:  # 當 gen_lib 目錄被直接加進 sys.path 時
    import make_beat as _mb


# --------------------------------------------------------------------- 預設真值資產
# repo 內唯一帶「真實 deform timeline」的生產資產 = main_draw 的 4 個 mesh(窗簾 2 + 陰影 2)。
# 窗簾在 9 支動畫全有 deform,是變形最劇烈、最適合當「生成 mesh 耐不耐拉」真值的件。
def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


DEFAULT_SKELETON = os.path.join(_repo_root(), "assets", "main_draw.json")
DEFAULT_ATLAS = os.path.join(_repo_root(), "assets", "main_draw.atlas")
DEFAULT_PNG = os.path.join(_repo_root(), "assets", "main_draw.png")
DEFAULT_CURTAIN = ("image/curtain_left", "image/curtain_left")


def _wire():
    """掛 repo tools/mesh_gen,回傳模組 (generate_mesh_v2, deform_eval, evaluate_mesh, atlas_crop)。"""
    _mb._wire_repo_tools()                    # 把 tools/analyzer、tools/mesh_gen、assets 掛上 sys.path
    import generate_mesh_v2 as gmv2           # noqa: E402
    import deform_eval as de                  # noqa: E402
    import evaluate_mesh as em                # noqa: E402
    import atlas_crop as ac                   # noqa: E402
    return gmv2, de, em, ac


# --------------------------------------------------------------------- 生成(strip / auto)
def generate_strip_mesh(image_path, rows=10, cols=3, mode="auto"):
    """對一張件 PNG 生成 Spine mesh(dict)。

    mode="auto":高瘦(aspect≥1.2)且 row-convex → strip;否則回退 Delaunay(v1)(軟邊 blob 走密邊界)。
    mode="strip" 強制 strip;mode="delaunay" 強制 v1。回傳 dict 含 `_mode` 標記實際用哪條。
    輸出為 **unweighted**(vertices.length == uvs.length == 頂點數×2),hull 頂點排最前。
    """
    gmv2, _, _, _ = _wire()
    return gmv2.generate(image_path, rows=rows, cols=cols, mode=mode)


# --------------------------------------------------------------------- 真實位移場
def load_real_deform_field(skeleton_path=DEFAULT_SKELETON, slot=None, name=None):
    """載入真實資產某 mesh 在所有動畫中「總位移最大幀」的逐頂點位移(local, y-up),以 UV 為座標。
    回傳 (uvs_src Nx2, field Nx2, best_anim_name)。位移場以 UV 表達 → **可轉移到任一拓樸的 mesh**。
    預設取 main_draw 的 curtain_left(變形最劇烈的生產件)。"""
    _, de, _, _ = _wire()
    slot = slot or DEFAULT_CURTAIN[0]
    name = name or DEFAULT_CURTAIN[1]
    sk = json.load(open(skeleton_path, encoding="utf-8"))
    return de.real_deform_field(sk, slot, name)


# --------------------------------------------------------------------- 變形自交閘
def deform_safety_check(mesh, uvs_src, field):
    """把真實位移場 (uvs_src, field) 內插到 mesh 頂點並套用,檢查幾何品質。
    回傳 {self_intersections, triangle_flips, degenerate, area_ratio, bbox, clean}。
    clean == (si==0 and flips==0 and degenerate==0) ⇔ 生成的網格在真實 deform 幅度下不撕裂/翻面。"""
    _, de, _, _ = _wire()
    return de.transfer_deform_check(mesh, uvs_src, field)


# --------------------------------------------------------------------- 覆蓋率(非平凡性)
def coverage_iou(mesh, mask):
    """生成 mesh 的靜態輪廓覆蓋率(vs alpha mask)。用來證「乾淨 ≠ 空殼」:
    一個頂點全擠在一起的退化 mesh 也會 si=0,但 IoU≈0。配合 deform 閘才是完整 AC。"""
    _, _, em, _ = _wire()
    return float(em.evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"])


def crop_atlas_region(atlas_path, png_path, name, out_png):
    """從真實 atlas+png 切出某 region 的緊湊 RGBA PNG(用於真實件生成);回傳 alpha mask。"""
    gmv2, _, em, ac = _wire()
    import cv2
    sub = ac.extract(atlas_path, png_path, name)
    cv2.imwrite(out_png, sub)
    return em.load_mask(out_png)


# --------------------------------------------------------------------- 端到端便利函式
def forge_and_gate(image_path, uvs_src=None, field=None, rows=10, cols=3, mode="auto"):
    """生成 mesh → 跑真實 deform 閘,一步到位。uvs_src/field 省略時用預設真實窗簾場。
    回傳 {mesh, mode, nv, hull, tris, gate}。"""
    mesh = generate_strip_mesh(image_path, rows=rows, cols=cols, mode=mode)
    if uvs_src is None or field is None:
        uvs_src, field, _ = load_real_deform_field()
    gate = deform_safety_check(mesh, uvs_src, field)
    return {"mesh": mesh, "mode": mesh.get("_mode"),
            "nv": len(mesh["uvs"]) // 2, "hull": mesh["hull"],
            "tris": len(mesh["triangles"]) // 3, "gate": gate}


# --------------------------------------------------------------------- 自檢
def _self_test(tmp_dir=None):
    """對真實 main_draw curtain_left 生成 strip mesh,跑真實 deform 閘,印結果。回傳 overall_clean。"""
    tmp_dir = tmp_dir or os.path.join(_repo_root(), "_c1_selftest_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    crop = os.path.join(tmp_dir, "_curtain_left.png")
    mask = crop_atlas_region(DEFAULT_ATLAS, DEFAULT_PNG, DEFAULT_CURTAIN[1], crop)
    uvs, field, frame = load_real_deform_field()
    out = forge_and_gate(crop, uvs, field)
    iou = coverage_iou(out["mesh"], mask)
    g = out["gate"]
    print(json.dumps({
        "part": DEFAULT_CURTAIN[1], "mode": out["mode"], "nv": out["nv"],
        "hull": out["hull"], "tris": out["tris"], "coverage_iou": round(iou, 4),
        "deform_frame": frame, "area_ratio": g["area_ratio"],
        "self_intersections": g["self_intersections"], "triangle_flips": g["triangle_flips"],
        "degenerate": g["degenerate"], "clean": g["clean"],
    }, ensure_ascii=False, indent=2))
    return bool(g["clean"] and iou > 0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="件 PNG;生成 mesh 並對真實窗簾 deform 場跑閘")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    ap.add_argument("--out", default=None, help="把生成 mesh 寫檔")
    ap.add_argument("--self-test", action="store_true", help="跑內建自檢(真實 main_draw 窗簾)")
    a = ap.parse_args()
    if a.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)
    if not a.image:
        ap.error("需 --image 或 --self-test")
    out = forge_and_gate(a.image, rows=a.rows, cols=a.cols, mode=a.mode)
    if a.out:
        json.dump(out["mesh"], open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(json.dumps({"mode": out["mode"], "nv": out["nv"], "hull": out["hull"],
                      "tris": out["tris"], "gate": out["gate"]}, ensure_ascii=False, indent=2))
    sys.exit(0 if out["gate"]["clean"] else 1)


if __name__ == "__main__":
    main()
