#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端「PSD 件 → S3 mesh」對照 Award 真實生產 mesh 的整合驗收閘。

流程(全純 CPU、無需 GPU / 無需外部 CDN):
  robot_parts.psd  --psd_slice-->  各部位件 PNG
                   --generate_mesh_v2-->  自動 mesh(unweighted)
                   --evaluate_mesh-->      靜態覆蓋閘(vs 件 alpha)
                   --本檔-->               對照 Award.json 真實 mesh(輪廓 IoU + 頂點預算)

為何用「uv 輪廓 + best-of-8 dihedral」做真值對照(不需骨頭變換、不需 uv 反解旋轉):
  - Award 這 3 件在生產檔是 **weighted** mesh(vertices≠uvs),setup 世界座標需骨頭變換。
  - 但每個 mesh 的 **uv layout 本身就是它在貼圖上的 2D 輪廓嵌入**(頂點貼在素材上)。
  - 把兩邊 hull 各自正規化到自身 bbox,再對 8 個二面體變換(4 旋轉×2 翻)取最佳 IoU,
    即可吸收 scale/atlas-rotate/flip 差異,純比「形狀」。
  - 判別力自驗:對角(同件)IoU 必須顯著 > 非對角(不同件),否則此指標不可信。

預設對照 robot_parts.psd 的 3 個「在 Award 中為 mesh」的件:光暈 / 身體 / 左手。
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))

# robot_parts.psd 件檔名(psd_slice 產出) → Award.json 的 slot
DEFAULT_MAP = {
    "00_光暈": "機器人拆件/光暈",
    "03_身體": "機器人拆件/身體",
    "04_左手": "機器人拆件/左手",
}


# ---------- Award 真實 mesh 讀取 ----------
def load_award_meshes(award_json):
    d = json.load(open(award_json, encoding="utf-8"))
    skins = d["skins"]
    it = skins if isinstance(skins, list) else [{"name": k, "attachments": v} for k, v in skins.items()]
    out = {}
    for skin in it:
        for slot, sa in skin["attachments"].items():
            for an, a in sa.items():
                if isinstance(a, dict) and a.get("type") == "mesh":
                    out[slot] = {"uvs": a["uvs"], "hull": a["hull"]}
    return out


# ---------- 輪廓形狀比較(無變換依賴) ----------
def hull_poly(uvs, hull):
    """Spine 慣例:vertices/uvs 前 hull 個即 hull 周界(依序)。"""
    uv = np.asarray(uvs, float).reshape(-1, 2)
    return uv[:hull]


def raster(poly, S=256):
    p = poly.astype(float).copy()
    mn = p.min(0); span = p.max(0) - mn; span[span == 0] = 1
    p = (p - mn) / span * (S - 1)
    img = np.zeros((S, S), np.uint8)
    cv2.fillPoly(img, [p.astype(np.int32)], 1)
    return img


def _dihedral(img, k):
    r = np.rot90(img, k % 4)
    if k >= 4:
        r = np.fliplr(r)
    return np.ascontiguousarray(r)


def best_iou(pa, pb):
    a = raster(pa)
    best = 0.0
    for k in range(8):
        b = _dihedral(raster(pb), k)
        inter = np.logical_and(a, b).sum(); uni = np.logical_or(a, b).sum()
        best = max(best, inter / uni if uni else 0.0)
    return float(best)


