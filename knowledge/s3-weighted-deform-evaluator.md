# S3 — weighted-mesh 骨綁變形評估器(補上唯一未驗維度的「真值端」)

- **動機**:`s3-robot-mesh-vs-award.md` 誠實限制 —— Award 機器人 3 件(光暈/左手/身體)是
  **weighted mesh**,靠骨骼+權重(LBS)變形、**無 deform timeline**,故逐頂點 `deform_eval.py` 不適用。
  「靜態 IoU PASS」不代表「骨綁變形平滑度對等」。要量化這維度,必須真的把骨骼 pose 序列套上去
  (forward-kinematics + linear blend skinning),先把**真值端**(美術 mesh 在真實動畫下的變形)建起來。
- **工具**:`tools/mesh_gen/weighted_deform.py`(純 CPU,可重現)。
- **信心**:高 —— reproducer 通過兩條 Spine 不變量自我驗證(見 AC0)。
- **階段**:第 2 階段 / S3(里程碑:首個 weighted-mesh 骨綁變形量化閘)。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform.py     # 3 件 × AC0–AC4 全 PASS → exit 0
```

## 資料事實(從 `assets/Award.json` 實測)

- 7 個 weighted mesh;機器人 3 件的綁定骨與唯一驅動動畫:

  | 件 | nv / hull / tri | 綁定骨 | 每頂點骨數分布 |
  |---|---|---|---|
  | 光暈 | 78 / 78 / 76 | 4_LEG3–6 | 1:40, 2:31, 3:7 |
  | 左手 | 80 / 42 / 116 | 4_LEG5, 4_LEG9 | 1:41, 2:39 |
  | 身體 | 98 / 40 / 154 | 4_LEG3, 4_LEG7, 4_LEG8 | 1:38, 2:58, 3:2 |

- **唯一驅動這 3 件的動畫 = `Award_Legend_Loop`**(移動 4_LEG4/5/6/7/9;4_LEG2 為受動祖先)。
  其餘 11 支動畫都不動這些骨 → 機器人本體在多數動畫是靜止的,只有 Legend_Loop 有骨綁待機呼吸。
- 綁定骨鏈:`4_LEG7 → 4_LEG3 → 4_LEG2 → 4_LEG → root`;**全骨 `transform=normal`**(全繼承旋轉/縮放),
  故 FK 為單純仿射鏈合成(免處理 noRotation/noScale 特例)。

## reproducer 做了什麼(Spine 3.8 忠實重現)

1. **bone FK**:local 仿射 = `R(rotation)·S(scaleX,scaleY)` 平移到 (x,y);world = parent.world ∘ local。
   動畫 timeline:`rotate`(加角度)、`translate`(加位移,相對 setup local)、`scale`(乘);
   內插支援 **compact bezier**(`curve=cx1, c2=cy1, c3=cx2, c4=cy2`,缺鍵預設 0)、`stepped`、`linear`。
   bezier 以「給 x 二分解 u 再取 y」求值。
2. **LBS**:`worldV = Σ_j w_j·(boneWorld_j ⊗ bind_j)`(bind 為 setup 下相對該骨座標;CLAUDE.md 雷點 #6)。
3. **幾何閘**:重用 `deform_eval` 的 `signed_area`/`_seg_cross`/`tri_edges` → flips/degen/self_intersections。

## 五條可機讀 AC(3 件全 PASS)

- **AC0 reproducer 可信**(關鍵):每頂點 `Σw=1`(誤差 ≤1e-5)、動畫 t=0(首幀空 keyframe)
  逐頂點重合 setup pose(**0.0000px**)→ 證 FK+LBS 解析與合成無誤。
- **AC1** setup 幾何非退化(bbox diag 335~951px)。
- **AC2** 真實變形乾淨:Legend_Loop 逐幀(25 幀)**0 翻面 / 0 自交 / 0 退化**(美術真值本就乾淨)。
- **AC3** 變形非平凡:max 頂點位移 12~36px(占 diag **2.4%~10.8%**)—— 左手最靈活(10.8%)。
- **AC4** 負對照:把 t=0.5 相對 setup 位移放大 **30×** → 抓到大量翻面(2~26)+ 自交(23~270),證有鑑別力。

## 這給了什麼 / 還缺什麼(誠實界定)

- ✅ **建成了 weighted-mesh 變形品質的量化真值端**:任一 pose 下美術 mesh 的世界頂點 + 拓樸乾淨度可算。
- ✅ 附帶量化了「這些件實際變形多大」(AC3)—— 之後生成 mesh 要對照的是這個量級。
- ⏳ **尚缺(下一個 chunk)**:把**自產 mesh**(boundary-dense/strip)配上**權重(BBW 或啟發式骨距權重)**,
  用同一 driver anim 套 LBS,與美術 mesh 逐點比對「變形後表面差」與平滑度(如相鄰頂點位移梯度/曲率),
  才能回答原始問題「內部取樣密度不足是否真的犧牲變形平滑度」。真值端已就緒,可直接接。
- ⏳ 只驗這 3 件 + 1 driver anim(其餘動畫不動這些骨)。若要更廣,4 個角色 mesh
  (OMG/megawin1,2/superwin)也是 weighted,可套同工具(需查各自 driver anim)。
