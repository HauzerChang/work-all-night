# S1 — 體積守恆扭轉(candidate G-4''''''-vol,`twist_volume_conserving` L2)

> 2026-09-24 run 002。續 twist 一路(G-4'''''' 生成器首度驅動 shearY → G-4''''''-tier 兩軸幅度隨檔位 →
> G-4''''''-count 扭轉段數隨檔位):這三個里程碑**每一個**都在結尾明列同一條 honest boundary ——
> 「反相雙軸 shear 未接體積守恆耦合 scale(`det=cos(shearY−shearX)≠1` → **擰轉變面積**;
> volume-conserving twist 為後續)」。本次正好把這條邊界接上:讓扭轉**擰而不變面積(det≡1)**。

## 幾何:為什麼純扭轉會縮小面積

Spine 3.8 bone local 2×2(`pivot_rotation.transform_matrix_full`,deg=0):

```
a = cos(shearX)·sx    b = cos(90+shearY)·sy = −sin(shearY)·sy
c = sin(shearX)·sx    d = sin(90+shearY)·sy =  cos(shearY)·sy
det = a·d − b·c = sx·sy·[cos(shearX)cos(shearY) + sin(shearX)sin(shearY)]
                = sx·sy·cos(shearX − shearY)
```

twist 令 `shearY = −φ·shearX`(φ=`TWIST_PHI`=0.7,反相),故 `shearX − shearY = (1+φ)·shearX`:

```
det = sx·sy·cos((1+φ)·shearX)
```

純扭轉(sx=sy=1)時 `det = cos((1+φ)·shearX)`。因 `|shearX|>0 ⇒ cos<1`,**扭轉在每個 shear 極值處
縮小面積**:特效件峰 shearX=16° → `cos(1.7·16°)=cos(27.2°)=0.889`,**~11% 面積損**(頭件 10° → 0.956,~4.4%)。
這就是 G-4''''''→count 一路留著的 honest boundary(`det=cos(shearY−shearX)≠1`)。

## 解:均勻耦合 scale 補償面積

加一條**均勻**(isotropic)耦合 scale `sx=sy=s`,令 `s² = 1/cos((1+φ)·shearX)`,即

```
s = 1 / √cos((1+φ)·shearX)        (beat_templates._twist_vol_scale)
⇒ sx·sy = s² = 1/cos((1+φ)·shearX)
⇒ det = [1/cos((1+φ)·shearX)]·cos((1+φ)·shearX) ≡ 1     (擰而不變面積)
```

- `shearX=0`(首尾 identity)→ `cos(0)=1` → `s=1` → `scale=(1,1)`:**介面契約保持**(可插 Loop 間)。
- `s ≥ 1`(cos≤1)→ 補償是**淨脹**(呼吸式微膨),把扭轉損掉的面積補回來。
- **shear 通道逐位元不變**:只**加**一條 scale 通道,shearX/shearY 一字不動 → φ 比值、反相、阻尼簽章全保。

實測(特效 16° 峰逐極值,scale 6 dp 捨入):`det` 在每關鍵幀 = 1.0000000±1e-6;`|sx−sy|≡0`。

## crux:與 squash 的鑑別(為什麼必須「均勻」)

