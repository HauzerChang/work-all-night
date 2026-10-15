#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**確定性 deform-aware mesh 生成 + 變形自交閘**入口
(MERGE_PLAN Phase C1)。

== 這支解決什麼(C1 相對 B 階段的增量)==
  B 階段(make_beat / pivot_axis / sequence)讓件**動起來**(beat / 繞關節 / 序列),但件本身仍是
  剛性 region。要讓件能**變形**(窗簾彎、陰影拉伸、衣物飄),就需要 **mesh**。v1.3.0 的 validator 只能
  *檢查* 既有 mesh,**不能生成**。本模組把 repo 的 S3 生成器(`generate_mesh_v2` 的 strip 拓樸)+
  變形自交評估(`deform_eval` 的真實位移場轉移)抽成**一條 skill 層級流程**:
      一張件 PNG / atlas region → 生成 deformable mesh(strip/delaunay/boundary 自動選型)
                                → 用**真實位移場**轉移驗「拉扯下會不會撕裂」(si / flip / degen)。

== 為什麼是 strip(C1 的核心發現,見 knowledge/s3-real-asset-finding.md)==
  Canny 散點 Delaunay 靜態 IoU 高,但**大單向拉伸下自交**。藝術家對窗簾用「直條(vertical strip)」拓樸:
  每列取 alpha 左右邊界放點、順著拉伸軸 → 變形時各帶平滑滑動、**耐變形**。本模組預設 strip
  (高瘦 row-convex 件),對軟邊 blob(羽化帶高,如光暈)退 boundary-dense,其餘退 Delaunay。
  **實測**:main_draw 真實 deform 下,strip 對 4 mesh 全 si=0;naive Delaunay 在 curtain_right(si=19)、
  shadow(si=64)**撕裂** → strip 拓樸選型正是「真實 deform si=0」可達成的原因。

