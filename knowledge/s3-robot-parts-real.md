# S3 端到端真實驗收:PSD→件→mesh 對照 Award 生產 mesh(機器人拆件)

- **結論**:S3 mesh 生成器對**真實生產標的**(Award big win 機器人的 3 個 mesh 件)端到端驗收
  **全數 PASS**(overall_pass=True)。這是「PSD→件→mesh」首次對「有藝術家真值可比」的真實 spine 驗證。
- **信心**:高。指標為覆蓋率 IoU(對真實 alpha)對照藝術家 mesh 自身覆蓋率 + 靜態拓樸有效性;
  工具 `tools/mesh_gen/validate_robot_parts.py`,標準指令一鍵重跑。
- **相關階段**:S3(mesh 生成器)× S4(PSD→spine 對應)串接;第 2 階段能力鍛鍊。

## 標的與真值

Award(機器人 big win 生產 spine)中,會 warp 的件做 mesh、剛體件用 region(見 `s4-psd-to-spine-real.md`)。
3 個 mesh 件即真值來源(slot == attachment name == `機器人拆件/<圖層名>`):

| 件 | atlas 區塊(0.70 縮小) | 藝術家 mesh | 覆蓋率基準 |
|---|---|---|---|
| 機器人拆件/光暈 | 496×480(Award2,rotate) | 78v(**全 hull**,76 tris) | 0.9795 |
| 機器人拆件/左手 | 181×152(Award,無 rotate) | 80v(hull42,116 tris) | 0.9681 |
| 機器人拆件/身體 | 267×299(Award2,rotate) | 98v(hull40,154 tris) | 0.9760 |

- **atlas 區塊 = 0.70× 邏輯尺寸**(offset=0、orig==size、無 trim)→ 藝術家 `uvs` 為 **region-local [0,1]**,
  可直接 `uvs*W, uvs*H` 還原到 region 像素空間,與生成 mesh 同座標系對照(log 006 的「atlas UV」提醒
  在此校驗為:uvs 本就 region-local,只是 region 是縮小頁)。

## 與 main_draw 4 mesh 的關鍵差異:這 3 件**無 deform**

12 支動畫掃描確認:光暈/左手/身體 **皆無 deform timeline**(靠骨骼驅動,不逐頂點變形)。因此:
- **真實位移場閘(`transfer_deform_check`)N/A** —— 沒有位移場可轉移,硬套會誤導。
- 改用**靜態拓樸有效性**閘(setup pose:0 自交 / 0 翻面 / 0 退化)+ 覆蓋率 IoU。
- 教訓:閘要**對得上標的的實際運動**;非變形件不該套變形件的閘。

## 生成器發現:預設 Douglas-Peucker eps 對「細緻/圓形」邊界欠取樣

3 件長寬比皆 < 1.2(近方形/圓)→ v2 auto 全部**回退 Delaunay v1**(非 strip)。首輪用預設
`eps=0.008` 時:

- 光暈 hull 僅 **14** 點 → 圓形邊界被欠取樣 → 覆蓋率 IoU **0.929 < 基準**(FAIL)。
- eps 掃描(光暈):0.008→IoU0.929 / 0.004→0.966 / 0.002→0.983(但 73v 超預算)/ 0.001→0.992(101v)。
  **愈細 eps → hull 愈密 → IoU 愈高,但頂點數上升**。

### 修正:adaptive 邊界取樣(opt-in,零回歸)

`generate_mesh_v2.generate(..., adaptive=True, budget=64)`:在 eps 階梯
`[0.008,0.006,0.004,0.003,0.002,0.0015,0.001]` 上取「頂點數仍 ≤ budget 的**最細** eps」。
- **預設 `adaptive=False`** → v1 default 與所有既有 caller(含 main_draw 4 mesh)行為完全不變。
- adaptive 結果:光暈 eps0.004/61v/IoU0.966、左手 eps0.003/61v/IoU0.988、身體 eps0.006/64v/IoU0.971 →
  **3 件全 PASS,全 ≤64 頂點,覆蓋率追平或超越藝術家**。
- 生成 mesh 頂點數皆**少於**藝術家(藝術家多的內部點是為 warp 控制;此件不變形,覆蓋率才是重點)。

## 回歸驗證(必做)

main_draw 4 mesh 以 `--gen v2` 全 `overall_pass=True`(curtain_left/right/shadow/shadow2,皆 strip 路徑,
不走新增的 adaptive 分支)→ 本次改動零回歸。shadow2 slot 共用 attachment `image/shadow`。

## 標準指令

```
python3 tools/mesh_gen/validate_robot_parts.py --tmp /tmp
# 全過 exit 0;每件回報 mode/eps/nv/hull、覆蓋率 IoU vs 藝術家、靜態拓樸、頂點預算。
```

## 待續

- Award.png 貼圖已在 assets → 可再做 texture 級(RGB)對照,不只 alpha 覆蓋率。
- 固化「件→Spine JSON」組裝(SkelToJson):把 `機器人拆件/<圖層名>`+size+2px padding+mesh/region 分配
  慣例寫成工具,端到端產出可載入的 Spine JSON。
