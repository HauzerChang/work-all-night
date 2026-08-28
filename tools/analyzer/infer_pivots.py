#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5 關節 pivot 推斷器（rig pivot inference）——「件（含世界輪廓）→ 骨架樹 + 各關節 pivot」。

路線圖 S5 的第一個純幾何、可自主收斂的塊：給定一組已切好的「件」(每件一組世界座標多邊形
silhouette)，**不看真實骨架**，推斷：
  (1) 哪些件互為相鄰（會構成關節）；
  (2) 骨架階層樹（root=軀幹，四肢掛在軀幹上）；
  (3) 每條 parent→child 邊的 **pivot 世界座標**（子件繞它旋轉的關節中心）。

核心原理（確定性、非 ML）:
  - **關節 pivot = 兩相鄰件輪廓 overlap 區域的形心**。鉸鏈件在關節處交疊，形心落在關節。
  - **相鄰判定 = overlap 面積 ≥ τ × 較小件面積**（frac_of_smaller），濾掉不相接的件。
  - **樹 = 由 root 做 BFS**：每件的 parent = 最先在 BFS 中觸及它的已入樹件。
    這比「最大 overlap MST」穩健——四肢彼此的假交疊（如大張的手臂貼圖蓋到頭）
    不會被誤判成關節，因為兩件都已先被軀幹觸及（同層，不互為 parent/child）。
  - **特效層剔除**：對「≥半數其他件、且各以 frac≥0.9 覆蓋」者標記為 effect（如全幅光暈），
    不納入結構樹（對齊 build_meta 的 effect/structural 語意）。

⚠️ 誠實界定:
  - pivot 精度**相依 silhouette 緊緻度**（見 validate_pivots）：件必須是真實 alpha 輪廓
    (mesh 頂點 / atlas alpha 輪廓)，**不能是鬆散的 bounding-box**——鬆散框會把 overlap 形心
    拉向件中心（右手件實測 132px→25px 誤差差距即此）。
  - pivot 只推「關節中心」，**不推子件相對父件的初始旋轉/長度**（那由骨鏈幾何另算）。
  - 本器只做「已切件」→ rig 骨架 pivot；切件本身由 S1/S4 產出。

輸入抽象：parts = { name: [poly, ...] }，poly = [(x,y), ...] 世界座標（多邊形，可多塊/三角面）。
"""
import math
import numpy as np
import cv2


def _bbox(parts):
    pts = [p for polys in parts.values() for poly in polys for p in poly]
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def rasterize(parts, pad=5):
    """把每件的世界多邊形填成共用網格上的 mask。回傳 (masks, origin, shape)。"""
    minx, miny, maxx, maxy = _bbox(parts)
    minx -= pad
    miny -= pad
    Wg = int(math.ceil(maxx - minx)) + pad + 1
    Hg = int(math.ceil(maxy - miny)) + pad + 1
    masks = {}
    for name, polys in parts.items():
        m = np.zeros((Hg, Wg), np.uint8)
        for poly in polys:
            if len(poly) < 3:
                continue
            pts = np.array([[px - minx, py - miny] for px, py in poly], np.int32)
            cv2.fillPoly(m, [pts], 1)
        masks[name] = m
    return masks, (minx, miny), (Hg, Wg)


def overlap_graph(masks):
    """回傳 (areas, ov, frac)：ov[(a,b)] overlap 像素、frac[(a,b)] overlap/min_area。"""
    names = list(masks)
    areas = {n: int((masks[n] > 0).sum()) for n in names}
    ov, frac = {}, {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            o = int(((masks[a] > 0) & (masks[b] > 0)).sum())
            ov[(a, b)] = ov[(b, a)] = o
            denom = max(1, min(areas[a], areas[b]))
            frac[(a, b)] = frac[(b, a)] = o / denom
    return areas, ov, frac


def detect_effects(masks, areas, frac, cover=0.9, min_frac_of_parts=0.5):
    """全幅特效層偵測：對『≥min_frac_of_parts 比例的其他件、各以 frac≥cover 覆蓋』者標 effect。"""
    names = list(masks)
    eff = set()
    for n in names:
        others = [m for m in names if m != n]
        if not others:
            continue
        covered = sum(1 for m in others if frac[(n, m)] >= cover)
        if covered >= math.ceil(min_frac_of_parts * len(others)):
            eff.add(n)
    return eff


def overlap_centroid(masks, a, b, origin):
    """兩件 overlap 區域的世界形心，或 None（無交疊）。"""
    minx, miny = origin
    ov = (masks[a] > 0) & (masks[b] > 0)
    if ov.sum() == 0:
        return None
    ys, xs = np.where(ov)
    return (float(xs.mean()) + minx, float(ys.mean()) + miny)


def infer(parts, tau=0.02, root=None, exclude_effects=True):
    """主入口。回傳 dict：
      { root, effects, structural, hierarchy{child:parent}, pivots{child:(x,y)},
        edges[(parent,child,pivot,overlap_px)], areas, masks, origin }
    tau：相鄰判定門檻（frac_of_smaller）。root=None 時取最大結構件。"""
    masks, origin, shape = rasterize(parts)
    areas, ov, frac = overlap_graph(masks)
    effects = detect_effects(masks, areas, frac) if exclude_effects else set()
    structural = [n for n in masks if n not in effects]
    if not structural:
        return dict(root=None, effects=effects, structural=[], hierarchy={},
                    pivots={}, edges=[], areas=areas, masks=masks, origin=origin)
    if root is None:
        root = max(structural, key=lambda n: areas[n])

    # 相鄰表（結構件之間，frac ≥ tau）
    adj = {n: [] for n in structural}
    for i, a in enumerate(structural):
        for b in structural[i + 1:]:
            if frac[(a, b)] >= tau:
                adj[a].append(b)
                adj[b].append(a)

    # BFS 建樹：parent = BFS 中最先觸及者；同一件的多個候選父取 overlap 最大者
    hierarchy, edges, pivots = {}, [], {}
    visited = {root}
    frontier = [root]
    while frontier:
        nxt = []
        # 先蒐集本層每個未訪子件的最佳父（overlap 最大的已訪相鄰件）
        cand = {}
        for parent in frontier:
            for child in adj[parent]:
                if child in visited:
                    continue
                if child not in cand or ov[(parent, child)] > ov[(cand[child], child)]:
                    cand[child] = parent
        for child, parent in cand.items():
            visited.add(child)
            hierarchy[child] = parent
            piv = overlap_centroid(masks, parent, child, origin)
            pivots[child] = piv
            edges.append((parent, child, piv, ov[(parent, child)]))
            nxt.append(child)
        frontier = nxt

    return dict(root=root, effects=effects, structural=structural,
                hierarchy=hierarchy, pivots=pivots, edges=edges,
                areas=areas, masks=masks, origin=origin)
