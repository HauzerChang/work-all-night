"""畫出兩個 rig 的 contact-seam pivot 推斷 vs 藝術家真值(視覺驗證)。
輸出 figures/s5_pivot_multirig.png。無頭環境 (Agg)。"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
import infer_pivots as ip  # noqa: E402

# ASCII 標籤(DejaVu 無 CJK 字型,避免圖上出現方框)
LABEL = {
    "機器人拆件/頭": "head", "機器人拆件/左手": "l-hand", "機器人拆件/右手": "r-hand",
    "機器人拆件/身體": "body", "機器人拆件/光暈": "glow",
    "image/body": "body", "image/face": "face", "image/hand": "hand",
    "image/hand2": "hand2", "image/tail": "tail", "image/bell": "bell",
}


def draw_rig(ax, name, loader):
    parts, truth, tree, fid = loader(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    # 部件輪廓
    for slot, poly in parts.items():
        p = np.vstack([poly, poly[:1]])
        is_parent = slot in set(tree.values())
        ax.plot(p[:, 0], p[:, 1], "-", lw=1.4 if is_parent else 0.9,
                color="#333" if is_parent else "#9aa",
                alpha=0.9 if is_parent else 0.6)
    # pivot:真值 o、推斷 x、連線
    for c in tree:
        t, j = truth[c], inf[c]
        ax.plot([t[0], j[0]], [t[1], j[1]], "-", color="#e06", lw=0.8, alpha=0.6)
        ax.plot(*t, "o", ms=9, mfc="none", mec="#1a7", mew=2.0)
        ax.plot(*j, "x", ms=9, color="#e06", mew=2.2)
        e = np.linalg.norm(j - t)
        ax.annotate(f"{LABEL.get(c, c)}\n{e:.0f}px", j, textcoords="offset points",
                    xytext=(6, 6), fontsize=7, color="#c04")
    ax.set_title(name, fontsize=11)
    ax.set_aspect("equal"); ax.grid(True, alpha=0.2)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    draw_rig(axes[0], "Award robot rig (mesh+region)", ip.load_award_robot)
    draw_rig(axes[1], "main_draw cat rig (all region)", ip.load_main_draw_cat)
    # 圖例
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="o", mfc="none", mec="#1a7", mew=2, ls="", label="artist truth pivot"),
        Line2D([], [], marker="x", color="#e06", mew=2, ls="", label="contact-seam inferred"),
        Line2D([], [], color="#333", lw=1.4, label="parent part"),
        Line2D([], [], color="#9aa", lw=0.9, label="child part"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=9, frameon=False)
    fig.suptitle("S5 contact-seam pivot inference vs artist truth on 2 rigs "
                 "(all joints < 10% rig scale)", fontsize=12)
    fig.tight_layout(rect=[0, 0.05, 1, 0.96])
    out = os.path.join("figures", "s5_pivot_multirig.png")
    os.makedirs("figures", exist_ok=True)
    fig.savefig(out, dpi=110)
    print("saved", out)


if __name__ == "__main__":
    main()
