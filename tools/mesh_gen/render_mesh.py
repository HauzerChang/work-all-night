#!/usr/bin/env python3
"""純 CPU 貼圖網格渲染器 —— 取代 spine_inspector 的「實機 round-trip」視覺驗證。

背景:排程環境網路政策擋 jsDelivr/esotericsoftware(403),spine-webgl 3.8 runtime 載不進來;
npm 只有 4.x(與 3.8 資產不相容)。故改用離線、可自動化的純 CPU 渲染:
逐三角形把貼圖(UV)仿射映射到頂點位置 → 渲染出「貼好圖的 mesh」。
setup pose 應重現原貼圖(round-trip 正確性);套真實 deform 後可目視有無撕裂/穿插。

用法:render_mesh.py <mesh.json> <texture.png> [-o out.png]
  或 import:render(tex_bgra, mesh, dst_px) → BGR 畫布。
"""
import argparse, json, sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))


def _warp_triangle(tex, src, dst, out):
    """把 tex 上 src 三角仿射貼到 out 上 dst 三角(含 alpha 合成)。"""
    r = cv2.boundingRect(np.float32([dst]))
    x, y, w, h = r
    if w <= 0 or h <= 0:
        return
    dst_local = dst - np.array([x, y], np.float32)
    M = cv2.getAffineTransform(np.float32(src), np.float32(dst_local))
    patch = cv2.warpAffine(tex, M, (w, h), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REFLECT_101)
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, np.int32(dst_local), 255, cv2.LINE_AA)
    H, W = out.shape[:2]
    if x < 0 or y < 0 or x + w > W or y + h > H:
        return
    roi = out[y:y + h, x:x + w]
    if patch.shape[2] == 4:
        a = (patch[:, :, 3:4] / 255.0) * (mask[:, :, None] / 255.0)
        roi[:] = (patch[:, :, :3] * a + roi * (1 - a)).astype(np.uint8)
    else:
        m3 = mask[:, :, None] / 255.0
        roi[:] = (patch * m3 + roi * (1 - m3)).astype(np.uint8)


def render(tex, mesh, dst_px, canvas_wh, bg=(28, 28, 28)):
    """dst_px: Nx2 頂點在畫布上的像素座標。回傳 BGR 畫布。"""
    W, H = canvas_wh
    tw, th = mesh["width"], mesh["height"]
    uvs = np.array(mesh["uvs"]).reshape(-1, 2)
    src = np.column_stack([uvs[:, 0] * tw, uvs[:, 1] * th])
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    out = np.full((H, W, 3), bg, np.uint8)
    for t in tris:
        _warp_triangle(tex, src[t], dst_px[t].astype(np.float32), out)
    return out


def setup_px(mesh):
    """setup pose 頂點像素座標(由 y-up 置中還原)。"""
    v = mesh["vertices"]; W, H = mesh["width"], mesh["height"]
    s = np.column_stack([v[0::2], v[1::2]])
    return np.column_stack([s[:, 0] + W / 2.0, H / 2.0 - s[:, 1]])


def deformed_px(mesh, skeleton, slot, name):
    """套真實位移場後的頂點像素座標(用於撕裂檢查渲染)。"""
    import deform_eval as de
    from scipy.interpolate import griddata
    uvs_src, field, _ = de.real_deform_field(skeleton, slot, name)
    mu = np.array(mesh["uvs"]).reshape(-1, 2)
    dx = griddata(uvs_src, field[:, 0], mu, "linear"); dy = griddata(uvs_src, field[:, 1], mu, "linear")
    nx = griddata(uvs_src, field[:, 0], mu, "nearest"); ny = griddata(uvs_src, field[:, 1], mu, "nearest")
    dx = np.where(np.isnan(dx), nx, dx); dy = np.where(np.isnan(dy), ny, dy)
    base = setup_px(mesh)
    # field 為 y-up local;畫布為 y-down → y 位移取負
    return np.column_stack([base[:, 0] + dx, base[:, 1] - dy])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh_json")
    ap.add_argument("texture")
    ap.add_argument("-o", "--out", default="render.png")
    a = ap.parse_args()
    mesh = json.load(open(a.mesh_json))
    tex = cv2.imread(a.texture, cv2.IMREAD_UNCHANGED)
    img = render(tex, mesh, setup_px(mesh), (mesh["width"], mesh["height"]))
    cv2.imwrite(a.out, img)
    print(f"rendered setup → {a.out}")


if __name__ == "__main__":
    main()
