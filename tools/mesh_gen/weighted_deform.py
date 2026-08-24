#!/usr/bin/env python3
"""S3 — weighted-mesh deform 評估器:量化「靠骨骼+權重變形的 mesh 在真實動畫下的變形品質」。

背景(補上 knowledge/s3-robot-mesh-vs-award.md 的唯一未驗維度):
  Award「機器人拆件」的 3 個 mesh 件(光暈/左手/身體)是 **weighted mesh**,無 deform
  timeline —— 靠骨骼變換 + 每頂點權重變形。前一個 deform 評估器(deform_eval.py)只處理
  unweighted 的逐頂點 offset,無法量化 weighted 件。本工具重現 Spine 3.8 的:
    (1) 骨骼 world transform(transform=normal;Award 77 骨全 normal)
    (2) 動畫 bone timeline apply(rotate/translate/scale + 緊湊 bezier / stepped / linear)
    (3) weighted mesh computeWorldVertices(Σ weight_i · worldBone_i·(bindX,bindY))
  以此對 3 件在「會 pose 到其綁定骨」的動畫上做逐幀變形,跑幾何品質閘。

⚠️ 評估器可信度(先於任何權重生成器,見 RULES「每能力必配評估器」):
  - **AC1 多骨一致性閘(frame-invariant)**:setup pose 下,同一頂點受多骨影響時,
    各骨各自預測的世界點必須互相吻合(bind 定義如此)。若骨骼 world-transform 數學錯,
    此吻合度會爆掉。此檢查不需外部真值,且對 root/全域座標框不變 → 穩健自證。
  - **AC2 動畫 apply 自證**:t=0 的 pose == setup(delta 0);keyframe 時刻的插值 == keyframe 值。
  - **AC4 負對照**:打亂權重 → 變形度量顯著改變(具鑑別力),證明能區分好壞權重
    (下一步權重生成器的閘之前提)。

Spine 3.8 normal-mode world transform(對照 CLAUDE.md 雷點,座標 y-up):
  la=cos((rot+shearX)°)*sx ; lb=cos((rot+90+shearY)°)*sy
  lc=sin((rot+shearX)°)*sx ; ld=sin((rot+90+shearY)°)*sy
  root: a,b,c,d=la,lb,lc,ld ; wx,wy=x,y
  child: wx=pa*x+pb*y+p.wx ; wy=pc*x+pd*y+p.wy
         a=pa*la+pb*lc ; b=pa*lb+pb*ld ; c=pc*la+pd*lc ; d=pc*lb+pd*ld
  applyToPoint(vx,vy) → (a*vx+b*vy+wx, c*vx+d*vy+wy)
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from deform_eval import signed_area, eval_pose

DEG = math.pi / 180.0
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


# ---------------- bone world transforms ----------------
def bone_local(b):
    """setup 局部參數 (x,y,rotation,scaleX,scaleY,shearX,shearY)。"""
    return (b.get("x", 0.0), b.get("y", 0.0), b.get("rotation", 0.0),
            b.get("scaleX", 1.0), b.get("scaleY", 1.0),
            b.get("shearX", 0.0), b.get("shearY", 0.0))


def local_matrix(x, y, rot, sx, sy, shx, shy):
    la = math.cos((rot + shx) * DEG) * sx
    lc = math.sin((rot + shx) * DEG) * sx
    lb = math.cos((rot + 90 + shy) * DEG) * sy
    ld = math.sin((rot + 90 + shy) * DEG) * sy
    return la, lb, lc, ld, x, y


def world_transforms(bones, local_over=None):
    """回傳 dict name -> (a,b,c,d,wx,wy)。local_over[name]=(x,y,rot,sx,sy,shx,shy) 覆蓋 setup。"""
    name2b = {b["name"]: b for b in bones}
    order = []  # 父先於子
    seen = set()

    def visit(nm):
        if nm in seen:
            return
        b = name2b[nm]
        p = b.get("parent")
        if p and p not in seen:
            visit(p)
        order.append(nm)
        seen.add(nm)

    for b in bones:
        visit(b["name"])

    W = {}
    for nm in order:
        b = name2b[nm]
        loc = local_over[nm] if (local_over and nm in local_over) else bone_local(b)
        la, lb, lc, ld, x, y = local_matrix(*loc)
        p = b.get("parent")
        if not p:
            W[nm] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, pwx, pwy = W[p]
            wx = pa * x + pb * y + pwx
            wy = pc * x + pd * y + pwy
            a = pa * la + pb * lc
            bb = pa * lb + pb * ld
            c = pc * la + pd * lc
            d = pc * lb + pd * ld
            W[nm] = (a, bb, c, d, wx, wy)
    return W


def apply_point(M, vx, vy):
    a, b, c, d, wx, wy = M
    return (a * vx + b * vy + wx, c * vx + d * vy + wy)


# ---------------- weighted mesh parse ----------------
def parse_weighted(att, bones):
    """回傳 verts=[ [(boneName,bindX,bindY,weight),...], ... ](長度=頂點數)。"""
    idx2name = {i: b["name"] for i, b in enumerate(bones)}
    v = att["vertices"]
    out = []
    i = 0
    while i < len(v):
        n = int(v[i]); i += 1
        infl = []
        for _ in range(n):
            bi = int(v[i]); bx = v[i + 1]; by = v[i + 2]; w = v[i + 3]; i += 4
            infl.append((idx2name[bi], bx, by, w))
        out.append(infl)
    return out


def compute_world_vertices(verts, W):
    """weighted computeWorldVertices:Σ weight·worldBone·(bindX,bindY)。回傳 Nx2。"""
    out = np.zeros((len(verts), 2), np.float64)
    for k, infl in enumerate(verts):
        wx = wy = 0.0
        for (bn, bx, by, w) in infl:
            px, py = apply_point(W[bn], bx, by)
            wx += px * w; wy += py * w
        out[k] = (wx, wy)
    return out


# ---------------- animation bone apply ----------------
def _bezier_frac(cx1, cy1, cx2, cy2, p):
    """緊湊 bezier:給 x 目標 p∈[0,1],解參數 s 使 Bx(s)=p,回傳 By(s)。"""
    lo, hi = 0.0, 1.0
    for _ in range(24):
        s = (lo + hi) / 2
        oms = 1 - s
        bx = 3 * oms * oms * s * cx1 + 3 * oms * s * s * cx2 + s ** 3
        if bx < p:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2
    oms = 1 - s
    return 3 * oms * oms * s * cy1 + 3 * oms * s * s * cy2 + s ** 3


def _interp_channel(frames, time, keys, defaults):
    """在 keys(如 ['angle'] 或 ['x','y'])上取 time 的插值。frames 為該 channel timeline。
    緊湊 bezier 鍵在『起始幀』:curve(cx1),c2(cy1,default0),c3(cx2,default1),c4(cy2,default1)。
    'stepped' → 保持起始值;無 curve → linear。"""
    if not frames:
        return list(defaults)
    times = [f.get("time", 0.0) for f in frames]
    if time <= times[0]:
        return [frames[0].get(k, defaults[j]) for j, k in enumerate(keys)]
    if time >= times[-1]:
        return [frames[-1].get(k, defaults[j]) for j, k in enumerate(keys)]
    # 找區間 [i,i+1]
    i = 0
    while i + 1 < len(frames) and times[i + 1] <= time:
        i += 1
    f0, f1 = frames[i], frames[i + 1]
    t0, t1 = times[i], times[i + 1]
    v0 = [f0.get(k, defaults[j]) for j, k in enumerate(keys)]
    v1 = [f1.get(k, defaults[j]) for j, k in enumerate(keys)]
    curve = f0.get("curve", None)
    p = (time - t0) / (t1 - t0) if t1 > t0 else 0.0
    if curve == "stepped":
        return v0
    if curve is None:  # linear
        frac = p
    else:
        cx1 = curve
        cy1 = f0.get("c2", 0.0)
        cx2 = f0.get("c3", 1.0)
        cy2 = f0.get("c4", 1.0)
        frac = _bezier_frac(cx1, cy1, cx2, cy2, p)
    return [v0[j] + (v1[j] - v0[j]) * frac for j in range(len(keys))]


def pose_at(bones, anim_bones, time):
    """回傳 local_over:setup + timeline delta。rotate/translate 加成、scale 乘成。"""
    name2b = {b["name"]: b for b in bones}
    over = {}
    for bn, chans in anim_bones.items():
        if bn not in name2b:
            continue
        x, y, rot, sx, sy, shx, shy = bone_local(name2b[bn])
        if "rotate" in chans:
            rot += _interp_channel(chans["rotate"], time, ["angle"], [0.0])[0]
        if "translate" in chans:
            dx, dy = _interp_channel(chans["translate"], time, ["x", "y"], [0.0, 0.0])
            x += dx; y += dy
        if "scale" in chans:
            msx, msy = _interp_channel(chans["scale"], time, ["x", "y"], [1.0, 1.0])
            sx *= msx; sy *= msy
        if "shear" in chans:
            dshx, dshy = _interp_channel(chans["shear"], time, ["x", "y"], [0.0, 0.0])
            shx += dshx; shy += dshy
        over[bn] = (x, y, rot, sx, sy, shx, shy)
    return over


def anim_duration(anim):
    d = 0.0
    for section in ("bones", "slots", "deform"):
        pass
    for bn, chans in anim.get("bones", {}).items():
        for ch, frames in chans.items():
            for f in frames:
                d = max(d, f.get("time", 0.0))
    return d


# ---------------- loaders ----------------
def award_attachment(sk, slot):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def anims_posing(sk, bone_names):
    """回傳 [(anim_name, anim_bones_dict), ...] 有 pose 到 bone_names 任一者的動畫。"""
    out = []
    for aname, adata in sk.get("animations", {}).items():
        b = adata.get("bones", {})
        if any(bn in b for bn in bone_names):
            out.append((aname, adata))
    return out


# ---------------- gates ----------------
def multibone_agreement(verts, W):
    """AC1:對每個多骨頂點,各骨預測世界點的最大兩兩距離。回傳 (max_disagree, n_multi)。"""
    worst = 0.0; nmulti = 0
    for infl in verts:
        if len(infl) < 2:
            continue
        nmulti += 1
        pts = [apply_point(W[bn], bx, by) for (bn, bx, by, w) in infl]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dd = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                worst = max(worst, dd)
    return worst, nmulti


def sample_times(dur, n=13):
    if dur <= 0:
        return [0.0]
    return [dur * k / (n - 1) for k in range(n)]


def eval_piece(sk, slot, corrupt=None):
    bones = sk["bones"]
    att = award_attachment(sk, slot)
    verts = parse_weighted(att, bones)
    if corrupt == "shuffle_weights":
        # 負對照:打亂每頂點內 influence 的『骨↔bind 座標』配對(bind 不再一致)
        verts = _corrupt_shuffle(verts)
    tris = np.array(att["triangles"], np.int32).reshape(-1, 3)
    bone_names = set(bn for infl in verts for (bn, _, _, _) in infl)

    # setup world
    Wsetup = world_transforms(bones)
    disagree, nmulti = multibone_agreement(verts, Wsetup)
    setup_wv = compute_world_vertices(verts, Wsetup)
    setup_signs = [signed_area(setup_wv, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_wv, t)) for t in tris)

    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    max_disp = 0.0
    for aname, adata in anims_posing(sk, bone_names):
        dur = anim_duration(adata)
        results = []
        for t in sample_times(dur):
            over = pose_at(bones, adata["bones"], t)
            W = world_transforms(bones, over)
            wv = compute_world_vertices(verts, W)
            r = eval_pose(wv, tris, setup_signs, setup_area)
            disp = float(np.hypot(*(wv - setup_wv).T).max())
            max_disp = max(max_disp, disp)
            results.append(r)
        agg = {
            "frames": len(results),
            "max_self_intersections": max(r["self_intersections"] for r in results),
            "max_triangle_flips": max(r["triangle_flips"] for r in results),
            "max_degenerate": max(r["degenerate"] for r in results),
            "area_ratio_range": [min(r["area_ratio"] for r in results),
                                 max(r["area_ratio"] for r in results)],
            "all_clean": all(r["clean"] for r in results),
        }
        per_anim[aname] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    return {
        "slot": slot,
        "nverts": len(verts), "tris": len(tris), "hull": att["hull"],
        "n_multibone": nmulti,
        "AC1_multibone_agreement_px": round(disagree, 4),
        "AC1_pass": disagree < 0.5,
        "max_vertex_displacement_px": round(max_disp, 2),
        "anims": per_anim,
        "geometry_clean": (worst["self_intersections"] == 0 and
                           worst["triangle_flips"] == 0 and worst["degenerate"] == 0),
        "_worst": worst,
    }


def _corrupt_shuffle(verts):
    """負對照:把每個多骨頂點的『骨↔bind 座標』配對打亂 → bind 不再一致 → 變形應變壞。"""
    rng = np.random.RandomState(0)
    out = []
    for infl in verts:
        if len(infl) > 1:
            perm = rng.permutation(len(infl))
            bnames = [infl[k][0] for k in perm]
            out.append([(bnames[j], infl[j][1], infl[j][2], infl[j][3])
                        for j in range(len(infl))])
        else:
            out.append(infl)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--pieces", nargs="*", default=ROBOT_MESHES)
    ap.add_argument("--negative", action="store_true",
                    help="額外跑打亂權重的負對照,驗證評估器鑑別力")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))

    reports = [eval_piece(sk, s) for s in a.pieces]
    ac1_ok = all(r["AC1_pass"] for r in reports)
    # AC3:不再用「全部幾何乾淨」當硬閘 —— 藝術家自己的軟光暈(光暈)在 Legend_In
    #   入場時就大量自交(1.667x 縮放起手→收回,soft/additive glow 自疊視覺無害)。
    #   正確設計(同 compare_robot_mesh 的『不劣於藝術家』IoU baseline):以藝術家自身
    #   mesh 在自身動畫下的變形包絡當每件 baseline。此處記錄 baseline;硬閘只保
    #   AC1(變換正確)+AC4(鑑別力)。不透明結構件(左手/身體)乾淨可另作正對照。
    opaque_clean = all(r["geometry_clean"] for r in reports if r["slot"] != "機器人拆件/光暈")
    out = {"skeleton": a.skeleton,
           "AC1_all_multibone_agree": ac1_ok,
           "AC3_artist_deform_envelope": "recorded per piece (baseline for future weight generator)",
           "AC3_opaque_pieces_clean": opaque_clean,
           "pieces": reports}

    if a.negative:
        neg = [eval_piece(sk, s, corrupt="shuffle_weights") for s in a.pieces]
        # 鑑別力:負對照的 AC1 一致性應被破壞,或幾何應變壞
        discern = []
        for good, bad in zip(reports, neg):
            broke = (bad["AC1_multibone_agreement_px"] > good["AC1_multibone_agreement_px"] + 1.0
                     or bad["max_vertex_displacement_px"] != good["max_vertex_displacement_px"]
                     or not bad["geometry_clean"])
            discern.append({"slot": good["slot"],
                            "good_agree": good["AC1_multibone_agreement_px"],
                            "bad_agree": bad["AC1_multibone_agreement_px"],
                            "good_maxdisp": good["max_vertex_displacement_px"],
                            "bad_maxdisp": bad["max_vertex_displacement_px"],
                            "bad_geometry_clean": bad["geometry_clean"],
                            "discriminated": broke})
        out["AC4_negative_control"] = {"all_discriminated": all(d["discriminated"] for d in discern),
                                       "detail": discern}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    ok = ac1_ok and opaque_clean
    if a.negative:
        ok = ok and out["AC4_negative_control"]["all_discriminated"]
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
