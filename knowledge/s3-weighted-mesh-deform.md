# S3 — weighted mesh 骨骼驅動變形器 + 真值變形場(補上唯一未驗維度)

- **結論**:實作並**驗證正確**一個 CPU 版 weighted-mesh 骨骼驅動變形器(Linear Blend Skinning +
  Spine 3.8 骨骼世界變換 + 緊湊 bezier timeline),對 Award 機器人 **3 個 weighted mesh 件**
  (光暈/左手/身體)抽出**真值變形場**。這補上 `compare_robot_mesh.py`(靜態 IoU)明列的
  **唯一未驗維度:weighted mesh 的骨骼變形品質**。
- **信心**:高。變形器以「與資料無關的封閉解」自驗(剛體不變性誤差 **1.7e-13**、setup identity **0.0**),
  再對真實動畫抽變形場並下拓樸判定。
- **階段**:第 2 階段 / S3 + S2(評估器樞紐)。里程碑:首次量化 weighted mesh 的**骨骼變形**(非靜態、非逐頂點 deform)。
- **工具**:`tools/mesh_gen/weighted_deform.py`(變形器)+ `tools/mesh_gen/validate_weighted_deform.py`(驗證+抽場)。

## 標準指令

```
python3 tools/mesh_gen/validate_weighted_deform.py    # 4 項 AC 全過 → exit 0
```

metrics → `knowledge/figures/weighted_deform_field.json`;視覺 → `knowledge/figures/weighted_deform_field.png`
(列=件 glow/hand/body,欄=Loop/In;灰=setup,彩=時間漸層)。

## 變形器數學(重現 Spine 3.8 `computeWorldVertices`,weighted 路徑)

1. **骨骼世界變換**(transform=normal,依 list 拓樸序 parent→child):
   `la=cos(rot+shX)·sX, lc=sin(rot+shX)·sX, lb=cos(rot+90+shY)·sY, ld=sin(rot+90+shY)·sY`;
   child 世界 = parent 世界 ∘ local(2×2 矩陣乘 + 平移)。
2. **timeline 套用**(相對 setup):rotate `angle`(加)、translate `x,y`(加)、scale `x,y`(乘)、shear(加)。
   缺鍵預設:加法欄=0、scale=1。
3. **LBS**:`world[v] = Σ_j w_vj·(M_j·bind_vj + t_j)`(bind 為相對該骨 setup 座標,權重每頂點和=1)。
4. **緊湊 bezier**(雷點 #7):`{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}` → P0(0,0)P1(cx1,cy1)P2(cx2,cy2)P3(1,1);
   給正規化時間 x 解 s 使 Bx(s)=x(二分),回 By(s)。`"stepped"`=hold、無 curve=linear。

## 四項 AC(先驗證評估器/變形器可信,再下判定)

| AC | 內容 | 結果 |
|---|---|---|
| AC1 | 剛體不變性:對所有骨施同一剛體 → LBS 必等於「setup 頂點的同一剛體」(權重先正規化隔離數學) | **1.7e-13** PASS |
| AC2 | setup identity:Legend_Loop t=0 的 LEG 骨群偏移全 0 → mesh 世界座標 == setup | **0.0** PASS |
| AC3 | Loop 變形非平凡:3 件 max_disp > 2px(有真實訊號) | PASS |
| AC4 | Loop 藝術家真值拓樸乾淨:逐幀 0 自交/0 翻面/0 退化 | PASS |

原始匯出權重和最大偏差 **1.0e-5**(資料捨入,非數學誤差);故 AC1 先正規化權重再驗變換/LBS 正確性。

## 真值變形場(17 幀/動畫)

| 件 | nv | tris | **Loop**(平滑基準) | **In**(入場 burst) |
|---|---|---|---|---|
| 光暈 glow | 78 | 76 | si=0 disp≤**29px** area∈[0.997,1.003] **clean** | si≤71 disp≤**611px** area≤1.85 **自交** |
| 左手 hand | 80 | 116 | si=0 disp≤**36px** area∈[0.975,1.000] **clean** | si=0 disp≤241px area∈[0.743,1.014] clean |
| 身體 body | 98 | 154 | si=0 disp≤**12px** area∈[1.000,1.001] **clean** | si=0 disp≤172px area∈[0.932,1.014] clean |

## 三個關鍵發現

### 1. 平滑真值基準 = 持續型 idle **Loop**(3 件全 clean),不是入場動畫
`Award_Legend_Loop` 是呼吸型 idle:位移小(≤36px)、面積幾乎不變、3 件逐幀全 clean。
→ 這是量化「骨骼驅動變形平滑度」的**正確真值基準**(對照 unweighted 4 mesh 在 deform 下 si=0 的自一致性)。

### 2. **並非所有藝術家 weighted mesh 在自己的動畫下都拓樸乾淨** — 誠實界定
`Award_Legend_In`(入場 burst)裡**光暈**極端非剛體縮放(t=0 已 disp=529px、area 衝到 1.85)→
逐幀 si 最高 71、flip 7。這是 LBS「糖果紙(candy-wrapper)」效應:光暈跨 4 根 LEG 骨(49/33/29/12 影響),
入場時各骨運動不一致 → 頂點扇開自交。**但光暈是 additive soft glow,重疊發光視覺無害**,藝術家並未
把它設計成無自交。→ 與先前「光暈需 boundary-dense-v1 軟邊模式」一致:**光暈屬 soft-blend 類,
不納入平滑度基準**;結構性件(身體/左手)即使在 burst 下仍 clean。

### 3. 入場 In 起點 ≠ setup;Loop 起點 == setup
Legend_In 從遠處/大縮放狀態切入,t≈0.7 才收斂到 disp=0(== Loop 的 t=0)。故 setup identity 只在
Loop t=0 成立;抽真值變形場的 setup baseline 與動畫無關(用 pose(None))。

## ⚠️ 誠實限制 / 尚未做

- 本次驗的是**「藝術家 mesh 在真實骨骼動畫下的拓樸品質」+ 提供真值變形場**;**尚未**用它去
  評「我方生成的 weighted mesh」——那需要 (a) S3 生成 weighted mesh(內部取樣密度 + BBW 權重把
  相同骨群綁上生成拓樸)、(b) 用同一 Loop 骨骼場驅動、(c) 對照本真值場的平滑度指標。**這是下一步。**
- 只驗 transform=normal(3 件的骨鏈全 normal、單位 scale、無 shear);其他 transform mode 未走到。
- 平滑度目前用拓樸閘(si/flip/degen)+ 位移/面積範圍;更細的「彎折平滑度」(相鄰三角法向變化率、
  邊長變異)指標可於接生成器時再加。

## 下一步候選(承接)

1. **S3 weighted 生成器**:對身體/左手這類結構件,加「內部取樣密度控制 + BBW 骨綁權重」,綁上同一
   LEG 骨群,用 `weighted_deform` 的 Loop 場驅動,對照本真值場(位移/面積/自交)量平滑度差距。
2. **平滑度細指標**:接生成器時加「相鄰三角法向變化率 / 邊長變異」量化彎折平滑,超越 pass/fail 拓樸閘。
