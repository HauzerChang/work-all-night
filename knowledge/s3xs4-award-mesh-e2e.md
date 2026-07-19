# S3×S4 端到端 — 真實 PSD 件 → 生成 mesh → 對照 Award 生產 mesh

- **結論**:把「PSD 件 → S3 `generate_mesh_v2` → 靜態覆蓋/頂點預算閘」對 `robot_parts.psd` 中
  在 Award 為 mesh 的 3 件(光暈/身體/左手)**端到端跑通並全 PASS**。生成 mesh 輪廓覆蓋
  0.933/0.966/0.964(≥0.90 絕對閘),頂點數 35/60/59 = 藝術家 78/98/80 的 **45%/61%/74%**
  —— 生成件在同等或更緊的輪廓覆蓋下**更省頂點**。工具 `tools/mesh_gen/award_mesh_compare.py`。
- **信心**:高(真值=原始 PSD 件 alpha,無縮放無旋轉;負對照確認閘有鑑別力)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:S3 從 main_draw 窗簾/陰影 → 真實生產機器人件)。

## 可信對照量(2 個)+ 為何不用第 3 個

對照 Award 真實 mesh,只有兩個量**可信**:
1. **gen 靜態輪廓覆蓋**(vs 件 alpha,絕對閘 0.90;基準來自 main_draw 藝術家 mesh ~0.918)。
2. **頂點預算**(gen verts vs 藝術家 verts,純計數,無歧義)。

| 件 | gen 模式 | gen verts | gen tris | gen IoU | 藝術家 verts | verts 比 |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 | 49 | 0.933 | 78(hull78 純環) | 0.45 |
| 身體 | delaunay-v1 | 60 | 97 | 0.966 | 98 | 0.61 |
| 左手 | delaunay-v1 | 59 | 97 | 0.964 | 80 | 0.74 |

## 三個關鍵發現

1. **這 3 件走 v1 Delaunay(散點),不是 v2 strip** —— aspect 全 <1.2(0.97/1.12/0.84),
   `generate_mesh_v2` auto 模式回退 v1。**strip 適合窗簾/陰影(高瘦、單向拉伸)、v1 適合肢體/光暈
   (blob)** → 兩拓樸各有適用域,auto 的 aspect+row-convex 判別把它們分對了。

2. **regime 不同:Award 這 3 件是 weighted mesh 且無 deform timeline** ——
   靠骨骼/權重變形,不是逐頂點 deform。故 S3 的「真實位移場 deform 閘」在此**不適用**;
   正確的閘 = **靜態覆蓋 + 拓樸健全 + 頂點預算**。這補上了 S3 的第二個 regime
   (先前只驗過 main_draw 的逐頂點 deform 窗簾/陰影)。

3. **⚠️ 第 4 次評估器校準教訓 — 藝術家 mesh 覆蓋率不可用 atlas uvs 對齊(rotate:true 失真)**:
   想算「藝術家 mesh 對件的覆蓋」當對照基準,把藝術家 mesh 的 uvs 正規化到 bbox 再對件擺放。
   - **rotate:false(左手)可信**:自校準 8 二面體取最佳 → IoU 0.974,與 gen 0.964 幾乎同覆蓋
     (gen 用 74% 頂點做到)—— 這是唯一一組 honest 的 apples-to-apples。
   - **rotate:true(身體/光暈)不可信**:身體卡在 0.64,overlay 見藝術家 mesh(綠)相對真值
     (紅)**旋轉/偏斜**(uv 空間受 atlas 90° 旋轉 + page 長寬比糾纏,剛體 dihedral 無法對齊;
     uv bbox aspect 1.239 ≠ 件 1.121)。**故此值降為 informational + reliable 旗標,不當 pass/fail 閘。**
   - 教訓系列(第 4 次):`stress_field` miscalib → composite 透明白底 → atlas derotate CCW→CW →
     **本次 uv-對齊受 atlas 旋轉污染**。共同根因:**凡涉及 atlas 幾何(旋轉/縮放/page)就先用外部真值
     (PSD 件、原始 alpha)校驗,別信 atlas 內部自洽。**

## 評估器可信度(負對照)

- 正對照:身體 gen IoU 0.966。
- 負對照 A(mesh 向心縮 15%):0.709(<0.90,抓到)。
- 負對照 B(mesh 平移 +25px):0.744(<0.90,抓到)。
→ 覆蓋閘有鑑別力,非恆真。

## 可重現

```
python3 tools/mesh_gen/award_mesh_compare.py            # 3 件全 PASS, exit 0
python3 tools/mesh_gen/award_mesh_compare.py --dump /tmp/award_cmp   # 另存件 alpha + gen mesh
```

## 下一步

- **切圖→Spine JSON 組裝(SkelToJson)**:已握有真值慣例(`機器人拆件/<圖層名>`、size+2px、
  mesh/region 分配、v1/v2 拓樸選擇),可把「PSD 件 → Spine mesh attachment」固化成寫出工具,
  端到端產出可載入 Spine 的 JSON(unweighted mesh 版;weighted 需 S5 骨架/權重)。
- weighted mesh + 骨綁(S5)才能重現 Award 這 3 件的實際變形;目前 S3 產 unweighted,
  變形靠逐頂點 deform(適合 main_draw 窗簾 regime)。兩 regime 的橋接留待 S5。
