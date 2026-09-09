#!/usr/bin/env python3
"""candidate G-4'' 圖:wobble shear 峰隨檔位遞增(阻尼振盪簽章保形)。

左:各檔位 wobble__{tier} 的 shearX(τ) 阻尼振盪波形(峰隨檔位放大、簽章不變、首尾 0)。
右:各檔位 shear 峰值長條(Super<Mega<Omg<Legend 嚴格遞增)= base 峰 × 宣告增益。
純以 build_animations 端到端取值(真實 robot 骨架 + slot_bigwin 先驗)。
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
import build_spine

TIERS = ["Super", "Mega", "Omg", "Legend"]
COLORS = {"Super": "#7aa6c2", "Mega": "#4f8fb0", "Omg": "#d98c3f", "Legend": "#c0392b"}
PSD = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "robot_parts.psd")


def main():
    out = "/tmp/fig_wt_skel"
    build_spine.build(PSD, out, genre="slot_bigwin", animate=False)
    skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    sb = analyze(PSD, "slot_bigwin")["3_motion_storyboard"]
    gains = TV.gains_for("slot_bigwin")
    base = G.build_animations(skel, sb)
    anims = G.build_animations(skel, sb, tier_gains=gains)

    # 取「特效」件(峰最大的 sheared bone)做波形示範
    def peak_bone(an):
        best, bestv = None, -1
        for bn, ch in an.get("bones", {}).items():
            if "shear" in ch:
                v = max(abs(f["x"]) for f in ch["shear"])
                if v > bestv:
                    best, bestv = bn, v
        return best

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.2))

    bn = peak_bone(anims["wobble__Legend"])
    for t in TIERS:
        ch = anims["wobble__{}".format(t)]["bones"][bn]["shear"]
        xs = [f["time"] for f in ch]; ys = [f["x"] for f in ch]
        axL.plot(xs, ys, "-o", ms=4, lw=1.8, color=COLORS[t],
                 label="{} (peak {:.1f}°)".format(t, max(abs(y) for y in ys)))
    axL.axhline(0, color="#888", lw=0.8)
    axL.set_title("wobble shearX(τ) per tier — bone {}\n阻尼振盪簽章保形,峰隨檔位放大,首尾 identity".format(bn))
    axL.set_xlabel("time (s)"); axL.set_ylabel("shearX (deg)")
    axL.legend(fontsize=8, loc="upper right"); axL.grid(alpha=0.3)

    base_peak = max(abs(f["x"]) for f in base["wobble"]["bones"][bn]["shear"])
    peaks = [max(abs(f["x"]) for f in anims["wobble__{}".format(t)]["bones"][bn]["shear"]) for t in TIERS]
    bars = axR.bar(TIERS, peaks, color=[COLORS[t] for t in TIERS], edgecolor="#333")
    for b, p, t in zip(bars, peaks, TIERS):
        axR.text(b.get_x() + b.get_width() / 2, p + 0.5,
                 "{:.1f}°\n×{}".format(p, gains[t]), ha="center", fontsize=8)
    axR.set_title("shear peak Super<Mega<Omg<Legend (strictly ↑)\n= base {:.0f}° × declared gain".format(base_peak))
    axR.set_ylabel("|shearX| peak (deg)"); axR.grid(axis="y", alpha=0.3)
    axR.set_ylim(0, max(peaks) * 1.25)

    fig.suptitle("candidate G-4'': wobble shear 峰隨檔位遞增(shear = 與 (J) scale/rotate 正交的第三放大軸)",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    dst = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge", "figures", "s1_wobble_tier.png")
    fig.savefig(dst, dpi=110)
    print("saved", os.path.normpath(dst), "| peaks", [round(p, 2) for p in peaks])


if __name__ == "__main__":
    main()
