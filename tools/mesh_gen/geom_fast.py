#!/usr/bin/env python3
"""向量化幾何檢查(自交/翻面/退化)—— 讓 weighted_deform_eval 的多 pose 掃描實用化。

與 deform_eval.py 的純 Python O(E²) 檢查**數值一致**(同 orientation 準則),
但用 numpy 一次算完所有非相鄰邊對 → 快 1~2 個數量級。
自我一致性:tools 內含 `assert_matches_reference` 對 deform_eval 抽樣核對。
"""
import numpy as np


def tri_edges(tris):
    s = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            s.add((min(int(a), int(b)), max(int(a), int(b))))
    return np.array(sorted(s), np.int32)


def signed_areas(pts, tris):
    a = pts[tris[:, 0]]; b = pts[tris[:, 1]]; c = pts[tris[:, 2]]
    return ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) -
            (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])) / 2.0


def _orient(a, b, c):
    """sign of cross((b-a),(c-a)); 0 if |.|<1e-9. a,b (N,2); c (N,2)."""
    v = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    o = np.zeros(len(v), np.int8)
    o[v > 1e-9] = 1; o[v < -1e-9] = -1
    return o


def count_self_intersections(pts, edges):
    """非相鄰邊對真交叉數(proper crossing;共享端點的邊對排除)。向量化。"""
    E = len(edges)
    if E < 2:
        return 0
    ii, jj = np.triu_indices(E, k=1)
    e1 = edges[ii]; e2 = edges[jj]
    # 排除共享頂點
    share = ((e1[:, 0] == e2[:, 0]) | (e1[:, 0] == e2[:, 1]) |
             (e1[:, 1] == e2[:, 0]) | (e1[:, 1] == e2[:, 1]))
    m = ~share
    if not m.any():
        return 0
    p1 = pts[e1[m, 0]]; p2 = pts[e1[m, 1]]; p3 = pts[e2[m, 0]]; p4 = pts[e2[m, 1]]
    d1 = _orient(p3, p4, p1); d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3); d4 = _orient(p1, p2, p4)
    cross = (d1 != d2) & (d3 != d4) & (d1 != 0) & (d2 != 0) & (d3 != 0) & (d4 != 0)
    return int(cross.sum())


def eval_pose_fast(verts, tris, edges, setup_signs, setup_area):
    """回傳 dict,鍵同 deform_eval.eval_pose(self_intersections/triangle_flips/degenerate/
    area_ratio/bbox/clean)。setup_signs: bool array(signed_area>0);setup_area: float。"""
    sa = signed_areas(verts, tris)
    degen = int((np.abs(sa) < 1e-6).sum())
    pos = sa > 0
    flips = int(((pos != setup_signs) & (np.abs(sa) >= 1e-6)).sum())
    xs = count_self_intersections(verts, edges)
    area = float(np.abs(sa).sum())
    mn = verts.min(0); mx = verts.max(0)
    return {"self_intersections": xs, "triangle_flips": flips, "degenerate": degen,
            "area_ratio": round(area / setup_area, 3) if setup_area else 0.0,
            "bbox": [round(float(mx[0] - mn[0]), 1), round(float(mx[1] - mn[1]), 1)],
            "clean": xs == 0 and flips == 0 and degen == 0}
