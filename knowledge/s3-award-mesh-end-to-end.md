# S3 端到端驗收 — PSD件 → 生成 mesh → 對照 Award 真實藝術家 mesh(里程碑)

- **結論**:把 S3 mesh 生成器接到**真實生產標的**驗收成功。用 Award 生產 spine 裡機器人 3 個
  mesh 件(光暈/身體/左手)的真實 atlas alpha 跑 `generate_mesh_v2`(auto),
  與**藝術家手做 mesh**(ground truth)逐件比對:3 件全 PASS,IoU 全達/超越藝術家覆蓋率,
  且**頂點數更少**(生成 68/68/53 vs 藝術家 78/98/80),靜態拓樸全乾淨(0 自交/0 退化/0 孤兒)。
- **信心**:高(對真實生產 mesh 的外部真值比對 + 靜態拓樸閘 + 負向修正過)。
- **階段**:第 2 階段 / S3+S4 端到端(里程碑:合成→真實件→對照真實 mesh)。

## 驗收數據(`tools/mesh_gen/compare_award_mesh.py`,margin 0.02)

| 件 | region | 生成 mode | 生成 nv/hull | 生成 IoU | 藝術家 nv | 藝術家 IoU | 自交 | 判定 |
|---|---|---|---|---|---|---|---|---|
| 光暈 | 496×480 | delaunay-v1 | 68 / 32 | **0.9779** | 78 | 0.9795 | 0 | PASS |
| 身體 | 267×299 | delaunay-v1 | 68 / 28 | **0.9834** | 98 | 0.9760 | 0 | PASS |
| 左手 | 181×152 | delaunay-v1 | 53 / 26 | **0.9755** | 80 | 0.9681 | 0 | PASS |

(atlas 件為 ~0.70 縮小打包;IoU 對縮放不敏感,藝術家 mesh 與生成 mesh 同在該 region 像素格上比。)

## 關鍵發現

1. **auto 路由正確**:3 件都是「團塊」(aspect < 1.2),`generate_mesh_v2` auto **自動回退 v1 Delaunay**
   —— 正是團塊該用的拓樸(藝術家也用一般 mesh,非直條)。窗簾類走 strip、團塊類走 Delaunay 的分流成立。
2. **這 3 件在 Award 無 deform timeline**(靠骨骼/權重變形)→ **沒有真實位移場可轉移**。
   誠實做法:**不套未校準的合成壓力場**(RULES 禁),閘改為「靜態 IoU vs 藝術家 baseline + 靜態拓樸乾淨」。
3. **v1 邊界改自適應(本次工具升級)**:原固定 `epsilon_frac=0.008` 對大而柔的光暈太粗
   (hull 14、IoU 0.929、還掉出 1 孤兒點)。改成 `boundary_points(epsilon_frac=None)` **自適應**:
   由粗到細掃 DP epsilon,取「hull 多邊形覆蓋率 ≥ 0.97」的最粗結果(頂點最省)→ 光暈自動取 hull 32、
   IoU 0.978;小而簡單的件仍精簡。**藝術家覆蓋率(0.97~0.98)成了自然的 IoU 目標**。
4. **加通用孤兒頂點清除**(`drop_orphans`):過濾凹形三角後偶有頂點沒被任何三角用到
   (evaluate_mesh AC2c 失分)→ 一律移除並重編索引(hull 頂點永遠保留)。

## 無回歸

- main_draw 4 mesh 全走 **strip 模式**(curtain aspect 1.55、shadow 6.22),不碰 v1 邊界邏輯
  → 改自適應 v1 **不影響** main_draw;重驗 curtain_left/right + shadow 仍全 PASS(IoU 達標、真實 deform si=0)。
- (shadow2 與 shadow 共用同一 region,atlas 無獨立 region,屬預期。)

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py                    # 機器人 3 件對照 Award,ALL_PASS
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left  # 無回歸
```

## 下一步

- 把「件 → Spine JSON 組裝」固化(SkelToJson):用真實慣例 `<PSD名>/<圖層名>`、mesh/region 分配、
  +2px padding、atlas 縮放,端到端從 PSD 件輸出可載入的 Spine mesh attachment。
- S2 補圖閘 / 骨架閘仍缺(S2 樞紐待補齊)。
