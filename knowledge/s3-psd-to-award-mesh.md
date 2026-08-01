# S3 端到端驗收 — PSD 件 → S3 mesh → 對照 Award 真實生產 mesh

- **結論**:整條「PSD → `psd_slice` 切件 → `generate_mesh`(S3)→ mesh」對**真實生產標的**
  (機器人 3 個 mesh 件:光暈 / 左手 / 身體)達成**覆蓋率 parity 且在藝術家頂點預算內**。
  這是 S3+S4 第一次對「有真值(Award 藝術家 mesh)」的端到端閉環驗收。
- **信心**:高(對真實生產 spine 的藝術家 mesh 逐件量化比對;正/負皆有;可一鍵重現)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑)。

## 標的(Award 機器人拆件,mesh 件)

| 件 | Award 藝術家 mesh | 生成 mesh (eps=0.002) | 覆蓋率 IoU(同 region 幀) |
|---|---|---|---|
| 光暈 | 78v / hull78 / 76t | 73v / hull38 / 106t | gen **0.9832** ≥ art 0.9795 ✅ |
| 左手 | 80v / hull42 / 116t | 67v / hull43 / 89t | gen **0.9913** ≥ art 0.9681 ✅ |
| 身體 | 98v / hull40 / 154t | 77v / hull37 / 115t | gen **0.9926** ≥ art 0.9760 ✅ |

- **右手 / 頭**在 Award 是 **region(剛體 + 旋轉)不是 mesh**,故不比(見 `s4-psd-to-spine-real.md`)。
- 生成 mesh 頂點數 **全少於藝術家**(73/67/77 ≤ 78/80/98)→ 更精簡仍達覆蓋率 parity。

## ★ 關鍵發現:覆蓋率的唯一槓桿 = 邊界取樣密度(epsilon)

v1 Delaunay 路徑(這 3 件 aspect<1.2,v2 auto 落回 Delaunay)的覆蓋率由
`epsilon_frac`(Douglas-Peucker 邊界簡化)單一決定。epsilon 掃描(atlas region 幀):

| eps | 光暈 IoU (art 0.9795) | 左手 IoU (art 0.9681) | 身體 IoU (art 0.9760) |
|---|---|---|---|
| 0.008(預設) | 0.9292 ✗ | 0.9602 ✗ | 0.9680 ✗ |
| 0.004 | 0.9656 ✗ | 0.9816 ✅ | 0.9858 ✅ |
| **0.002** | **0.9832 ✅** | **0.9913 ✅** | **0.9926 ✅** |
| 0.001 | 0.9924 | 0.9963 | 0.9946(頂點暴增) |

→ **eps=0.002 是甜蜜點**:3 件全達 parity,頂點仍在藝術家預算內。
這與先前 v2 strip「**IoU 由 rows(邊界密度)決定、cols 不影響**」是**同一原理的統一**:
不論 Delaunay 或 strip,覆蓋率保真度就是「邊界取樣多密」。

**為何預設 eps=0.008 不改**:0.008 是為 main_draw 窗簾(strip 模式)驗過的;
這些精緻生產 blob 件(aspect<1.2 走 Delaunay)需要更密邊界。未動全域預設以免回歸
(已重驗 `validate_against_real --gen v2` curtain_left 仍 overall_pass)。
**下一步候選:自適應 epsilon**(依 perimeter/面積或目標 IoU 自動收斂),消滅這個手調參數。

## deform 閘為何在此 N/A(重要,別誤判)

Award 這 5 件**無 deform timeline** → 靠骨骼/權重變形,非逐頂點 deform。
把 main_draw **curtain_left 的真實位移場**硬轉到這些 mesh 上:
- 直接套(絕對像素):左手 self_int=21(313px 位移套在 181px 寬的手上,≈2× 尺寸)→ 假性失敗。
- 尺度歸一(同 49% 相對拉伸):身體/左手 **clean**,光暈仍 self_int=3(圓形 blob 被窗簾式剪切,Delaunay 薄三角撐不住)。

兩者都**不是 Award 件的校準測試**:變形**型態**(窗簾剪切)對圓形光暈是外來的,尺度也需人工歸一。
正是 RULES 警告的 miscalibration 類(前有 stress_field、composite 白底、derotate 方向)。
**結論**:對無 deform 的資產,只判「靜態覆蓋率 parity + 頂點預算」;逐頂點 deform 耐受
留給**有真實 deform 場**的資產(main_draw 4 mesh,已驗)。光暈那個 self_int 順帶提示
**圓形 blob 用 Delaunay 有薄三角風險**,若未來要對光暈做強剪切變形,考慮 fan/放射狀拓樸。

## 可重現

```bash
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_pieces
python3 tools/mesh_gen/validate_psd_to_award_mesh.py            # eps=0.002 → overall_pass, EXIT 0
python3 tools/mesh_gen/validate_psd_to_award_mesh.py --epsilon 0.008   # 重現「預設太粗」失敗
```

腿 A(atlas region 幀)= 嚴謹數字(生成 mesh 與藝術家 uvs 同幀);
腿 B(真上游 PSD 幀)= 從真正 PSD 件直接生成也得 IoU 0.98–0.99(證明整條上游通)。
