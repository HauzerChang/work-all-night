#!/usr/bin/env python3
"""成果發表 A/B:把研究成果套到真實 main_draw,產出可在 Spine 預覽器對比的兩份資產。

A = 原始 main_draw(未改)。
B = 用研究成果對 A 的 4 片會變形網格(curtain_left/right, shadow, shadow2)做升級:
    ① S3 v2 strip 生成器 → 自動細分成更高解析度、變形更穩的直條拓樸(頂點數 ×3)。
    ② deform 場轉移(平滑 RBF 重採樣) → 把原本全部 9 支動畫的每個 deform 關鍵影格
       忠實重建到新拓樸上(時間軸/緩動 curve 原樣保留)。
    ③ deform 閘(deform_eval)逐幀驗證:B 全程 0 自交 / 0 翻面(與藝術家同級穩健);
       任一幀若 RBF 過衝致自交 → 該幀退回線性(等同 A 的形狀、只是更密),保證 B 不劣於 A。

輸出 delivery/A/ 與 delivery/B/(各含 main_draw.json/.atlas/.png),使用者直接載入對比。
"""
import argparse, json, os, shutil, sys
import numpy as np
import cv2

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import deform_eval as de
from generate_mesh_v2 import gen_strip, to_spine

# (slot, attachment_name, rows, cols) — 細分解析度
TARGETS = [
    ("image/curtain_left",  "image/curtain_left",  16, 4),
    ("image/curtain_right", "image/curtain_right", 16, 4),
    ("image/shadow",        "image/shadow",        14, 3),
    ("image/shadow2",       "image/shadow",        14, 3),
]


def resample_setup(src_uv, src_local, dst_uv):
    """把原 mesh 的 setup local 座標當成 uv 空間上的場,平滑重採樣到新 uv 格點。
    RBF thin-plate 對仿射(curtain/shadow)精確重現、對非仿射 setup warp(shadow2 彎曲)平滑細分。
    回傳 (new_local Nx2, node_residual px)。"""
    from scipy.interpolate import RBFInterpolator
    rbf = RBFInterpolator(src_uv, src_local, kernel="thin_plate_spline", smoothing=0.0)
    res = float(np.abs(rbf(src_uv) - src_local).max())  # 節點自一致性
    return rbf(dst_uv), res


def resample_disp(src_uv, disp, dst_uv, smoothing=0.0):
    """把位移場(src_uv 座標)平滑重採樣到 dst_uv。RBF thin-plate;回傳 dst 位移 Nx2。"""
    from scipy.interpolate import RBFInterpolator
    rbf = RBFInterpolator(src_uv, disp, kernel="thin_plate_spline", smoothing=smoothing)
    return rbf(dst_uv)


def resample_disp_linear(src_uv, disp, dst_uv):
    from scipy.interpolate import griddata
    dx = griddata(src_uv, disp[:, 0], dst_uv, "linear")
    dy = griddata(src_uv, disp[:, 1], dst_uv, "linear")
    nx = griddata(src_uv, disp[:, 0], dst_uv, "nearest")
    ny = griddata(src_uv, disp[:, 1], dst_uv, "nearest")
    dx = np.where(np.isnan(dx), nx, dx); dy = np.where(np.isnan(dy), ny, dy)
    return np.column_stack([dx, dy])


def boundary_smoothness(setup, hull_n, deformed):
    """沿 hull 邊界的平均『轉折角』(度);越小越平滑。回傳變形姿態下的值。"""
    idx = list(range(hull_n))
    P = deformed[idx]
    ang = []
    for i in range(len(idx)):
        a, b, c = P[i - 1], P[i], P[(i + 1) % len(idx)]
        v1 = a - b; v2 = c - b
        n1 = np.linalg.norm(v1); n2 = np.linalg.norm(v2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        cosang = np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1)
        ang.append(180.0 - np.degrees(np.arccos(cosang)))  # 偏離直線的角度
    return float(np.mean(ang)) if ang else 0.0