== G 護欄(見 MERGE_PLAN §1)==
  - mesh 不是動畫 timeline,**不涉及 G1 末鍵 curve**(deform timeline 由動畫層負責,非本模組)。
  - **G3 不覆蓋美術原檔**:本流程只**產出 mesh dict**(attachment 片段),由呼叫端決定寫進哪個新 skin /
    新 attachment,不碰既有檔。
  - **Spine 3.8 格式**(CLAUDE.md 雷點 #6):unweighted mesh `len(vertices)==len(uvs)`(頂點數×2);
    hull 頂點排在 vertices **最前**;triangles 為攤平 int 索引。`mesh_schema_errors()` 機械化把關。

== 過渡期相依(C1 → E1)==
  同 make_beat:透過其 `_wire_repo_tools()` 把 repo `tools/mesh_gen` 掛上 sys.path
  (`generate_mesh_v2` / `deform_eval` / `atlas_crop`)。E1 self-contained bundle 後移除此相依。

用法(程式化):
  from gen_lib.mesh import generate_mesh, mesh_from_region, real_deform_field_for, deform_si_check
  mesh = generate_mesh("curtain_left.png")                      # 自動選型(此件 → strip)
  errs = mesh_schema_errors(mesh)                               # [] = Spine 3.8 schema 合法
  # 用真實位移場驗「變形下會不會撕裂」:
  mesh, _ = mesh_from_region("main_draw.json","main_draw.atlas","main_draw.png","image/curtain_left")
  uvs_src, field, frame = real_deform_field_for("main_draw.json","image/curtain_left","image/curtain_left")
  res = deform_si_check(mesh, uvs_src, field)                   # {self_intersections, ..., clean}

CLI:
  python3 mesh.py <image.png> [--mode auto|strip|delaunay] [--out mesh.json]
  python3 mesh.py --self-test            # 對 main_draw 4 mesh 跑生成 + 真實 deform 閘
"""
from __future__ import annotations
import argparse
import json
import os
import sys

import numpy as np

# 取用 make_beat 的過渡期路徑 shim(package 或 path-added 兩種 import 皆可)。
try:
    from . import make_beat as _mb
except ImportError:  # 當 gen_lib 目錄被直接加進 sys.path 時
    import make_beat as _mb


def _wire():
    """把 repo tools/mesh_gen 掛上 sys.path,回傳 (generate_mesh_v2, deform_eval, atlas_crop) 模組。"""
    _mb._wire_repo_tools()          # 把 tools/analyzer、tools/mesh_gen、assets 掛上 sys.path
    import generate_mesh_v2 as gmv2   # noqa: E402  tools/mesh_gen(strip 生成器)
    import deform_eval as de          # noqa: E402  真實位移場轉移 + 幾何閘
    import atlas_crop as ac           # noqa: E402  atlas region → 緊湊 png
    return gmv2, de, ac


# main_draw 的 4 個可變形 mesh(slot, attachment-name)。shadow2 的 slot 與 shadow 共用同一張
# region **且** 共用同一個 attachment 名(image/shadow);其餘 slot==attachment 名。
CURTAIN_MESHES = (
    ("image/curtain_left", "image/curtain_left"),
    ("image/curtain_right", "image/curtain_right"),
    ("image/shadow", "image/shadow"),
    ("image/shadow2", "image/shadow"),
)
_SHARED_REGION = {"image/shadow2": "image/shadow"}   # shadow2 無獨立 region,共用 shadow


# --------------------------------------------------------------------- 生成
def generate_mesh(image_path, rows=10, cols=3, mode="auto"):
    """一張件 PNG(RGBA,alpha 為前景遮罩)→ Spine 3.8 unweighted mesh dict。

    mode="auto"(預設):高瘦且 row-convex → strip;軟邊 blob(羽化帶 ≥0.20)→ boundary-dense;其餘 → Delaunay。
    mode="strip"/"delaunay" 強制。回傳 dict 含 vertices/uvs/triangles/hull/width/height/_mode。
    """
    gmv2, _, _ = _wire()
    return gmv2.generate(image_path, rows=rows, cols=cols, mode=mode)


def mesh_from_region(skeleton_path, atlas_path, png_path, region,
                     tmp_crop=None, rows=10, cols=3, mode="auto"):
    """便捷:從 atlas 切出 `region` 的緊湊貼圖 → 生成 mesh。回傳 (mesh, crop_png_path)。

    region 無獨立 atlas entry 時(如 image/shadow2)自動改用共用 region(見 _SHARED_REGION)。
    tmp_crop=None → 寫到 skeleton 同目錄的暫存 png。
    """
    import cv2
    import tempfile
    _, _, ac = _wire()
    src_region = _SHARED_REGION.get(region, region)
    sub = ac.extract(atlas_path, png_path, src_region)
    if tmp_crop is None:
        # 暫存切圖寫系統 temp(不污染 skeleton/assets 目錄,不進版控)。
        tmp_crop = os.path.join(tempfile.gettempdir(),
                                "_c1_region_%s.png" % region.replace("/", "_"))
    cv2.imwrite(tmp_crop, sub)
    return generate_mesh(tmp_crop, rows=rows, cols=cols, mode=mode), tmp_crop


def write_mesh(mesh, out_path):
    """把 mesh dict 寫成 json(供外部/除錯;正式使用一般是嵌進 skin attachment)。"""
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mesh, f, ensure_ascii=False)
    return out_path


# --------------------------------------------------------------------- schema 閘(Spine 3.8)
def mesh_schema_errors(mesh):
    """機械化檢查 mesh 是否為合法 Spine 3.8 unweighted mesh。回傳錯誤字串 list([] = 合法)。

    檢查(對應 CLAUDE.md 雷點 #6):
      · vertices / uvs 長度為偶數且相等(unweighted ⇔ len(vertices)==len(uvs)=頂點數×2)
      · 全為有限數(無 NaN/Inf)
      · hull 為 int 且 3 ≤ hull ≤ 頂點數(hull 頂點排在 vertices 最前)
      · triangles 長度為 3 的倍數;索引皆落在 [0, 頂點數);每三角三索引相異
      · 每個頂點至少被一個三角引用(無孤兒頂點)
    """
    errs = []
    v = mesh.get("vertices"); uv = mesh.get("uvs"); tris = mesh.get("triangles")
    hull = mesh.get("hull")
    if not isinstance(v, list) or not isinstance(uv, list) or not isinstance(tris, list):
        return ["vertices/uvs/triangles 必須為 list"]
    if len(v) % 2 or len(uv) % 2:
        errs.append("vertices/uvs 長度須為偶數 (x,y 成對)")
    if len(v) != len(uv):
        errs.append("unweighted mesh 須 len(vertices)==len(uvs)(此為 weighted 或損壞:{} != {})"
                    .format(len(v), len(uv)))
    nv = len(uv) // 2
    if nv < 3:
        errs.append("頂點數 {} < 3(無法構成三角)".format(nv))
    if not all(np.isfinite(x) for x in v + uv):
        errs.append("vertices/uvs 含非有限數 (NaN/Inf)")
    if not isinstance(hull, int) or not (3 <= hull <= nv):
        errs.append("hull 須為 int 且 3 ≤ hull ≤ 頂點數 (得 {!r}, nv={})".format(hull, nv))
    if len(tris) % 3:
        errs.append("triangles 長度 {} 非 3 的倍數".format(len(tris)))
    used = set()
    for k in range(0, len(tris) - 2, 3):
        a, b, c = tris[k], tris[k + 1], tris[k + 2]
        if not all(isinstance(i, int) and 0 <= i < nv for i in (a, b, c)):
            errs.append("三角索引越界: ({},{},{}) nv={}".format(a, b, c, nv)); break
        if len({a, b, c}) != 3:
            errs.append("退化三角(索引重複): ({},{},{})".format(a, b, c)); break
        used.update((a, b, c))
    if nv >= 3 and len(used) < nv:
        errs.append("孤兒頂點 {} 個未被任何三角引用".format(nv - len(used)))
    return errs


# --------------------------------------------------------------------- 真實位移場 + 變形自交閘
def real_deform_field_for(skeleton, slot, name):
    """取某 mesh 在所有動畫中『總位移最大幀』的逐頂點真實位移場(以 UV 為座標,可轉移到任一拓樸)。

    skeleton : skeleton dict 或 .json 路徑。回傳 (uvs_src Nx2, field Nx2, frame_name)。
    """
    _, de, _ = _wire()
    if isinstance(skeleton, str):
        skeleton = json.load(open(skeleton, encoding="utf-8"))
    return de.real_deform_field(skeleton, slot, name)


def deform_si_check(mesh, uvs_src, field):
    """把真實位移場(uvs_src 座標、y-up)內插到 mesh 頂點並套用,檢查幾何拓樸。

    回傳 dict:{self_intersections, triangle_flips, degenerate, area_ratio, bbox, clean}。
    clean=True ⟺ 0 自交 ∧ 0 翻面 ∧ 0 退化 → 「這張 mesh 在此變形下不撕裂」(C1 的 si=0 閘)。
    """
    _, de, _ = _wire()
    return de.transfer_deform_check(mesh, uvs_src, field)


# --------------------------------------------------------------------- CLI / 自檢
def _self_test(main_draw_dir):
    sk = os.path.join(main_draw_dir, "main_draw.json")
    at = os.path.join(main_draw_dir, "main_draw.atlas")
    pg = os.path.join(main_draw_dir, "main_draw.png")
    ok = True
    for slot, name in CURTAIN_MESHES:
        mesh, _ = mesh_from_region(sk, at, pg, slot)
        errs = mesh_schema_errors(mesh)
        uvs_src, field, frame = real_deform_field_for(sk, slot, name)
        res = deform_si_check(mesh, uvs_src, field)
        good = (not errs) and res["clean"]
        ok = ok and good
        print("[{}] {:22} mode={:18} verts={:3} schema_errs={} | deform@{} si={} flip={} clean={}".format(
            "OK " if good else "FAIL", slot, mesh.get("_mode"), len(mesh["uvs"]) // 2,
            len(errs), frame, res["self_intersections"], res["triangle_flips"], res["clean"]))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", help="件 PNG(RGBA);省略時配 --self-test")
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--self-test", action="store_true",
                    help="對 main_draw 4 mesh 跑生成 + 真實 deform 閘")
    ap.add_argument("--main-draw-dir", default=None, help="main_draw.* 所在目錄(預設推 repo assets)")
    a = ap.parse_args()
    if a.self_test:
        d = a.main_draw_dir or os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "..", "..", "assets"))
        sys.exit(0 if _self_test(d) else 1)
    if not a.image:
        ap.error("需要 image 位置引數,或用 --self-test")
    mesh = generate_mesh(a.image, rows=a.rows, cols=a.cols, mode=a.mode)
    errs = mesh_schema_errors(mesh)
    out = a.out or (a.image.rsplit(".", 1)[0] + "_mesh.json")
    write_mesh(mesh, out)
    print("[{}] {}: mode={} verts={} hull={} tris={} schema_errs={}".format(
        "OK" if not errs else "SCHEMA-FAIL", out, mesh.get("_mode"),
        len(mesh["uvs"]) // 2, mesh["hull"], len(mesh["triangles"]) // 3, errs))
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()
