# S3 端到端驗收 — 件→生成 mesh 對照 Award 真實生產 mesh

- **結論**:把 S3 生成器接到**真實生產 mesh 真值**(Award spine 的機器人 3 件 mesh:光暈/身體/左手),
  端到端「atlas 切件 alpha → `generate_mesh_v2(auto)` → 對照藝術家 mesh」**3 件全 `overall_pass`**。
  這是 S3 第一次對「藝術家手做 mesh 的真值」驗收(先前 4-mesh 全是窗簾/陰影 strip;這 3 件是 blob)。
- **信心**:高(真值來自生產 spine `Award.json`;評估器先以藝術家自身 mesh 做可信度先驗;純 CPU 可重現)。
- **階段**:第 2 階段 / S3 × S4 串接(端到端里程碑)。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`。

## 結果(coverage IoU vs 藝術家真值 / 頂點 / 靜置拓樸)

| 件 | 生成 mode | 生成 nv | 生成 IoU | 藝術家 nv | 藝術家 IoU | epsilon(收斂) | overall |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 57 | 0.9504 | 78 | 0.9795 | 0.006(iter 2) | ✅ |
| 身體 | delaunay-v1 | 61 | 0.9680 | 98 | 0.9760 | 0.008(iter 1) | ✅ |
| 左手 | delaunay-v1 | 48 | 0.9602 | 80 | 0.9681 | 0.008(iter 1) | ✅ |

覆蓋率門檻 = 藝術家基準 − margin(0.03)。靜置拓樸(self-int / degenerate)生成與藝術家皆 0。

## 關鍵發現

1. **auto 對 blob 正確回退 v1 Delaunay**:這 3 件長寬比 <1.2、非 row-convex(光暈近方形、身體/左手矮胖),
   `generate_mesh_v2(auto)` 全數走 Delaunay 路徑 —— strip 只適合窗簾式高瘦件。**這是 v1/Delaunay 路徑
   第一次對真實生產 mesh 真值驗收通過**(補上 strip 之外的另一半)。

2. **Delaunay 的覆蓋率旋鈕 = hull 點密度(`epsilon_frac`),與 strip 的 `rows` 同理。**
   epsilon 掃描(光暈,藝術家基準 0.9795):

   | epsilon | hull | nv | IoU |
   |---|---|---|---|
   | 0.008(舊預設) | 14 | 54 | 0.9292 |
   | 0.006 | 22 | 57 | 0.9504 |
   | 0.004 | 22 | 61 | 0.9656 |
   | 0.002 | 38 | 73 | 0.9832 |
   | 0.001 | 58 | 92 | 0.9924 |

   → **預設 `epsilon_frac=0.008` 對「大面積、軟羽化邊」的 blob(如光暈)欠取樣**(approxPolyDP
   把圓潤外框砍成 14 點,覆蓋率掉到 0.929)。身體/左手邊界較銳,0.008 就夠。

3. **確定性覆蓋率自動收斂(無隨機/無學習)**:`compare_award_mesh.gen_with_coverage()` 用 epsilon 階梯
   `[0.008,0.006,0.004,0.003,0.002]` 由粗到細,取「第一個過覆蓋率門檻且仍在頂點預算(64)內」者。
   光暈 2 iter 收斂(eps 0.006、nv 57)。符合 RULES 的「自我驗證迴圈、迭代預算內自動修正」。

4. **效率**:生成 mesh 以藝術家 ~60–75% 的頂點數(57/78、61/98、48/80)達到覆蓋率基準。
   藝術家用純 hull 點(光暈 78 hull/0 內部)換取邊界擬合度;生成器用較少點 + 內部格點達同等覆蓋。

5. **評估器可信度先驗**:同一組閘先量藝術家自己的 3 件 mesh → 靜置 self-intersection 全 0
   (`artist_topology_all_clean=True`)→ 閘不誤殺真值,對生成 mesh 的判定可信。

## ⚠️ 範圍誠實聲明:deform 閘在此**不適用**

這 3 件在 Award **無 deform timeline**(見 `s4-psd-to-spine-real.md`:靠骨骼/權重變形,
非逐頂點 deform)→ 沒有「真實位移場」可轉移,故**不套** `transfer_deform_check`。
本次驗收是**覆蓋率 + 靜置拓樸**對真值,deform 穩健性結論仍以 strip/rows 研究
(`s3-four-mesh-generalization.md`)為準。要對 blob 做 deform 閘,需未來拿到「有 deform timeline
的 blob mesh」或設計 weight-based deform 的閘(待辦)。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py            # 3 件 all_pass, exit 0
# 單件 / 調參:
python3 tools/mesh_gen/compare_award_mesh.py --pieces '機器人拆件/光暈' --iou-margin 0.03 --budget 64
```

## 下一步候選

- 把「件→Spine mesh attachment」慣例(`PSD名/圖層名` slot、size+2px、mesh vs region 分配、
  atlas 0.70 縮放、Delaunay epsilon 自動收斂)固化成 **SkelToJson 組裝工具**(端到端產 Spine JSON)。
- 設計 **weight-based deform 閘**(補上 blob mesh 的變形穩健性驗收,目前缺口)。
- S2 補圖閘 / 骨架閘(純 CPU 可續)。