| | squash(G-4'''') | volume-conserving twist(本次) |
|---|---|---|
| scale 型態 | **非均勻**(scaleX≠scaleY) | **均勻**(sx==sy) |
| scale 自身 | `scaleX·scaleY≡1`(自守恆) | `sx·sy=1/cos>1`(淨脹) |
| 誰破面積 | shear 破、scale **另計**(scale 自己守恆) | shear 破、scale **補償**(抵銷 shear 的 cos) |
| 語意 | 擠壓(壓一軸拉一軸) | 扭轉(擰而不變面積) |

**關鍵**:squash 的 scale 是「自己守恆」的擠壓形變(`sx·sy=1`),把它拿來補償 twist 會得到
`det = (sx·sy)·cos = 1·cos = cos ≠ 1` —— **仍不守恆**(VV6a 負對照:squash 式 scale 補償峰 det=0.889,
偏離 0.11)。twist 的面積是被 **shear 本身**破壞的(`cos<1`),補償 scale 必須讓 `sx·sy=1/cos` 才抵得掉,
而**維持 sx==sy(均勻)** 才不引入擠壓非均勻 → 保住「純扭轉」語意。`|sx−sy|≡0` 是與 squash 的鑑別簽章。

## 一般仿射四自由度首度湊齊且守恆

至此,Spine local 一般仿射 M 的四自由度(rotate / 非均勻 scale / shearX / shearY)不但**生成端全被真實
beat 驅動過**(G-4'''''' 收齊),本次更讓 **shear + scale + rotate 三通道同時作用而 det=1** ——
即「用滿仿射自由度、面積仍守恆」的扭轉。`build_spine --shear-pivot` 把三通道一起繞關節 pivot 補償
(Δ=(M−I)(O−P) 通用公式),補償**只加 translate、M 不變** → det≡1 於未重採樣件端到端延續。

## 實作(全 additive,opt-in,零回歸)

- `beat_templates.py`:新增 `_twist_vol_scale(shx_deg)`;`gen_twist(..., vol_conserve=False)` —— 預設 False
  → 逐位元同無此參數(無 scale 通道);True → 額外產均勻耦合 scale 通道(與 shear 同時間點)。
- `gen_animations.py`:`_build_beat(..., twist_volume=False)` 只對 **twist** cat 帶 `vol_conserve=True`
  (kwargs 隔離,其餘 count-aware 類別不吃);`build_animations(..., twist_volume=False)` 透傳(base + tier 變體)。
- `build_spine.py`:`--twist-volume` 旗標 → `build(..., twist_volume=True)`。
- `validate_twist_vol.py`:新閘 6 AC。復用 `validate_twist_gen`(雙軸讀取/反相判準/fixture)、
  `validate_shear_gen`(阻尼簽章)、`validate_shear_pivot._world`、`pivot_rotation.transform_matrix_full`。
- `check_readiness.py`:註冊 cap `twist_volume_conserving` L2(pipeline)。

## AC(`validate_twist_vol.py`,先驗庫→**真實 build_spine robot 骨架**→build_animations(twist_volume=True))

- **VV1 present + backward-compat**:每 twist beat 直出/finite/≥1 bone 帶 **shear+scale** 雙通道、scale 首尾
  (1,1);twist_volume=False → twist beat **無** scale 通道,且 True 的 shear 逐位元同 False(加 scale 不擾動 shear)。
- **VV2 體積守恆 det≡1(crux)**:每 twist bone 每內部極值 `|det(M)−1| ≤ 2e-3`(實測 worst 1e-6);
  負對照(無 vol scale,sx=sy=1)每 bone 峰 det ≤ 0.956 < 0.98(證面積確被扭轉縮小 ≥2%、且 scale 是守恆之因)。
- **VV3 均勻 + 反相雙軸保形(crux)**:每 bone scale 每幀 `|sx−sy| ≤ 1e-4`(與 squash 非均勻鑑別)+ 反相雙軸
  逐內部極值保形(反號+偏離)+ φ=|shy/shx|≈0.7(誤差 ≤2e-3)。實測 `max_iso=0.0`、φ 逐極值 0.7。
- **VV4 兩軸阻尼保形**:shearX 與 shearY 各自首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減(證加 scale 未動 shear)。
- **VV5 端到端 det≡1 + pivot 不動**:`build_spine --animate --twist-volume --shear-pivot`。有關節 pivot 的 bone
  在 `--shear-pivot` 下 scale/shear 被**重採樣到 60fps 密網格**(標準 keyframe 重採樣),shear 頂點次幀弦割讓 det
  偏離 ~0.5%(取樣假影,非設計破壞)→ 故 det≡1 端到端**在未重採樣件**(無關節 pivot → 通道原封)嚴格驗
  (worst 9e-7);有關節 pivot 件改驗 **pivot 殘差 < 0.5px**(實測 0.004–0.016px)vs 負對照(未補償)8–29px。
- **VV6 負對照/隔離**:(a)**均勻性守衛** squash 式 sx·sy=1 補償同扭轉 → 峰 det 偏離 0.11 ≥ 0.02(證非均勻**不**守恆
  twist,均勻才是解);(b)**無 scale 守衛** vol=False 峰 det 非守恆;(c)**scale 隔離** 非 twist beat 在 True/False
  逐位元不變(vol scale 只作用 twist);(d)**加性** 移除 twist storyboard → 其餘逐位元不變。

**6 AC 全 PASS**。端到端 `build_spine --animate --twist-volume --shear-pivot` 直出 `twist`(帶均勻耦合 scale,
det≡1),`twist__{tier}` 亦帶 scale 通道。

## 關鍵發現

- **有兩種「體積守恆」機制,語意不同**:squash 是 scale **自守恆**(`sx·sy=1`,擠壓不變體積);
  vol-twist 是 scale **補償 shear 破的面積**(`sx·sy=1/cos`,扭轉不變面積)。前者 scale 是形變主角、
  後者 scale 是配角(抵銷 shear 的 det 損)。**同一句「體積守恆」對不同破面積來源要用不同耦合**。
- **均勻 vs 非均勻是鑑別點**:補償 shear 破的面積要用**均勻** scale(不引入新的擠壓);用非均勻(squash 式)
  既補不對(sx·sy=1≠1/cos)又污染扭轉語意。`|sx−sy|≡0` 是 vol-twist 的客觀鑑別簽章。

## honest boundary(仍在)

- **tier / count 檔位變體未接 vol 的耦合放大**:檔位變體套 tier 幅度增益 g 於 **shear**(shearX→g·shearX),
  卻**未**依 g 重算 scale 補償(補償量隨 shear 增大應變 `s=1/√cos((1+φ)·g·shearX)`)→ 高檔位 det≠1。
  需一個 `_amp_scale_twist_vol` 耦合放大(比照 squash 的 `_amp_scale_coupled`「沿守恆流形放大」)。本次只驗
  **base(Super/未放大)** det≡1;高檔位守恆為後續。
- 均勻補償量、φ、幅度皆為 **PROPOSAL**(手感 A 類,留使用者);單一真值資產(robot)。
- cap `twist_volume_conserving` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
