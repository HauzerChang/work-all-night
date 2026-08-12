# S3 端到端:PSD 生產件 → v2 mesh 對照 Award 真實 mesh(里程碑)

- **結論**:S3 `generate_mesh_v2` **端到端推廣到真實生產 PSD 件成功** —— 機器人拆件 3 個 mesh 件
  (光暈 / 身體 / 左手)自動生成的 mesh,靜態覆蓋率 + 拓樸 + 頂點經濟度**全對照 Award 生產 spine 通過**。
- **信心**:高(對真實生產標的、可機讀閘、含負向診斷與外部真值校準)。
- **階段**:第 2 階段(用工具鍛鍊四能力)/ S3 mesh。工具:`tools/mesh_gen/compare_award_mesh.py`。

## 驗收結果(atlas 抽件當 alpha 來源,epsilon=0.006 後)

| 件 | v2 頂點 | v2 IoU | 拓樸 | IoU 門檻(來源) | 藝術家頂點 | overall |
|---|---|---|---|---|---|---|
| 光暈 glow | 56 | 0.950 | pass | 0.879(artist) | 78 | ✅ |
| 身體 body | 64 | 0.971 | pass | 0.90(fallback) | 98 | ✅ |
| 左手 lefthand | 52 | 0.974 | pass | 0.970(artist) | 80 | ✅ |

`python3 tools/mesh_gen/compare_award_mesh.py` → `all_pass: true`(exit 0)。
**頂點經濟度全勝藝術家**(56/64/52 vs 78/98/80)於相當覆蓋率下。

## 關鍵發現 / 教訓

1. **Award 3 mesh 件是 weighted + 無 deform timeline**(骨骼驅動變形)→ 真實位移場 deform 閘
   (`transfer_deform_check`)對這些件 **N/A**(沒有 deform 場可轉移)。可套用的是「靜態覆蓋 + 拓樸」閘。
   ⇒ 生產實務:warp 件既可用 unweighted+deform(main_draw 窗簾),也可用 weighted+骨骼(Award 機器人),
   兩種變形機制;S3 目前產 unweighted,對「靜態拓樸/覆蓋」層面通用,骨骼權重(BBW)仍是 S3 未做部分。

2. **Award.json uvs 在「原始 atlas 座標系」,shipped PNG 為 ~0.70 repack** → 直接把 json uvs 用
   shipped page 尺寸 normalize **對不上** shipped atlas region 幾何(body: u_max·1780=1351 ≠ region col 1460)。
   ⇒ 疊藝術家 mesh 當基準時,用「uv-bbox → 抽出 region 影像 bbox」自校準(枚舉 8 個二面體方位取 IoU 高者);
   當自校準 IoU < 0.85(件的 uv-bbox 未填滿 region,如 body u∈[0,0.76])即判「基準不可信」,
   **退回 AC.md 絕對門檻 0.90**(誠實處理,不假裝有可信藝術家參照)。這延續 log 006「round-trip 自洽 ≠ 絕對正確,
   要外部真值」的紀律。

3. **atlas 抽件足以代表 PSD 件**:log 006 已證 PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 = 同素材;
   本閘用 atlas 抽件(能直接疊 Award uvs)做主來源,結論等價於「PSD 件」。

## 連帶修好的生成器兩處(v1,v2-auto 對 blobby 件會回退 v1)

- **孤兒頂點(AC2c)**:凹形輪廓(光暈星芒)`filter_triangles` 砍凹陷三角後,某邊界頂點失去全部三角 →
  孤兒(Spine 不接受)。加 `prune_orphans()`:濾三角後移除未被引用頂點並重編索引,保住 hull-first 不變式。
  修後光暈 orphans 1→0。
- **epsilon 預設 0.008→0.006**:0.008 對有細長突起的件(左手手指)過度簡化輪廓,漏覆蓋 ~1%。
  0.006 讓左手 IoU 0.960→0.974(勝藝術家 0.970),52 頂點仍遠低於預算 64。
  **回歸驗證乾淨**:main_draw 4 mesh v2 全 overall_pass(30v,deform 乾淨);Award 3 件全過。

## 標準指令

```
python3 tools/mesh_gen/compare_award_mesh.py          # 3 件端到端閘,exit 0=全過
```

## 待續

- **BBW 骨骼權重生成**(S3 缺塊):Award 機器人件用 weighted mesh,S3 目前只產 unweighted。
  要真正取代生產 weighted mesh 需加 bone binding + 權重(BBW),並配「骨骼驅動變形」閘。
- 把「件→Spine attachment」命名慣例(`<PSD檔名>/<圖層名>`、size+2px)固化成 SkelToJson 組裝工具。
