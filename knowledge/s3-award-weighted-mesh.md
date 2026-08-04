# S3 端到端驗收:PSD件 → generate_mesh_v2 → 對照 Award 真實「加權」生產 mesh

- **結論**:S3 mesh 生成器**推廣通過**到 Award 生產 spine 的 3 件 **weighted mesh**
  (`機器人拆件/光暈`、`/身體`、`/左手`)。3 件在**靜態閘**(覆蓋率 / 頂點預算 / setup 拓樸)
  全 `overall_pass`,負對照抓到(38 self-int)。這是 S3 首次對「加權 + 低長寬比(Delaunay 路徑)
  + 真實生產」mesh 的驗收——先前 4 件全是 unweighted 窗簾/影子(strip 路徑)。
- **信心**:高。對真實生產標的、有藝術家 mesh 真值、評估器經 self-check + 負對照校驗。
- **階段**:第 2 階段 / S3+S4 端到端(里程碑:合成→真實 unweighted→**真實 weighted 生產件**)。
- **工具**:`tools/mesh_gen/validate_psd_to_award_mesh.py`(可重現)。

## 為何是「靜態」閘(誠實,不捏造 deform)

這 3 件在 Award **無 deform timeline**(見 `s4-psd-to-spine-real.md`:靠骨骼權重變形,
非逐頂點 deform)。剛體/仿射的骨骼變換不會使拓樸自交,故套用 `transfer_deform_check`
沒有真實位移場可轉移——不硬造 deform 閘(記取 stress_field miscalibration 教訓)。
有意義的閘因此是:① 覆蓋率 IoU vs 藝術家 mesh ② 頂點預算 vs 藝術家 ③ setup 拓樸有效性。

## 結果(2026-08-04)

| 件 | 藝術家 nv/hull | self-IoU(自校驗) | 生成 nv/hull | eps/輪 | 生成 IoU | 預算(≤1.3×) | 靜態 |
|---|---|---|---|---|---|---|---|
| 光暈 | 78 / 78(全邊界) | 0.9795 | 60 / 21 | 0.005 / 2 | **0.9629** | 60≤101 ✓ | 0 si/0 deg |
| 身體 | 98 / 40 | 0.9760 | 61 / 21 | 預設 / 1 | **0.9680** | 61≤127 ✓ | 0 si/0 deg |
| 左手 | 80 / 42 | 0.9681 | 48 / 18 | 預設 / 1 | **0.9602** | 48≤104 ✓ | 0 si/0 deg |

- 覆蓋率門檻 = 藝術家 self-IoU − 0.02(對齊藝術家自身覆蓋率,不用武斷 0.95;沿用
  `validate_against_real` 校正)。3 件生成 mesh 覆蓋率均達標,且頂點數比藝術家**更精簡**。
- 端到端 PSD sanity:對 PSD 切件跑同一生成器,IoU(身體 0.966 / 左手 0.964 / 光暈 0.933)
  ≈ atlas 裁切件 → **PSD 切件與 atlas 貼圖餵給 S3 結果一致**,PSD→件→mesh 閉環。

## 兩個可重用發現

### ① Spine JSON 的 mesh `uvs` 是 **region-local 0..1**(非 atlas 頁面座標)
直接 `uv*[Wc,Hc]` 把藝術家三角形填到「atlas_crop 上正裁切件」尺寸的畫布,
對 3 件 self-IoU = **0.98 / 0.98 / 0.97**(orient 全 `u,v`,無需翻轉)。這**同時驗證兩件事**:
(a) uvs 是 region-local;(b) `atlas_crop` 對**旋轉件**(光暈/身體 rotate=true)的 CW derotate
方向正確——藝術家 mesh 與 derotate 後貼圖完全同幀。是 CW-bug 修正後的又一外部佐證。
> 自校驗價值:初版誤把 uvs 當頁面座標光柵化 → self-IoU 0.0 → self-check 立即抓到座標假設錯。

### ② 覆蓋率 IoU 由「邊界取樣密度(epsilon/hull)」決定,與內部點數無關
`generate_mesh` 的 `epsilon_frac` 掃描(光暈):

| eps | 0.008(預設) | 0.005 | 0.003 | 0.002 | 0.0015 | 0.001 |
|---|---|---|---|---|---|---|
| hull | 14 | 21 | 32 | 38 | 48 | 58 |
| IoU | 0.929 | 0.963 | 0.978 | 0.983 | 0.988 | 0.992 |

`max_interior` 40→60 對 IoU 幾乎無影響(只加內部點)。**與 strip 模式「IoU 由 rows 決定、
cols 不影響」是同一規律**。預設 eps=0.008 對簡單近凸件(身體/左手)夠;但對**軟/細邊界**
(光暈:發光環,藝術家用 78 全邊界點細描)過度簡化 → 需更細 eps 才達基準。

## 對工具的改動(向後相容)

- `generate_mesh_v2.generate(..., epsilon_frac=None, max_interior=None)`:僅在退回 v1(Delaunay)
  時傳入;None → v1 預設 → **strip 與 4 mesh 既有結果不受影響**(已回歸驗證 4 mesh 全 PASS)。
- 驗證器內建**有界自我迭代**(RULES 自我驗證迴圈,≤5 輪):覆蓋率未達基準時,依
  `[預設,0.005,0.003,0.002,0.0015]` 加密邊界取樣,達標且在預算內即停(光暈 2 輪達標)。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_award_mesh.py     # 3 件 overall_pass + 負對照 → exit 0
```

## 下一步

- 把「件→Spine attachment」慣例(`PSD名/圖層名`、mesh vs region 分配、+2px padding、
  atlas 0.70 縮放、region-local uv、軟邊界需細 eps)固化成 SkelToJson 組裝工具(候選 #2)。
- 加權 mesh 的**權重生成(BBW)**尚未做——本次只驗拓樸/覆蓋,骨綁與權重是後續(S5 交界)。
