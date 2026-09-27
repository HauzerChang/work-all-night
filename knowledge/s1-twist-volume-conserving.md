# S1 — volume-conserving twist(反相雙軸 shear 接體積守恆等向 scale)

> 結論先行 / candidate **G-4''''''-vol** / 里程碑 2026-09-27 / 信心:**高**(閘 6 AC + 負對照 + 22→23 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 twist 系列(G-4'''''' 生成 → tier 幅度 → count 段數)一路留到現在的**最後一條 honest boundary**:
反相雙軸 shear 的 Spine local 行列式 `det = cos(shearX − shearY) < 1` → **擰轉使面積縮小**。本次掛一條
**等向(uniform)補償 scale** `s = 1/√cos(shearX − shearY)`(scaleX==scaleY)使全域 local 行列式

```
det = (s · s) · cos(shearX − shearY) ≡ 1      # 擰而不變面積
```

`shear + scale + rotate` 三通道**同時**作用、塞滿一般仿射四自由度**且體積守恆**。至此**一般仿射四自由度
(rotate / 非均勻 scale / shearX / shearY)+ 體積守恆全數在生成端成立**。

## 幾何依據

Spine 3.8 bone local(`transform_matrix_full`,TransformMode.Normal,θ=0):

```
x 基底 = (cos(shearX),        sin(shearX))          · scaleX
y 基底 = (cos(90+shearY), sin(90+shearY)) = (−sin(shearY), cos(shearY)) · scaleY
det = scaleX·scaleY · [cos(shearX)cos(shearY) + sin(shearX)sin(shearY)]
    = scaleX·scaleY · cos(shearX − shearY)
```

- 兩基底夾角 = `90 + shearY − shearX`。反相 twist(shearX=+a、shearY=−φa,φ=0.7)時 `shearX − shearY =
  (1+φ)a` → cos<1 → 面積被擰小(平行四邊形沿對角擰緊)。
- 補償只約束 **乘積** `scaleX·scaleY = 1/cos(shearX − shearY)`。**等向**(scaleX=scaleY=s、s²=1/cos)是
  最小(不再引入額外各向異性)的守恆選擇 —— twist 的各向異性**全由 shear 提供**,scale 純為等向面積復原。
- 端點 shear=0 → cos(0)=1 → s=1 → **identity 介面自動保持**(可插 Loop 間)。

## 與 squash(G-4'''')體積守恆的**機制對比**(關鍵鑑別點)

| | squash(G-4'''') | volume-conserving twist(本次) |
|---|---|---|
| 體積守恆 scale | **非均勻**(scaleX≠scaleY,`scaleX=1+q, scaleY=1/(1+q)`) | **等向**(scaleX==scaleY=s) |
| scale 的角色 | scale 本身**即擠壓**(各向異性來源) | scale 純**補償** shear 造成的面積變化 |
| 各向異性來源 | scale(shearX 另加扭) | 全部來自 shear(scale 等向) |
| det≡1 由 | `(1+q)·1/(1+q)≡1` 建構保證 | `s²·cos(shearX−shearY)≡1`,s 由 cos 反推 |

→ 兩種**同是體積守恆、但不同源**的機制;閘 TV6(b)以「twist scale 等向 vs squash scale 非均勻」互證隔離。

## 實作(全 additive、預設逐位元向後相容)

- `beat_templates.gen_twist(role, side, radial, nosc=4, vol_conserve=False)`:`vol_conserve=True` 時掛
  `b["scale"]`(等向補償);`False`(預設)→ **逐位元同 shear-only twist**(無 scale 通道)。
- `beat_templates._twist_scale_env(shx_env, shy_env)`:對每個 shear 極值 τ 算 `s=1/√cos(shx−shy)`,回
  `[(τ, s, s)]`,首尾 (1,1)。scale 值 round 到 4-dec(同 gen_squash)。
- `gen_animations._build_beat(..., twist_vol=False)` / `build_animations(..., twist_volume=False)`:
  twist 專屬 `vol_conserve` kwarg 只對 cat=="twist" 生效;其餘類別不吃。
- `build_spine.build(..., twist_volume=False)` + CLI `--twist-volume`;配 `--shear-pivot`
  端到端把 shear+scale+rotate 三通道一起繞關節 pivot 補償(`include_scale` 已隨 shear_pivot 開)。

## 閘 `validate_twist_volume.py`(6 AC 全 PASS,真實 robot 骨架)

- **TV1** present + shear&scale 雙通道(crux):≥1 bone 同時帶雙軸 shear(shearX 峰 16°、shearY 峰 11.2°)
  **與** scale 通道,且 scale **等向**(每幀 scaleX==scaleY)。
- **TV2** 體積守恆(crux):每內部極值幀全域 `|det−1| ≤ 8.8e-5`(TOL 2e-4);**負對照 scale≡1(純 twist)
  `|det−1|` 0.04–0.11(縮面積)** → >500× 分離,證閘測「真體積守恆」非「有 scale 即可」。
- **TV3** 雙軸反相阻尼簽章保形:體積耦合不破壞 twist 簽章(兩軸繞 0 變號≥3、相繼極值遞減、每內部極值反號)。
- **TV4** identity 介面:shear 首尾 (0,0)、scale 首尾 (1,1)、sample 端點各 bone identity。
- **TV5** 端到端三通道 pivot 不動:`--twist-volume --shear-pivot` pivot 殘差 **<0.016px**(含補償 scale)
  vs 負對照(繞件中心)8–29px。
- **TV6** 負對照/隔離/向後相容:(a) 無補償縮面積(0.11);(b) 等向 vs squash 非均勻隔離;(c)
  `twist_volume=False` 逐位元同 shear-only(無 scale)+ 移除 twist storyboard 其餘 beat 逐位元不變。

## honest boundary(仍在)

- **vol 僅作用 base twist**:tier 變體仍 shear-only。vol 隨檔位放大需**重算補償 scale** 以維持 det≡1
  (tier 放大 shear → cos(shearX−shearY) 變 → 補償 s 須跟著非線性重算,比照 squash 的耦合 amplify),為後續。
- 幅度/φ 為 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。

## 一句話心法

**跨通道約束(det≡1)由建構(等向補償 scale = cos 的反推)保證;同一守恆目標,squash 走非均勻、twist 走等向
—— scale 的『語意角色』(自己是擠壓 vs 補償別人)決定它是各向異或等向。**