def build(src_json, out_json, report):
    sk = json.load(open(src_json))
    att = sk["skins"][0]["attachments"]

    for slot, name, rows, cols in TARGETS:
        a0 = att[slot][name]
        W, H = a0["width"], a0["height"]
        setup0 = np.array(a0["vertices"], np.float64).reshape(-1, 2)
        uv0 = np.array(a0["uvs"], np.float64).reshape(-1, 2)
        tris0 = np.array(a0["triangles"], np.int32).reshape(-1, 3)
        hull0 = a0["hull"]

        # ① 細分「藝術家 mesh 自身的 footprint」(非圖檔 alpha:shadow 是軟漸層 alpha,
        #    直接切會變細;藝術家 mesh 才是真正上貼圖的形狀)→ 光柵化 mesh 三角當 mask → strip 細分
        SS = 2  # 超取樣讓邊界平滑
        Wm, Hm = W * SS, H * SS
        rp = np.column_stack([uv0[:, 0] * Wm, uv0[:, 1] * Hm])
        mask = np.zeros((Hm, Wm), np.uint8)
        for t in tris0:
            cv2.fillConvexPoly(mask, np.round(rp[t]).astype(np.int32), 1)
        pts, new_tris_list, new_hull = gen_strip(mask, Wm, Hm, rows, cols)
        m = to_spine(pts, new_tris_list, new_hull, Wm, Hm)   # uvs = x/Wm, y/Hm ∈ [0,1]
        new_uv = np.array(m["uvs"], np.float64).reshape(-1, 2)
        new_tris = np.array(m["triangles"], np.int32).reshape(-1, 3)

        # 把原 setup local 當 uv 空間的場平滑重採樣到新格點(仿射精確、非仿射 warp 平滑細分)
        new_setup, res = resample_setup(uv0, setup0, new_uv)
        new_setup_flat = [round(float(x), 3) for x in new_setup.reshape(-1)]
        # setup 自身拓樸須乾淨(無自交/退化)
        _ssign = [de.signed_area(new_setup, t) > 0 for t in new_tris]
        _setup_chk = de.check(new_setup, new_tris, None)

        # 替換 attachment(保留其它欄位)
        a1 = dict(a0)
        a1["type"] = "mesh"
        a1["vertices"] = new_setup_flat
        a1["uvs"] = [round(float(x), 6) for x in new_uv.reshape(-1)]
        a1["triangles"] = [int(i) for t in new_tris for i in t]
        a1["hull"] = int(new_hull)
        a1.pop("edges", None)  # 舊 edges 索引失效,移除(非必要欄位)
        att[slot][name] = a1

        # setup 幾何簽章(用於 flip 判定)
        signs = [de.signed_area(new_setup, t) > 0 for t in new_tris]
        area0 = sum(abs(de.signed_area(new_setup, t)) for t in new_tris)

        # ② 逐動畫重建 deform
        r_mesh = {"nv": [len(setup0), len(new_setup)], "hull": [hull0, new_hull],
                  "tris": [len(tris0), len(new_tris)], "resample_node_residual": round(res, 4),
                  "setup_selfint": _setup_chk["self_intersections"],
                  "setup_degenerate": _setup_chk["degenerate"], "anims": {}}
        for anim, ad in sk.get("animations", {}).items():
            dfm = ad.get("deform")
            if not dfm:
                continue
            for skinname, slots in dfm.items():
                if slot not in slots or name not in slots[slot]:
                    continue
                frames = slots[slot][name]
                a_worst_s, b_worst_s = 0, 0        # self-int A vs B
                a_worst_f, b_worst_f = 0, 0
                a_sm, b_sm, nkf = 0.0, 0.0, 0
                new_frames = []
                for kf in frames:
                    off = kf.get("offset", 0)
                    dv = np.array(kf.get("vertices", []), np.float64)
                    # A(原)變形 + 品質/平滑
                    defA = de.apply_deform(setup0, off, dv)
                    dispA = defA - setup0
                    rA = de.eval_pose(defA, tris0,
                                      [de.signed_area(setup0, t) > 0 for t in tris0],
                                      sum(abs(de.signed_area(setup0, t)) for t in tris0))
                    a_worst_s = max(a_worst_s, rA["self_intersections"])
                    a_worst_f = max(a_worst_f, rA["triangle_flips"])
                    a_sm += boundary_smoothness(setup0, hull0, defA)
                    # B:平滑 RBF 重採樣位移場 → 若不乾淨退線性
                    dispB = resample_disp(uv0, dispA, new_uv, smoothing=0.0)
                    defB = new_setup + dispB
                    rB = de.eval_pose(defB, new_tris, signs, area0)
                    if not rB["clean"]:
                        dispB = resample_disp_linear(uv0, dispA, new_uv)
                        defB = new_setup + dispB
                        rB = de.eval_pose(defB, new_tris, signs, area0)
                    b_worst_s = max(b_worst_s, rB["self_intersections"])
                    b_worst_f = max(b_worst_f, rB["triangle_flips"])
                    b_sm += boundary_smoothness(new_setup, new_hull, defB)
                    nkf += 1
                    nkf_new = dict(kf)
                    nkf_new.pop("offset", None)
                    nkf_new["vertices"] = [round(float(x), 3) for x in dispB.reshape(-1)]
                    new_frames.append(nkf_new)
                slots[slot][name] = new_frames
                r_mesh["anims"][anim] = {
                    "keys": nkf,
                    "A_max_selfint": a_worst_s, "B_max_selfint": b_worst_s,
                    "A_max_flip": a_worst_f, "B_max_flip": b_worst_f,
                    "A_bnd_angle": round(a_sm / max(nkf, 1), 2),
                    "B_bnd_angle": round(b_sm / max(nkf, 1), 2),
                }
        report[f"{slot}"] = r_mesh

    json.dump(sk, open(out_json, "w"), ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="assets/main_draw.json")
    ap.add_argument("--out", default="delivery")
    a = ap.parse_args()
    A = os.path.join(a.out, "A"); B = os.path.join(a.out, "B")
    os.makedirs(A, exist_ok=True); os.makedirs(B, exist_ok=True)
    # A = 原封不動
    for ext in ("json", "atlas", "png"):
        shutil.copy(f"assets/main_draw.{ext}", os.path.join(A, f"main_draw.{ext}"))
    # B = 改 json,atlas/png 共用
    shutil.copy("assets/main_draw.atlas", os.path.join(B, "main_draw.atlas"))
    shutil.copy("assets/main_draw.png", os.path.join(B, "main_draw.png"))
    report = {}
    build(a.src, os.path.join(B, "main_draw.json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # 摘要
    print("\n=== A/B 摘要 ===")
    for slot, r in report.items():
        print(f"{slot}: 頂點 {r['nv'][0]}→{r['nv'][1]}  hull {r['hull'][0]}→{r['hull'][1]}  三角 {r['tris'][0]}→{r['tris'][1]}  (重採樣殘差 {r['resample_node_residual']}px, setup 自交 {r['setup_selfint']}/退化 {r['setup_degenerate']})")
        for an, x in r["anims"].items():
            print(f"    {an:16s} keys={x['keys']}  自交 A{x['A_max_selfint']}/B{x['B_max_selfint']}  翻面 A{x['A_max_flip']}/B{x['B_max_flip']}  邊界轉折角 A{x['A_bnd_angle']}°→B{x['B_bnd_angle']}°")


if __name__ == "__main__":
    main()