# ---------- pipeline 步驟(呼叫既有工具) ----------
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0, 1):  # evaluate_mesh 以 exit 1 表 fail,仍要讀 stdout
        sys.stderr.write(r.stderr)
        raise RuntimeError(f"命令失敗: {' '.join(cmd)}")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--psd", default=os.path.join(HERE, "../../assets/robot_parts.psd"))
    ap.add_argument("--award", default=os.path.join(HERE, "../../assets/Award.json"))
    ap.add_argument("--tmp", default=None, help="工作目錄(預設用暫存)")
    ap.add_argument("--iou_thresh", type=float, default=0.85, help="輪廓 IoU 對真值的通過門檻")
    args = ap.parse_args()

    tmp = args.tmp or tempfile.mkdtemp(prefix="cmp_award_")
    pieces = os.path.join(tmp, "pieces"); meshes = os.path.join(tmp, "meshes")
    os.makedirs(meshes, exist_ok=True)

    # 1) PSD → 件
    run([sys.executable, os.path.join(HERE, "psd_slice.py"), args.psd, "-o", pieces])
    aw = load_award_meshes(args.award)

    rows = []
    genpoly, awpoly = {}, {}
    for fkey, slot in DEFAULT_MAP.items():
        piece = os.path.join(pieces, f"{fkey}.png")
        mjson = os.path.join(meshes, f"{fkey}.json")
        # 2) 件 → v2 mesh
        run([sys.executable, os.path.join(HERE, "generate_mesh_v2.py"), piece, "-o", mjson])
        g = json.load(open(mjson))
        # 3) 靜態覆蓋閘
        ev = run([sys.executable, os.path.join(HERE, "evaluate_mesh.py"), mjson, piece])
        ej = json.loads(ev.stdout)
        gv, gh = len(g["uvs"]) // 2, g["hull"]
        av, ah = len(aw[slot]["uvs"]) // 2, aw[slot]["hull"]
        genpoly[slot] = hull_poly(g["uvs"], g["hull"])
        awpoly[slot] = hull_poly(aw[slot]["uvs"], aw[slot]["hull"])
        rows.append({
            "piece": slot.split("/")[-1], "slot": slot, "mode": g.get("_mode"),
            "static_iou": round(ej["criteria"]["AC1_iou"]["value"], 4),
            "static_pass": ej["criteria"]["AC1_iou"]["pass"],
            "gen_v": gv, "gen_h": gh, "art_v": av, "art_h": ah,
            "v_ratio": round(gv / av, 2),
        })

    # 4) 輪廓 IoU 矩陣(對真值)
    slots = [r["slot"] for r in rows]
    mat = {gs: {as_: best_iou(genpoly[gs], awpoly[as_]) for as_ in slots} for gs in slots}
    for r in rows:
        s = r["slot"]
        r["silhouette_iou"] = round(mat[s][s], 3)
        offs = [mat[s][o] for o in slots if o != s]
        r["max_offdiag"] = round(max(offs), 3)
        # 判別:對角需為該列最大且 > 所有非對角
        r["discriminative"] = all(mat[s][s] > mat[s][o] for o in slots if o != s)
        r["silhouette_pass"] = (r["silhouette_iou"] >= args.iou_thresh) and r["discriminative"]
        r["budget_pass"] = r["gen_v"] <= r["art_v"]

    # ---------- 報告 ----------
    print("=== 端到端 PSD件→S3 v2 mesh → 對照 Award 真實 mesh ===\n")
    hdr = f"{'件':6s} {'mode':11s} {'靜態IoU':>8s} {'輪廓IoU':>8s} {'非對角max':>9s} {'gen v/h':>9s} {'art v/h':>9s} {'v比':>5s}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['piece']:6s} {r['mode']:11s} {r['static_iou']:8.3f} "
              f"{r['silhouette_iou']:8.3f} {r['max_offdiag']:9.3f} "
              f"{str(r['gen_v'])+'/'+str(r['gen_h']):>9s} "
              f"{str(r['art_v'])+'/'+str(r['art_h']):>9s} {r['v_ratio']:5.2f}")

    print("\n=== 輪廓 IoU 矩陣 (gen列 × award行, best-of-8 dihedral) — 判別力自驗 ===")
    print("gen\\art".ljust(8) + "".join(s.split('/')[-1].rjust(8) for s in slots))
    for gs in slots:
        print(gs.split('/')[-1].ljust(8) + "".join(f"{mat[gs][a]:8.3f}" for a in slots))

    overall = all(r["silhouette_pass"] and r["budget_pass"] for r in rows)
    print("\n逐件判定:")
    for r in rows:
        print(f"  {r['piece']}: 靜態覆蓋={'PASS' if r['static_pass'] else 'FAIL'}  "
              f"輪廓對真值={'PASS' if r['silhouette_pass'] else 'FAIL'}  "
              f"頂點預算≤藝術家={'PASS' if r['budget_pass'] else 'FAIL'}")
    print(f"\nOVERALL (輪廓+預算全過): {'PASS' if overall else 'FAIL'}")
    print("註:光暈靜態覆蓋為已知軟 alpha 邊緣限制(見 knowledge/s3-psd-to-award-mesh.md)。")

    print("\n" + json.dumps({"rows": rows}, ensure_ascii=False))
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
