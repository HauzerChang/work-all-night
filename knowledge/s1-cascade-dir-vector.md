# S1 (J-6) cascade 波方向一般化為任意角投影 — 把 J-5 的方向軸由 4 向離散補成連續

> candidate J-6 · 2026-10-02 run 001 · cap `cascade_dir_vector` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_vector.py`(5 AC 全 PASS)

## 承 (J-5):方向軸從「4 個具名」補成「連續」

(J-5) 把 cascade 跨件波的**相位來源**從件序換成空間,給方向軸 4 個**具名**取值:

| J-5 具名 | 排序鍵 | 類型 |
|---|---|---|
| `lr` / `rl` | `±x`(基數軸) | 投影(到 ±x 軸) |
| `co` / `oc` | `±hypot(x−cx, y−cy)`(距中心) | radial(非線性) |

(J-6) 把這**同一條方向軸由離散補成連續**:方向可給**角度(度)或向量 `(ux, uy)`**,
相位依件中心在該單位向量上的**投影** `k = x·ux + y·uy` 排序。相位值仍 `rank/(nvalid−1)∈[0,1]`,
只是 rank 的排序鍵換成任意方向的投影。

- `lr` == θ=0°(投影到 `(1,0)`,`k=x`)、`rl` == θ=180°(`k=−x`)→ **投影族的基數軸特例**(逐位元相容)。
- `co`/`oc` 是 **radial**(距中心,非線性),**不是**投影,保留為各自的特例 —— 任何單一投影都無法重現徑向序
  (投影是線性,徑向是 2D 距離)。

## crux:這**不是**第四條正交軸(honest distinction,勿誇大)

(J-5) 已把「方向 / 相位來源」立為跨件時序通道的**第三條正交軸**(結構 nrip × 幅度 span × 方向)。
**J-6 沒有新增第四條軸** —— 它只是把這**同一條方向軸**的**取值**由「4 個具名」擴成「連續角 + 任意向量」。

機制仍是 J-5 的「既有相位的重新指派(排列)」—— 同一組相位值 `{0, 1/(n−1), …, 1}` 被**排列**到不同件上;
J-6 唯一改的是**排序鍵**:從 `{基數軸 ±x, radial}` 擴成 `{任意投影角, radial}`。

**它的價值**:對角 / 垂直 / 任意角的波,J-5 的 4 向**表達不了**。例如垂直(90°,`k=y`)波在 robot fixture 上
產出件序 `[身體, 光暈, 左手, 右手, 頭]`(index `[3,0,4,1,2]`),這個波序在 J-5 的 4 向下**都做不出來**。

## 鑑別資產:robot fixture 的 x/y 非單調 → 垂直/對角序 ∉ 所有 J-5 序

robot 件序 `[光暈, 右手, 頭, 身體, 左手]`,座標(canvas center 356.5, 346.5):

| 件 | idx | x | y | radial |
|---|---|---|---|---|
| 光暈 | 0 | 359.0 | 341.5 | 5.6 |
| 右手 | 1 | 320.5 | 435.0 | 95.5 |
| 頭 | 2 | 361.0 | 443.5 | 97.1 |
| 身體 | 3 | 393.5 | 227.5 | 124.6 |
| 左手 | 4 | 557.5 | 408.5 | 210.3 |

各方向的波序(以件序 index 表示):

| 方向 | 波序(idx) | 說明 |
|---|---|---|
| `po`(件序) | `[0,1,2,3,4]` | 作者排版順序 |
| `lr`(x↑) | `[1,0,2,3,4]` | 基數軸 |
| `rl`(x↓) | `[4,3,2,0,1]` | |
| `co`(徑向↑) | `[0,1,2,3,4]` | 此 fixture 巧合==件序(J-5 已註) |
| `oc`(徑向↓) | `[4,3,2,1,0]` | |
| **90°(y↑,J-6)** | **`[3,0,4,1,2]`** | **∉ 以上任一** |
| **45°(對角,J-6)** | **`[3,0,1,2,4]`** | **∉ 以上任一** |

V5(a) 固化此鑑別:垂直 / 對角的**實測峰序** ∉ 全部 J-5 方向的件序集合 `{po, lr, rl, co, oc}`
→ 證任意角投影是**真‧新方向**,不是換個名字的具名方向。

## 自我驗證(AC-first,量化;`validate_cascade_dir_vector.py` 5 AC 全 PASS)

- **V1 present + backward-compat**:每個新方向(90°/270°/45°/135°/向量 (1,1)/(0,-1))皆產每個 cascade beat 且
  finite/有 bone;**投影族含具名** —— 角度 0°/180° 與向量 (1,0)/(-1,0) **逐位元同** `"lr"`/`"rl"`;`None`/`"po"`
  仍逐位元同件序;非 cascade 主秀 beat 不受任一方向影響。
- **V2 projection ordering(crux)**:每個新方向下各件峰時刻依**該方向投影鍵** `x·ux+y·uy` 嚴格遞增
  (任意角的波序 = 投影序)。
- **V3 signature + interface**:每個新方向仍一道有序跨件波(沿投影序散佈 ≥ 0.30)+首尾 setup identity + 特效 slot alpha=1。
- **V4 orthogonality**:新方向(角 / 向量)下仍保 (a) dir⟂深度(峰 overshoot 跨方向相同,HIRES 量消相位時移混疊)、
  (b) dir⟂nrip(帶 ripples 各件 pop 次數==nrip)、(c) dir⟂span(帶 span 跨件散佈==span;相位集合只被排列→min/max 不變)。
- **V5 neg-control**:(a) **crux discriminator** 垂直 90° `[3,0,4,1,2]` + 對角 45° `[3,0,1,2,4]` 實測峰序 ∉ 全部 J-5 序;
  (b) 連續性/端點:0°==lr、180°==rl、90° 兩者皆非(lr/rl 為投影族端點,內部為新);(c) 投影≠radial:crux 峰序≠co/oc;
  (d) 輸入守衛:零向量 / 長度≠2 向量 / bool / 未知字串 → ValueError。
- **端到端**:`build_spine --animate --cascade-dir 90` 直出垂直掃波;`validate_build` round-trip overall_pass。

## 關鍵發現

1. **「補成連續」是一種獨立的研究動作**:J-5 把一個隱含預設(件序即波向)顯式化成**離散**軸(4 向);J-6 再把這條
   離散軸**補成連續**(任意角 + 向量)。離散→連續本身是個通用槓桿:凡是「挑了幾個具名值」的軸,問「這些具名是不是
   某連續參數的取樣?」往往能一般化(此處 lr/rl 正是連續角的 θ=0°/180° 取樣)。
2. **一般化時務必分清「含」與「不含」**:投影族**含** lr/rl(基數軸=特例),但**不含** co/oc(radial 是 2D 非線性,
   不是任何單一投影)。誠實的一般化要同時說清楚「哪些舊值被收編成特例」「哪些舊值是另一族、保留」。
3. **零回歸的來源是「特例逐位元相等」而非「預設不變」**:lr 的投影 `k=x·1+y·0` 在浮點下 `y·0=0`、`x·1=x` → 精確
   `=x`,與 J-5 直接 `k=x` 逐位元相等 → 排序→rank→相位值皆同。一般化若想宣稱向後相容,要證舊值在新路徑下**逐位元**
   重現,不能只證「預設沒變」。

## honest boundary(仍在)

- **J-6 不是新正交軸**,是方向軸的連續化(取值擴充);跨件時序通道仍是**三條**正交軸(結構 × 幅度 × 方向)。
- 方向選擇(具體用哪個角 / 向量)是 **PROPOSAL**(手感 A 類);`build_spine` 預設 `cascade_dir=None`(件序,byte-identical),
  角度 / 向量為 **opt-in**(`--cascade-dir 90` 或 `--cascade-dir "1,1"`)→ 對既有 golden 零回歸。
- 單一真值資產(robot)。`spine-anim-forge` 仍 HOLD(運動基元先驗、單一真值,防固化)。

## 產出

- `tools/analyzer/gen_animations.py`:`_normalize_cascade_dir()`(方向規格→`(kind, payload)`:po/proj/co/oc,
  角度→`(cosθ,sinθ)`、向量→正規化單位向量,零向量/長度≠2/bool/未知字串→`ValueError`)+ `_cascade_phase_of` 改走統一排序鍵。
- `tools/analyzer/build_spine.py`:`--cascade-dir` 吃角度(如 `90`)或向量(如 `"1,1"`)(`_parse_cascade_dir`);
  具名 lr/rl/co/oc/po/auto 不變。
- `tools/analyzer/validate_cascade_dir_vector.py`(新,5 AC)+ `tools/check_readiness.py` 新增 cap `cascade_dir_vector`。
- `knowledge/s1-cascade-dir-vector.md`(本檔)+ `knowledge/README.md` 索引。
