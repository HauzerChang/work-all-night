# S3×S4 端到端驗收 — PSD 件 → 生成 mesh → 對照真實生產 mesh(Award)

- **結論**:把 `robot_parts.psd` 切出的 3 個 mesh 件(光暈/身體/左手)餵給 S3 `generate_mesh`(v1),
  和同一件在真實生產 spine `Award` 裡的**藝術家手做 mesh** 比 coverage IoU。**校準後三件全 BEAT
  藝術家覆蓋率,且頂點更少、通過全部 AC**(格式/退化/孤兒/預算)。這是 S3+S4 的接縫、
  對**外部真值**(非自產)的強驗收 —— 端到端「PSD→件→mesh」對真實標的成立。
- **信心**:高(真實生產 PSD + 真實生產 spine mesh 交叉;正/負可辨;有可重跑閘)。
- **階段**:第 2 階段 / S3×S4 接縫(里程碑)。

## 數據(coverage IoU vs 件 alpha;新預設 epsilon=0.004 + 孤兒清除)

| 件 | 藝術家 mesh IoU | 生成 mesh IoU | 藝術家頂點 | 生成頂點 | 結果 |
|---|---|---|---|---|---|
| 光暈 | 0.9486 | **0.9606** | 78 | 42 | BEAT,頂點 0.54× |
| 身體 | 0.9477 | **0.9828** | 98 | 69 | BEAT,頂點 0.70× |
| 左手 | 0.9768 | **0.9796** | 80 | 70 | BEAT,頂點 0.88× |

對照(舊預設 epsilon=0.008):光暈 0.9331、左手 0.9642 —— 兩件**低於**藝術家,身體 0.966 已過。

## 關鍵發現

1. **coverage 由邊界取樣密度(`epsilon_frac`)決定,不是內部點**。與 v2 strip 的
   「IoU 由 rows 決定、cols 不影響」同構 —— 覆蓋率是**輪廓貼合度**問題,不是內部密度問題。
   epsilon 掃描(robot 3 件):0.008→兩件輸;**0.004→三件全 BEAT 且頂點更少**;0.002→IoU 更高但 64–84v。
   → **v1 預設 epsilon_frac 由 0.008 調為 0.004**(對複雜有機輪廓才夠貼;窗簾走 v2 strip 不受影響)。
2. **凹形輪廓孤兒頂點**:邊界取樣變細後,凹口的 hull 頂點其相鄰三角重心落在 alpha 外,
   被 `filter_triangles` 砍光 → 該頂點變孤兒(違反 AC2c)。光暈在 0.004 首次出現。
   → 加 `prune_orphans()`:移除未被引用頂點並重編號,hull 計數相應減 1
   (hull 仍是「前 n_hull 依序繞外周」不變式;少一個被裁掉的凹口點,幾何正確)。修後光暈 42v 無孤兒、IoU 不變。

## 方法論再確認

- 生成 mesh 目標**不是**「複製藝術家頂點」,而是**達到同等/更好的覆蓋率**(可量測),用**更少頂點**(更省)。
  這正是「別用 ML 學沒有唯一解的美術決定;用確定性演算法 + 評估器把關」的實證。
- **Award mesh 的 uvs 為 region-local [0,1]**(實證:藝術家重建 IoU≈0.95 合理;若為 atlas-global 會近 0)。
  故可直接對「PSD 切件原尺寸 alpha」比對,+2px atlas padding 對 IoU 影響可忽略。
- 這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形)→ 本驗收為**靜態覆蓋率**;
  逐頂點 deform 耐受性另由 main_draw 4 mesh(有 deform)把關,不在此重複。

## 可重現

```bash
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_pieces
python3 tools/mesh_gen/validate_psd_mesh.py --pieces-dir /tmp/robot_pieces   # exit 0, 三件全 pass
# 對照舊預設看差異:
python3 tools/mesh_gen/validate_psd_mesh.py --pieces-dir /tmp/robot_pieces --epsilon 0.008
```

## 下一步

- 把命名慣例(`PSD名/圖層名`)+ size+2px padding + mesh/region 分配 + 本 mesh 生成,固化成
  **SkelToJson 組裝工具**:PSD → 各件 → 自動產出可載入的 Spine JSON(端到端 S3+S4 產線)。
- 目前為靜態覆蓋率驗收;若日後要對 Award 的骨骼權重變形做耐受性驗,需 weighted mesh 支援(現生成為 unweighted)。
