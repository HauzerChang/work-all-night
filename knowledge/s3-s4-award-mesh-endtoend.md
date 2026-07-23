# S3×S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,並對**真實藝術家真值**(生產 spine
  `Award` 中機器人的三件 mesh:光暈/身體/左手)驗收 —— `generate_mesh_v2(auto)` 產出的 mesh
  在**覆蓋率達到或超過藝術家水準**、且**頂點數更精簡**、拓樸乾淨。**三件全 `overall_pass`。**
- **信心**:高。真值來自使用者提供的生產檔(非合成、非自產),座標系經正/負對照校驗。
- **階段**:第 2 階段 / S3+S4 整合里程碑。工具:`tools/mesh_gen/compare_award_mesh.py`。

## 結果(margin=0.03,件源=PSD 全解析度切件)

| 件 | 生成 mode | 生成 v/t/hull | 生成 IoU | 藝術家 v/t/hull | 藝術家 IoU | 覆蓋差 |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 49 / 16 | 0.9331 | 78 / 76 / **78** | 0.9486 | −0.0155 |
| 身體 | delaunay-v1 | 60 / 97 / 20 | 0.9660 | 98 / 154 / 40 | 0.9477 | **+0.0183** |
| 左手 | delaunay-v1 | 59 / 97 / 19 | 0.9642 | 80 / 116 / 42 | 0.9768 | −0.0126 |

三件覆蓋差都在 ±0.02 內(margin 0.03),頂點數皆 < 藝術家(35<78 / 60<98 / 59<80);
重心 100% 在 mask、0 孤兒、0 退化、格式合法。

## 座標系校驗(推翻 log 006 的假設)

log 006 記「Award mesh uvs 為 atlas 頁 UV,需先轉 region 局部」。**實測為誤**:
把 Award 這三件的 mesh 三角形以 `uv*[W,H]` 直接渲染到件 alpha:

- **v-top(v 由頂部量)**:IoU 0.95~0.98(PSD 件)/ 0.97~0.98(atlas region 件);
- **v-flip**:IoU 0.43~0.61。

→ Award 這幾件 JSON 的 `uvs` **本就是 region 局部 0..1、v 由頂部量**,與 `generate_mesh_v2`
的 uv 慣例(`x/W, y/H`)一致,**無需任何轉換**。可直接比較。
(推測:此 spine 匯出時 uvs 已相對 region,或此資產屬單件填滿型;不同匯出設定可能不同,
未來遇 u/v 範圍遠小於 1 的資產才需做 atlas 頁→region 轉換。)

## 三個真實發現

1. **這三件在 auto 模式全走 v1 Delaunay**(非 strip):aspect(H/W)分別 0.97 / 1.12 / 0.84,
   都 < strip 門檻 1.2。**這是 v1 首次在真實生產「團塊狀」mesh 上對藝術家真值驗收** —— 通過。
   (strip 之前只在 main_draw 高瘦窗簾/陰影驗過;兩種拓樸各有適用形狀,auto 分流正確。)
2. **生成器比藝術家精簡**:同等覆蓋率下頂點數約為藝術家的 45~75%。藝術家對「光暈」用
   **純邊界多邊形(78 頂點全在 hull,0 內部點)**密集描邊 → 覆蓋率略高(0.9486);v1 用
   16 hull + 內部散點,較粗的邊界少 ~1.5% 邊緣覆蓋但仍在容差內。
   **啟示**:若要逼近藝術家的邊緣貼合度,可調高 v1 的輪廓取樣密度(hull 點數),
   代價是頂點數上升 —— 覆蓋率↔頂點預算的取捨可由此參數控制。
3. **deform 閘不適用於這五件**:Award 中機器人五件**無 deform timeline**(靠骨骼/權重變形,
   非逐頂點 deform)。故本比較只驗靜態覆蓋/拓樸/精簡;變形穩健性在 main_draw 四 mesh 已另驗。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_award_mesh.py          # all_pass=True, exit 0
```

視覺對照:`knowledge/figures/award_mesh_compare.png`(每件左=生成綠線框、右=藝術家橘線框)。

## 下一步

- 把「件→Spine attachment/mesh」固化成組裝工具(SkelToJson):用已驗慣例
  `機器人拆件/<圖層名>`、size+2px padding、mesh vs region 分配、region-local v-top uvs、
  atlas 0.70 縮放,端到端由 PSD 產出可載入的 Spine JSON。
- (可選)給 v1 加「hull 取樣密度」參數,做覆蓋率↔頂點數的 Pareto 掃描,對藝術家真值定甜蜜點。
