#!/usr/bin/env python3
"""權重模組 — unweighted mesh → weighted(envelope 綁定),S3 最後一塊。

對照 Award 藝術家真實權重 pattern 設計(見 knowledge/s5-weights.md):
  - 權重和恰 1、稀疏(藝術家 ≤3 骨/頂點、約半數頂點單骨)、混合只在關節局部。
  - 本 v1:每件 mesh 綁「自身骨 + parent 骨」兩根,關節(draft pivot)附近 smoothstep
    混向 parent,核心區剛性;wmax=0.85(藝術家接縫頂點次要骨最高 0.84,以此錨定)。
  - 半徑 R = k × sqrt(關節重疊面積/π)(重疊區 RMS 半徑;k 預設 2.5),無重疊資訊時 0.25×對角線。

範疇外(誠實邊界):
  - **子件級變形骨**(Award 的 4_LEG7/8 肩部輔助、4_LEG9 前臂):需要運動資訊才推得出
    「件內還要再分幾節」(S1 反推的事)。
  - **效果件跨件綁定**(光暈綁四根部位骨、跟著全身動):特效歸屬的全域決策(A 類)。
    v1 光暈剛性綁自身錨骨(靜態)。

weighted Spine 格式:vertices = [n, boneIdx, bindX, bindY, w, ...] × 頂點;
bind 為該骨 setup 局部座標(本骨架 rotation 全 0 → bind = 頂點世界 − 骨世界)。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

W_MAX = 0.85          # 藝術家接縫頂點次要骨最高 0.84
R_K = 2.5             # 關節半徑 = R_K × 重疊 RMS 半徑
W_EPS = 0.01          # 低於此的次要權重捨去(保持稀疏)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def envelope_weights(world_pts, joint_world, R):
    """回傳每頂點 parent 權重(0..W_MAX):關節處最高、R 外為 0。"""
    d = np.hypot(world_pts[:, 0] - joint_world[0], world_pts[:, 1] - joint_world[1])
    return W_MAX * smoothstep(1.0 - d / max(R, 1e-6))


def weight_mesh(verts_flat, own_world, parent_world, joint_world, R,
                own_idx, parent_idx):
    """verts_flat: unweighted mesh 頂點(相對 own bone 的局部座標,y-up)。
    回傳 Spine weighted vertices list。"""
    local = np.asarray(verts_flat, float).reshape(-1, 2)
    world = local + np.asarray(own_world)                 # rotation 0
    wp = envelope_weights(world, joint_world, R)
    out = []
    for i, (x, y) in enumerate(world):
        w2 = float(wp[i])
        if w2 < W_EPS:
            out += [1, own_idx, round(x - own_world[0], 3), round(y - own_world[1], 3), 1.0]
        else:
            w1 = 1.0 - w2
            out += [2,
                    own_idx, round(x - own_world[0], 3), round(y - own_world[1], 3), round(w1, 5),
                    parent_idx, round(x - parent_world[0], 3), round(y - parent_world[1], 3), round(w2, 5)]
    return out


def joint_radius(evidence, diag):
    ov = evidence.get("overlap_px")
    if ov:
        return R_K * math.sqrt(ov / math.pi)
    return 0.25 * diag


# ---------- LBS(rotation-0 骨架 + 單骨旋轉試驗) ----------
def parse_weighted(vflat):
    """→ [(n, [(bi,bx,by,w),...]), ...]"""
    out, i = [], 0
    v = vflat
    while i < len(v):
        n = int(v[i]); i += 1
        infl = []
        for _ in range(n):
            infl.append((int(v[i]), float(v[i+1]), float(v[i+2]), float(v[i+3])))
            i += 4
        out.append(infl)
    return out


def lbs_world(weighted, bone_world, bone_rot=None):
    """bone_world: idx->(x,y);bone_rot: idx->(pivot_x,pivot_y,theta) 對該骨的世界旋轉
    (繞 pivot 轉 theta;pivot 通常 = 骨世界位置)。回傳 Nx2 世界座標。"""
    pts = []
    for infl in weighted:
        acc = np.zeros(2)
        for (bi, bx, by, w) in infl:
            ox, oy = bone_world[bi]
            p = np.array([ox + bx, oy + by])
            if bone_rot and bi in bone_rot:
                px, py, th = bone_rot[bi]
                c, s = math.cos(th), math.sin(th)
                d = p - (px, py)
                p = np.array([px + c * d[0] - s * d[1], py + s * d[0] + c * d[1]])
            acc += w * p
        pts.append(acc)
    return np.array(pts)


if __name__ == "__main__":
    print("模組:由 skel_to_json --weights 調用;驗證見 validate_weights.py")
