#!/usr/bin/env python3
"""端到端對照:PSD件 → S3 generate_mesh_v2 → 對 Award 真實(藝術家)mesh。
靜態覆蓋(IoU vs alpha)+ 拓樸(頂點/三角/hull)+ 頂點預算。
robot mesh 為 weighted 且無 deform timeline → 變形閘 N/A(見結論)。
"""
import sys, json
sys.path.insert(0, '/home/user/work-all-night/tools/mesh_gen')
import numpy as np, cv2
import generate_mesh_v2 as g
import evaluate_mesh as e

PIECES = [
    ("機器人拆件/光暈", "scratch_robot/guangyun.png"),
    ("機器人拆件/左手", "scratch_robot/zuoshou.png"),
    ("機器人拆件/身體", "scratch_robot/shenti.png"),
]
AWARD = json.load(open('assets/Award.json'))
_sk = AWARD['skins']
ATTS = _sk['default'] if isinstance(_sk, dict) else next(s for s in _sk if s['name'] == 'default')['attachments']


def artist_coverage(name, W, H):
    """把藝術家 mesh 的 uvs(region-local 0..1)+ triangles 光柵化到 (H,W),回覆蓋 mask。"""
    a = ATTS[name][name]
    uvs = a['uvs']
    tris = np.array(a['triangles'], dtype=np.int32).reshape(-1, 3)
    nv = len(uvs) // 2
    # Spine uv: (0,0)=左上, v 向下 → pixel = (u*W, v*H)
    pts = np.array([[uvs[2*i]*W, uvs[2*i+1]*H] for i in range(nv)], dtype=np.float64)
    cov = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(cov, np.round(pts[t]).astype(np.int32), 1)
    return cov, nv, len(tris), a['hull']


def iou(a, b):
    a = (a > 0); b = (b > 0)
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


report = {}
for name, png in PIECES:
    mask, W, H = g.load_mask(png)          # PSD 件原始尺寸
    m = (mask > 0).astype(np.uint8)
    # --- 我的 mesh ---
    mesh = g.generate(png)
    ev = e.evaluate(mesh, mask, iou_thresh=0.90)
    my_iou = ev['criteria']['AC1_iou']['value']
    my_nv = ev['vertices']; my_tris = ev['triangles']; my_hull = ev['hull']
    # --- 藝術家 mesh(對照真值,縮放到同一 piece 尺寸)---
    cov, a_nv, a_tris, a_hull = artist_coverage(name, W, H)
    art_iou = round(iou(cov, m), 4)
    # y-flip 健檢(確認 uv 慣例)
    covf = artist_coverage(name, W, H)[0]  # same
    report[name] = {
        "piece_px": [W, H], "alpha_cov": round(float(m.mean()), 3),
        "mine": {"mode": mesh.get('_mode'), "iou": my_iou, "verts": my_nv,
                 "tris": my_tris, "hull": my_hull, "static_pass": ev['overall_pass']},
        "artist": {"iou": art_iou, "verts": a_nv, "tris": a_tris, "hull": a_hull,
                   "weighted": len(ATTS[name][name]['vertices']) != len(ATTS[name][name]['uvs'])},
        "AC1_mine_ge_artist": my_iou >= art_iou,
    }

print(json.dumps(report, ensure_ascii=False, indent=2))
