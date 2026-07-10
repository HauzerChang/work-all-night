# S3×S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh

> 結論:**S4(psd_slice)→ S3(generate_mesh_v2)串成端到端,對真實生產標的(Award 機器人 3 件 mesh)
> 靜態拓樸+覆蓋驗收通過** —— 生成 mesh 以**更少頂點**達到**優於藝術家**的覆蓋率。
> 依據:`tools/mesh_gen/validate_psd_to_award.py`(2026-07-10)。信心:高(對藝術家真值直接量化)。
> 階段:第 2 階段(鍛鍊四能力)——把 S4 切圖 + S3 mesh 兩能力串起來對真實標的收斂。

## 標的與真值

`robot_parts.psd`(713×693,5 圖層,大 win 主角機器人)一對一對應真實 spine `Award` 的
slot `機器人拆件/<圖層名>`(見 `s4-psd-to-spine-real.md`)。其中 3 件會 warp → 藝術家做成 **mesh**:

| PSD 圖層 | Award slot | 藝術家 mesh(真值) | atlas |
|---|---|---|---|
| 光暈 | 機器人拆件/光暈 | 78v / hull 78(純輪廓 fan)/ 76 tri | rotate:true, ×0.70 |
| 身體 | 機器人拆件/身體 | 98v / hull 40 / 154 tri | rotate:true, ×0.70 |
| 左手 | 機器人拆件/左手 | 80v / hull 42 / 116 tri | rotate:false, ×0.70 |

剛體 2 件(右手/頭)為 region,不在 mesh 驗收範圍。藝術家 3 件 mesh 皆 **weighted**
(vertices 為 `[骨數,idx,bindX,bindY,w,...]` 變長格式)。

## 驗收方法(純 CPU,無需 Award.png)

1. **切件**:`psd_slice.py` 切出各件緊湊 PNG(bbox 裁切,+manifest)。
2. **生成**:`generate_mesh_v2.generate(png, mode="auto", coverage=0.98)`。3 件長寬比 <1.2 →
   走 Delaunay(非 strip);給 `coverage` 目標 → 觸發**評估器驅動自動精修**(見下)。
3. **對真值**:
   - **覆蓋 IoU**:生成 mesh 與藝術家 mesh **各自**以 uvs 光柵化(`uv*(W,H)`)覆蓋同一切件 alpha,
     比 IoU。藝術家為 baseline。
   - **頂點預算**:生成頂點數 ≤ 藝術家頂點數。
4. 另跑 `evaluate_mesh` 全閘(centroid-in-mask / 退化 / 孤兒 / 格式)確認高 IoU 非以壞幾何換來。

### 為何用 uvs 而非 vertices 比對(關鍵)

藝術家 mesh 是 weighted,`vertices` 不能直讀局部座標;`uvs` 每頂點一組,是**紋理座標**。
**經實測驗證**:即使 atlas region `rotate:true`(光暈/身體),直接 `uv*(W,H)` 映射切件像素,
藝術家 baseline IoU 仍達 0.948~0.977(合理、非亂碼)→ 證明 **Spine JSON 的 uvs 存於 art 邏輯
[0,1] 空間**,atlas 的 rotate/縮放只影響打包、不影響 uvs 邏輯座標。這個 baseline 合理性本身
就是「比對空間正確」的負對照式檢查。

## 結果(coverage 目標 0.98,margin 0)

| 件 | 生成 | 生成 IoU | 藝術家 IoU | 頂點(生成/藝術家) |
|---|---|---|---|---|
| 光暈 | eps=0.0015, 72v, hull45 | **0.9877** | 0.9486 | 72 / 78 ✅ |
| 身體 | eps=0.005, 67v, hull27 | **0.9802** | 0.9477 | 67 / 98 ✅ |
| 左手 | eps=0.003, 75v, hull26 | **0.9849** | 0.9768 | 75 / 80 ✅ |

**overall_pass=True**;3 件全以**更少頂點**達到**優於藝術家**的靜態覆蓋。
全數通過 `evaluate_mesh` 幾何全閘(centroid 1.0 / 0 退化 / 0 孤兒)。

## 關鍵發現

1. **覆蓋率單調受 hull 密度(epsilon / Douglas-Peucker)支配** —— 與 strip 模式「IoU 由 rows 決定」
   同構的定律。epsilon 掃描(光暈):
   `0.008→0.933(35v) · 0.005→0.961(44v) · 0.003→0.966(49v) · 0.002→0.980(64v) · 0.001→0.992(81v)`。
2. **評估器驅動自動精修**(新增於 `generate_mesh_v2._refine_delaunay`,對應 RULES 5 輪迭代預算):
   沿遞減 epsilon 排程取「首個覆蓋率達標且頂點 ≤ 預算」的 mesh(=達標中頂點最少者)。
   **不依賴藝術家真值**,是可上生產的自我品質閘。
3. **自我閘門檻的敏感度**:目標 0.97 → 2/3 達/超越藝術家(左手差 0.3pp,因其藝術家 mesh 特別緊 0.977);
   **目標 0.98 → 3/3 全超越**。實務上把生產自評門檻設 0.98 即可穩定匹配這批藝術家水準。
4. **這 3 件在 Award 無 deform timeline**(靠骨骼擺 pose)→ 本驗收為「靜態拓樸+覆蓋」;
   **deform 耐受閘仍以 main_draw 窗簾(有 deform)為準**(見 `s3-four-mesh-generalization.md`)。

## 局限 / 待辦

- 未做 **deform 耐受**對照(Award 這 3 件無 deform 真值);若日後拿到會 warp 且有 deform 的生產 mesh 可補。
- 覆蓋率是「面積 IoU」,未評估**邊界貼合的均勻度**(藝術家 78-hull 沿羽化邊更均勻);
  對 bone-driven warp 平滑度可能有別。屬主觀手感,留待實機/使用者。
- 尚未把生成 mesh **寫回 Spine JSON attachment**(SkelToJson 組裝仍是 STATE 候選 #2)。
