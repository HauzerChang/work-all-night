# S1 分鏡 → 動畫 keyframe(Loop 待機呼吸)

- **結論**:build_spine 產的靜態素材(`animations:{}`)現在「會動」了。新增 `animate_spine.py`
  把 analyzer #3 storyboard 的 **Loop(待機)** beat 確定性地轉成 Spine 3.8 `animations.loop`
  timeline;配套 `validate_animation.py` 反算量測運動指標,對 robot(12 檢查)/Symbol_Ww(38 檢查)
  **全 PASS**,負對照證明閘有鑑別力。
- **信心**:高(端到端可載入格式 + 自我量化閘 + 負對照)。
- **相關階段**:專案第 2 階段;S1 候選 0d(接續 `build_spine.py` 的最高優先項)。日期 2026-08-25。

## 角色 → 運動原語(deterministic role → motion primitive)

沿用 analyzer 的 `struct_role`(body/head/limb)+ effect 分類。Loop beat 各角色:

| 角色 | 原語 | Spine timeline | 幅度(預設) |
|---|---|---|---|
| body | 呼吸(胸口起伏) | `translate.y` 升餘弦 `A·(1−cos)/2` + `scale` 同步微幅 | A=clamp(0.015·H, 3, 12)px;scale ±1.2% |
| head | 微點頭/傾 | `rotate` 正弦 | ±3° |
| limb | 末梢微盪(相位錯開) | `rotate` 正弦,**相位 φ_i = i/n_limb** | ±4° |
| effect | 微脈動 | slot `color` alpha 升餘弦 | 0.75→1.0 |

- **loop 無縫**:每條 timeline 週期函數在 t=0 與 t=period 同值(尾幀強制=首幀),0 接縫。
- **相位錯開**:各肢體 `sin(2π(t/T+φ_i))` 相位不同 → peak 時間分散,避免「整身同步紙板感」
  (對應 CLAUDE.md 動畫課題「全身同步紙板感」的最小體現)。

## 誠實界定 / 已知限制

1. **dense-linear,非 bezier**:每週期 K=12 個等距 keyframe + 線性內插(Spine 無 curve 鍵=linear)。
   刻意讓**產生器與驗證器用同一種內插**,保證「閘驗到的 == JSON 裡的」。真實美術用 compact-bezier
   緩動(見 CLAUDE.md 雷點 7);bezier 緩動屬後續精修,dense-linear 對 proposal 級待機足夠平滑。
2. **只做 Loop beat**:In(入場爆發)/Out(退場)需要更大位移 + attachment 顯隱 timeline + overshoot,
   且無現成幾何真值可自驗 → 留作後續(可先做 In 的 translate/scale 彈入,量化 overshoot)。
3. **無真值 spine 逐幀對照**:Award 的動畫是美術手 K,節奏/幅度是主觀決定(RULES:主觀手感留給使用者)。
   本閘驗的是**客觀可量**維度(幅度在合理區間、無縫、相位有錯開、alpha 在 [0,1]),非「像不像美術」。
4. **pivot 未推斷**:limb 目前繞自身 bone(件中心)旋轉;真實末梢應繞根部關節(S5 pivot,唯一卡死環節)。
   件中心旋轉對「小幅待機」視覺可接受,大幅動作(In 甩入)才會露餡。

## 驗證器(validate_animation.py)量測與 AC

反算流程:讀 `animations.loop` → 重現 Spine linear 取樣(密集抽 200 點/週期)→ 逐角色量測:

- `body.ty_range` ∈ [2, 30]px、`body.seam` ≤ 1e-6
- `rotate.range`(head/limb)∈ [1, 12]°、`rotate.seam` ≤ 1e-6
- `limb.phase_spread`:肢體 peak 時間最大差 > 0.1·period(錯開)
- `effect.alpha_in01` ∈ [0,1] 且 `alpha_pulse` > 0.02、`effect.seam` ≤ 1e-6

**負對照(證明鑑別力)**:
- `_static_anim`(全零)→ body/rotate range 全 FAIL(passed=false)。
- `_inphase_anim`(肢體同相位)→ `limb.phase_spread` FAIL。
- 兩者皆如期 fail → `discriminating: true`。

## 標準指令

```
# 1) 產靜態素材   2) 注入 Loop 動畫   3) 驗證(含負對照)
python tools/analyzer/build_spine.py assets/robot_parts.psd --out specs/robot_parts_spine
python tools/analyzer/animate_spine.py specs/robot_parts_spine/skeleton.json --psd assets/robot_parts.psd --genre slot_bigwin
python tools/analyzer/validate_animation.py specs/robot_parts_spine/skeleton.json --neg
```

實測:robot → bones_animated=4/slots=1、12 檢查全過、phase_spread=0.5;
Symbol_Ww(18 件)→ 17 bones/1 slot、38 檢查全過、phase_spread=0.915。exit 0。

## 下一步候選

- **In beat**:彈入(translate/scale overshoot)+ attachment 顯隱;量化 overshoot 峰值/回穩。
- **bezier 緩動**:升級 keyframe 為 compact-bezier(ease-in-out),驗證器同步支援 3.8 散鍵 bezier。
- **接 pivot(S5)**:limb 繞關節而非件中心旋轉 → 需件→關節推斷(S1 候選 e)。
