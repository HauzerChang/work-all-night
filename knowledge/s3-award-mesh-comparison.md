# S3 端到端驗收 — PSD件 → 生成 mesh → 對照 Award 真實生產 mesh

> 2026-07-17。把 S3 mesh 生成器對「真實生產標的」head-to-head:不是合成 fixture、
> 不是自訂門檻,而是直接跟藝術家在生產 spine(`Award.json`)手做的 mesh 比。
> 工具:`tools/mesh_gen/compare_award_mesh.py`(+ `generate_mesh.generate_auto`)。

## 結論(高信心)

**生成器在藝術家頂點量級即達/超越藝術家的靜態輪廓保真,3 件全過。**
`python3 tools/mesh_gen/compare_award_mesh.py` → `overall_pass: true`(exit 0)。

| 件 | 藝術家 nv / IoU | 生成 nv / IoU | epsilon | 判定 |
|---|---|---|---|---|
| 機器人拆件/身體 | 98 / 0.9760 | **89 / 0.9858** | 0.004 | 更省頂點**且**更高 IoU(完勝) |
| 機器人拆件/光暈 | 78 / 0.9795 | 98 / 0.9832 | 0.002 | 達保真,+20 頂點 |
| 機器人拆件/左手 | 80 / 0.9681 | 84 / 0.9713 | 0.006 | 達保真,+4 頂點 |

拓樸全乾淨:centroid_in_mask=1.0、0 退化、0 孤兒、格式合規(hull-first / 索引在範圍)。

## 關鍵發現

1. **單一旋鈕(epsilon = Douglas-Peucker 容差)單調換「頂點↔覆蓋率」。**
   default `epsilon=0.008` 是**省頂點取向**:3 件 IoU 0.926/0.970/0.960 全**低於**藝術家基準,
   且留 1–2 個孤兒頂點(AC2c fail)。降 epsilon(細化 hull 邊界取樣)→ IoU 單調上升、孤兒歸零。
   epsilon 掃描(左手 / 身體 / 光暈):
   ```
   0.008 → IoU 0.960 / 0.970 / 0.926 (＜藝術家, 有孤兒)
   0.004 → IoU 0.982 / 0.986 / 0.962
   0.002 → IoU 0.991 / 0.993 / 0.983 (光暈在此才過)
   ```
2. **IoU 由 hull(邊界)取樣密度決定**,與 S3 窗簾結論一致(strip 是 rows,Delaunay 是 epsilon)。
   內部點(Canny+格點)幾乎不影響覆蓋率,只影響變形時的內部細分。
3. **這 3 件走 v1(Delaunay)不是 v2(strip)**:光暈/身體/左手是團塊狀(非高長寬比 row-convex),
   `mode=auto` 正確回退 v1。v2 strip 適用窗簾類長條;v1 適用團塊 —— **auto 路由已能分流**。
4. 新增 `generate_mesh.generate_auto(path, target_iou, vertex_budget)`:降序掃 epsilon,
   回「最省頂點且達標」的 mesh(達不到則回最高 IoU 者)。把「調參達藝術家保真」自動化。

## 閘可信度(負對照內建)

- **鑑別力**:default 粗 epsilon(0.008)3 件全 `iou_ge_artist=false` → 閘不是自動放行;
  只有 auto-tune 後才過 → pass 有意義。
- 量測法一致:生成 mesh 與藝術家 mesh **用同一 `artist_iou`/`evaluate` 三角填滿法**在同一
  atlas 切件遮罩上量 → 公平對照(消除量測法差異)。
- atlas 切件已於前一里程碑用 PSD 外部真值驗為同素材(alpha-IoU 0.92–0.99,含 CW derotate 校正)。

## ⚠️ 範圍與誠實(重要)

- **本閘只驗「靜態輪廓保真 + 拓樸品質 + 頂點預算」的端到端。**
- 藝術家這 3 件是 **weighted mesh(靠骨骼權重變形,Award 中無 deform timeline)**;
  我們生成的是 **unweighted**。故**不宣稱變形手感/權重等價** —— 那需要 BBW 權重(S3 後續子目標,未做),
  且這 3 件無真實逐頂點位移場可轉移(不同於 main_draw 窗簾有 deform timeline)。
- 亦即:**「PSD → 件 → 靜態 mesh 幾何」對真實生產標的已通;「加權變形」是下一個未攻子目標。**

## 端到端鏈條(現況)

```
真實 PSD(robot_parts) ──psd_slice──> 件PNG ─(=)─ Award atlas 切件(alpha-IoU 0.92–0.99)
      └─────────────────── S4 已驗(無損切圖 + 命名慣例) ───────────────────┘
Award atlas 切件 ──generate_auto(v1)──> unweighted mesh ──對照──> 藝術家 weighted mesh
      └────────── S3 本次驗(靜態輪廓達/超藝術家,拓樸乾淨) ──────────┘
缺口:unweighted → weighted(BBW 權重)= 下一子目標。
```

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py                 # 3 件對藝術家基準, overall_pass
python3 tools/mesh_gen/compare_award_mesh.py --target-iou 0.99   # 提高門檻(會用更多頂點)
```
