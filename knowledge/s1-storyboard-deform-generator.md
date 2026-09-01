# S1/S3 — mesh deform timeline 生成器(candidate 0e,讓軟件「會變形」)

- **結論**:補上 candidate 0d 的缺口 —— 之前 `build --animate` 只生 bone TRS + slot color,mesh 軟件
  (窗簾/陰影/布料)只會被父骨**剛體搬動**,不會像真實 main_draw 窗簾那樣**逐頂點變形**(9 支動畫全有 deform)。
  新增 `gen_deform.py`:對 skin 裡每個 **unweighted** mesh attachment 生成 Spine 3.8 `deform` timeline,
  用**駐波微顫(standing-wave shimmer)**確定性基元。對 **main_draw 4 個真實藝術家 mesh 拓樸**
  用已校準的 `deform_eval` 閘驗收,**AC1–4 + 負對照全 PASS**;整合驗:對 main_draw 注入 12/12
  (4 mesh × 3 非-hold beat)deform 全乾淨 + JSON 可載入。
- **信心**:高(客觀幾何閘;閘本身經藝術家真值 + 負對照雙向校準)。
- **相關階段**:第 2 階段(mesh 能力)× S1 keyframe 產線 —— 讓 build --animate 的軟件會 deform。

## 運動基元:駐波微顫

位移(沿件**短軸**)= `A · env(s) · sin(2π·k·s) · temporal(τ)`
- `s` = 頂點沿**長軸**正規化座標(0..1);`env(s)=(1-s)`(懸掛模型:固定端不動、自由端擺最多)。
- `sin(2π·k·s)` = 空間駐波結構(k=wavenum,預設 1.0)。
- `temporal(τ)`:loop→`sin(2πτ)`;其他 beat→`sin(πτ)`。**兩者在 τ=0 與 τ=1 皆 = 0**。
- `A = amp_frac · 短軸 extent`(預設 amp_frac=0.08)。

**關鍵設計 = 端點回 identity**:temporal 在 τ=0/τ=1 皆為 0 → deform 端點 == setup identity(0 offset)。
故 (a) loop 無縫循環;(b) 與 gen_animations 的 bone timeline 共用「setup identity 介面」,
任意 beat 串接無跳變(對齊 candidate 0d 的 AC4)。端點另強制歸零消浮點殘差。

## AC(對 main_draw 4 真實 mesh,`validate_deform_gen.py`)

| AC | 判準 | 結果 |
|---|---|---|
| AC1 seamless | loop deform 首幀==末幀==identity(maxdiff/identity ≤1e-6) | ✅ 4/4 (0.0) |
| AC2 clean | 預設參數,4 mesh 全 beat 逐子幀 si=0/flip=0/degen=0 | ✅(loop 49 poses、其他 25 poses 全乾淨) |
| AC3 non-trivial | 每 mesh 最大位移 >3px(非 no-op) | ✅(curtain ~19.6/19.4px、shadow ~5.2/7.0px) |
| AC4 identity 介面 | 每 beat deform 端點 == identity | ✅ 4/4 |
| NC discriminating | 同 mesh 施「高頻雙軸扭轉」壞場 → 閘必爆 | ✅(si 1–125、flip 2–12,4 mesh 全爆) |

**整合驗(end-to-end)**:對真實 main_draw 骨架清掉原生 deform、注入 3 beat → **12/12 pair 注入、全幀乾淨、
JSON round-trip 可載入**;`build_spine --animate` 對剛體 robot_parts 正確注入 **0** 個軟件 deform
(肢體皆 region/weighted,無 unweighted 軟件)且不崩潰、wiring 在位。

## 發現 / 誠實界定

- **此類 deform 對 strip 拓樸無條件安全**:純短軸橫向駐波施於直掛薄片,即使把 amp_frac 拉到 1.2
  (位移 ~294px,逼近真實 314px)或 wavenum 拉到 4.0,4 mesh **仍 si=0/flip=0**。coarse strip(21v/12v)
  解析不出高頻、單軸橫移不易讓三角互穿 → 是**正面穩健性**,不是閘失能。故負對照改用「高頻雙軸扭轉壞場」
  (證閘在同 mesh 上仍具鑑別力),而非「把生成器參數拉爆」。
- **deform 只對 unweighted mesh**:weighted mesh(`len(vertices)!=len(uvs)`)靠**骨骼 skinning** 變形,
  deform 不是對的機制(且 setup 位置需經 bind 逆變換還原)。`mesh_attachments()` 自動跳過 weighted。
  軟件(curtain/shadow/布料)本就是 unweighted mesh + deform 驅動 → 正是標的。
- **env/wavenum/幅度是先驗手感**(懸掛方向、波數、擺幅),非學自真值 → 屬美術可調(A 類),
  客觀交給幾何閘。真實藝術家的 deform 是逐幀手 key 的複雜位移(達 314px),本生成器只提供「會動且不破」的
  基線微顫,不宣稱追平藝術家表現力。

## 檔案

- `tools/analyzer/gen_deform.py` —— 生成器(`gen_deform_frames`/`add_deform_for_beats`/CLI)。
- `tools/analyzer/gen_animations.py` —— `build_animations(..., with_deform=True)` 內建注入。
- `tools/analyzer/validate_deform_gen.py` —— AC1–4 + NC + 整合驗。
- 閘:`tools/mesh_gen/deform_eval.py`(既有,已校準)。
