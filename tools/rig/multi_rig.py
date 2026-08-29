"""S5 rig pivot 推斷 — 多 rig 泛化 + 兩種資產表徵的方法對應。

把「pivot 推斷只在單一 rig(Award 機器人)驗過」的限制拆掉。做法是引入 Award 另外三個角色
OMG(1_OMG)、SUPERWIN(2_SUP)、MEGAWIN(3_MEG,兩張圖)——它們**不是拆件式**,各自是
**單一 weighted mesh** 由一條骨鏈變形。

核心發現:**推斷方法必須對應資產表徵。**
  ┌ 拆件式(separated parts;PSD 分層 / 機器人 slot-per-part):件之間有真實空隙,
  │   關節在「子件 ⇄ 父件」幾何接觸縫 → 用 `infer_pivots.contact_seam_joint`(幾何法)。
  └ 單一 weighted mesh(連續網格,骨以權重共享頂點):件之間沒有幾何縫,dominant-weight 硬切
      會把肩部頂點分給手臂 → 幾何最近點落在末梢而非關節(實測手臂爆掉)。此時關節資訊在
      **權重混合**裡:關節落在「子骨近端邊」,即子骨自有頂點中父骨影響最強處。
      → 用 `proximal_joint`(權重法):s = w_child² · w_parent 的頂點加權質心。

兩者皆確定性、純 CPU、無 ML;皆以藝術家親手放的骨世界位置為真值。
不變的界定:軸向精修 / 手感 = 美術(A 類);細節骨(dominant 頂點過少)如實排除。
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import weighted_deform_eval as wde  # noqa: E402


# Award 四角色 weighted mesh:(名稱, slot, 子 rig 根骨)。megawin 兩張獨立圖 → 兩 rig。
WEIGHTED_CHARACTERS = [
    ("OMG",  "OMG角色",       "1_OMG"),
    ("SUP",  "superwin_角色",  "2_SUP"),
    ("MEG1", "megawin角色1",   "3_MEG"),
    ("MEG2", "megawin角色2",   "3_MEG"),
]


def load_weighted_character(slot, award_path="assets/Award.json"):
    """回傳 (V, W, infl, scale, byname, world):
      V     Nx2 setup-pose 世界頂點
      W     list of {bone_name: weight}(每頂點)
      infl  set 影響此 mesh 的骨名
      scale mesh bbox 對角線(尺度正規化)
    """
    sk, bones, byname, order = wde.load_skeleton(award_path)
    atts = wde.get_skin_attachments(sk)
    world = wde.bone_world_transforms(bones, byname, order, {})
    att = next(iter(atts[slot].values()))
    pv, tris, hull, uvs, weighted = wde.parse_weighted(att)
    assert weighted, f"{slot} 非 weighted mesh"
    V = wde.skin_vertices(pv, world, order)
    W = [{order[bi]: w for (bi, bx, by, w) in e} for e in pv]
    infl = set(order[bi] for e in pv for (bi, bx, by, w) in e)
    scale = float(np.linalg.norm(V.max(0) - V.min(0)))
    return V, W, infl, scale, byname, world


def joints_of(infl, byname):
    """可推斷關節 = (child, parent) 皆在 infl 的父子對(排除原點根骨:它不控制頂點)。"""
    return [(c, byname[c]["parent"]) for c in infl if byname[c].get("parent") in infl]


def _wvec(W, bone):
    return np.array([w.get(bone, 0.0) for w in W], dtype=np.float64)


def proximal_joint(V, W, child, parent):
    """權重法 pivot:關節在子骨近端邊 = 子骨頂點中父骨影響最強處。
    s = w_child² · w_parent 的頂點加權質心(w_child² 使估計留在子件側=近端邊,
    ×w_parent 拉向父件相鄰緣=接合處)。"""
    wc = _wvec(W, child); wp = _wvec(W, parent)
    s = wc * wc * wp
    return (V * s[:, None]).sum(0) / s.sum() if s.sum() > 0 else V.mean(0)


def child_part_centroid(V, W, child):
    """baseline:子骨 dominant-weight 頂點質心(權重法要顯著贏過它)。"""
    dom = np.array([V[i] for i, w in enumerate(W)
                    if w and max(w, key=w.get) == child], dtype=np.float64)
    return dom.mean(0) if len(dom) else np.asarray(V).mean(0)


def eval_weighted_character(name, slot, root, award_path="assets/Award.json"):
    """回傳 (rows, meta)。rows: 每關節 proximal / baseline 誤差(px 與正規化 + GT/估計座標)。"""
    V, W, infl, scale, byname, world = load_weighted_character(slot, award_path)
    rows = []
    for c, p in joints_of(infl, byname):
        gt = np.array([world[c][4], world[c][5]], dtype=np.float64)
        est = proximal_joint(V, W, c, p)
        base = child_part_centroid(V, W, c)
        rows.append(dict(char=name, child=c, parent=p,
                         gt=gt, est=est,
                         err=float(np.linalg.norm(est - gt)), err_norm=float(np.linalg.norm(est - gt)) / scale,
                         base=float(np.linalg.norm(base - gt)), base_norm=float(np.linalg.norm(base - gt)) / scale))
    return rows, dict(scale=scale, V=V, njoints=len(rows))


if __name__ == "__main__":
    for name, slot, root in WEIGHTED_CHARACTERS:
        rows, meta = eval_weighted_character(name, slot, root)
        print(f"\n=== {name} ({slot}) scale={meta['scale']:.0f} joints={meta['njoints']} ===")
        for r in rows:
            flag = "" if r["err_norm"] < 0.10 else "  <-- hard (splayed limb)"
            print(f"  {r['child']:<9}<-{r['parent']:<9} "
                  f"proximal={r['err']:6.1f}px({r['err_norm']:.3f})  "
                  f"base={r['base']:6.1f}px({r['base_norm']:.3f}){flag}")
