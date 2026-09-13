# skill 化完成度快照 (READINESS)

> 由 `python3 tools/check_readiness.py` 產出。真相以指令即時輸出為準;本檔為人讀快照,里程碑時更新。
> 產生於 2026-09-13 run(S1 candidate (G-4'''''):**squash 接檔位差異化 — 體積守恆耦合放大** —— 補 G-4'''' 的 honest boundary(squash **不在** `MAIN_SHOW_CATS`,因逐軸 `_amp_scale` 放大 scaleX>1 卻把 scaleY<1 當樓地板保留 → 破壞體積守恆)。讓斜拉果凍**擠壓**(shear + 耦合非均勻 scale)幅度隨檔位嚴格遞增而 `scaleX·scaleY≡1` 恆保持。**crux=耦合放大**:改用 `_amp_scale_coupled`(以 scaleX 復原擠壓量 q、線性放大 q'=g·q、重建 scaleX'=1+q'、scaleY'=1/scaleX')→ 守恆重參數化;shear 同 (G-4'') 對 0 對稱放大 → **雙通道一起放大**(擠壓峰 [0.16,0.216,0.272,0.336]、shear 峰 [16,21.6,27.2,33.6]°)。`amplify_bone_tl` 的 `g==1.0` 零變換捷徑保 **Super==base 逐位元**(避開耦合重建 4-dec 漂移)。squash 併入 `MAIN_SHOW_CATS` + 新增 `COUPLED_SCALE_CATS={"squash"}`。`spine-anim-forge` 新增 cap `squash_tier_amplitude` L2(pipeline)→ 區塊**仍 HOLD**。`validate_squash_tier.py` 6AC PASS(ST2 crux 雙通道峰嚴格遞增且 Super==base/ST3 crux 每檔位每極值體積守恆 |積-1|≤4.6e-5+非均勻+阻尼遞減/ST5 shear 隔離/ST6b **耦合必要性守衛** naive volErr 0.152 vs coupled 5.6e-5 = **2710×** 證耦合必要且閘可信/ST6c 耦合隔離)。端到端 `--tier-variants --shear-pivot` 直出各檔位變體、round-trip overall_pass;副修 `tier_combo_count` K5c(count-隔離 proxy 由「峰數相同」改為直測「full vs gains-only 逐位元同」,對 squash 幅度放大穩健)。**關鍵發現:第三種檔位放大形態=耦合軸**(繼幅度軸 J、結構段數軸 J-2/G-4''' 之後);crux 是「coupled 地板 vs naive 破壞的數量級差」非「誤差 <5e-5」(4-dec 對耦合對有 ~1e-4 地板 → 閘容差用 TOL_VOL 0.02 抓守恆 vs 破壞)。可 skill 化 2 區塊 spine-mesh-doctor/spine-weighted-forge 不變。)
> (前次:(G-4'''')生成器產耦合 shear+非均勻 scale / (G-4''')wobble 段數隨檔位 / (G-4'')wobble shear 峰隨檔位 / (G-4')生成器產 shear 通道 / (G-4)件繞關節 pivot 一般仿射 / (J-2) combo 連擊數隨檔位 / (J)檔位幅度差異化 / (I) cascade 接先驗庫 / (H) combo/charge 接先驗庫。)

```
==============================================================================
可 skill 化(達門檻): spine-mesh-doctor, spine-weighted-forge
HOLD(防固化半成品): spine-asset-forge, spine-slicing, spine-target-analysis, spine-rig-pivot, spine-anim-forge
```
