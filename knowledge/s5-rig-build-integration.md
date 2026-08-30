# S5 — 接觸縫 pivot 寫入 build_spine 關節骨樹(端到端)

> 里程碑 2026-08-30。接續 2026-08-29 的 pivot 推斷器(`knowledge/s5-rig-pivot-inference.md`)。
> 把「推斷出的關節 pivot」真的**寫進可載入的 Spine 骨樹**,補上 `spine-rig-pivot` 區塊
> `pivot_end2end`(原 L0)的空白。工具:`tools/analyzer/build_spine.py --rig`、
> 閘:`tools/rig/validate_rig_build.py`。一鍵驗證:`python3 tools/rig/validate_rig_build.py`(exit 0=PASS)。

## 做了什麼

`build_spine --rig`:在原本「每件綁 root、bone 置件中心」之上,對**結構肢體**改發**關節骨樹**:

```
root
└─ b_身體            (body render 骨,置身體件中心;rig 根,parent=root)
   ├─ j_頭  (joint) → b_頭   (render)
   ├─ j_右手 (joint) → b_右手
   └─ j_左手 (joint) → b_左手
b_光暈               (特效件仍掛 root、置件中心,不入結構樹)
```

**關鍵設計 —「中介 joint 骨」模式**(讓 setup pose 一格不動、round-trip 免費繼承):
- `j_<件>`:**置於接觸縫 pivot**(由 `infer_pivots.contact_seam_joint(父件, 子件)` 世界邊界多邊形算得),
  parent = body render 骨;local =(pivot − body 中心)。
- `b_<件>`:render 骨,parent = `j_<件>`;local =(件中心 − pivot)。**attachment 相對件中心不動**。
- FK 疊加:`b_<件>` 世界 = body中心 +(pivot−body中心)+(件中心−pivot)= **件中心**。
  → render 骨世界座標與非 rig build **逐件 d=0.0000px 相同**,attachment 原封不動 → setup pose byte 級不變。
- 而 `j_<件>` 正好落在 pivot:轉 `j_<件>` θ 度 →**整條肢體繞正確關節旋轉 θ**(這才是 rig 的價值)。

運動學父子樹**取自分析器 #4 note**(`_structural_tree`:note 含 body 者為根,head/limb 為其子,特效不入)
—— 誠實界定:tree 由分析器/先驗給,非本器推(肢體拓樸推斷是另一子問題)。
產物多一份 `rig_meta.json`(root_part / tree / 各關節 bone+pivot / roles)。

## 端到端閘(對 robot_parts.psd,真值+負對照)

`validate_rig_build.py` 用 `weighted_deform_eval` 的 Spine 3.8 FK 實算世界座標比對:

| 校驗 | 內容 | 結果 |
|---|---|---|
| **AC-R1 setup 不變** | 每 render 骨 FK 世界 == 非 rig build 件中心(d<0.5px) | **PASS** max d=**0.0000px**(繼承非 rig 已驗 round-trip) |
| **AC-R2 joint 落 pivot** | 每 joint 骨 FK 世界 == 推斷 pivot(d<0.5px) | **PASS** max d=**0.005px**(emitter 自一致) |
| **AC-R3 關節帶動肢體** | 轉 joint 30°→ 子件繞 pivot 轉 30°(半徑守恆)、父件不動 | **PASS** 三關節轉角 30.00°±0.003、radius_err<0.003px、父件位移 0 |
| **AC-R4 pivot 非天真** | pivot 顯著異於件中心 + 繞 pivot vs 繞件中心對末梢造成不同位移 | **PASS** med\|pivot−中心\|/scale=**0.255**、med 末梢位移/scale=**0.132**(皆>0.10) |

- **AC-R3 是核心**:證明骨樹**真的 articulate**——不是掛了個沒作用的骨,而是轉關節會帶動整條肢體繞
  正確 pivot 轉,且不擾動父件。
- **AC-R4 證明 pivot 落點有意義**:pivot 離件中心達 body 尺度的 1/4;若天真綁件中心,肢體末梢會落在
  差 0.13×body 尺度的地方(即動作明顯不同)→ 放對 pivot 才對。絕對準度(對美術真值)由
  `validate_pivots.py`(相同接觸縫演算法、同美術)另行擔保,兩閘互補。

## 誠實限制 / 為何仍 HOLD(未達 L3)

- **只在單一 rig(robot,3 關節)端到端驗過** → `pivot_end2end` 記 **L2**(真值驗收 + 評估器可信),
  **非 L3**(L3 定義為「對多個真實標的穩定通過」)。故 `spine-rig-pivot` 區塊**續 HOLD**。
- **多 rig 真值卡在資產**:Award 內另三個角色鏈(`1_OMG`/`2_SUP`/`3_MEG`)經實查,
  **各只是掛在單一鏈根骨上的『一整片 weighted mesh』(slot `OMG角色`/`superwin_角色`/`megawin角色1,2`),
  並非像機器人那樣拆成 身體/頭/左右手 多件、件間有接觸縫關節** —— 因此**無法充當第二個拆件 rig 的
  pivot 真值**。要達 L3 需**第二個拆件(multi-part)且有藝術家 pivot 真值的 rig 資產**(使用者層級資源)。
- **rig 與 weighted 目前不同時支援**:`--rig` 走 unweighted/region(避免與 weighted 控制骨 index 糾纏);
  兩者結合(關節骨樹 + 骨綁 mesh 變形)是後續步驟。
- 軸向精修 / 手感 = 美術(RULES A 類),不在此閘。

## 對 build_spine 的相容性(無回歸)

`--rig` 為 opt-in;不帶時 bone/slot/attachment 產出與改動前**逐件 d=0** 相同。改動後實跑確認既有閘全綠:
非 rig `validate_build`(premult 0.031、0 孤兒)、`validate_weighted_build`(OVERALL PASS)、
`validate_pivots`(4 AC PASS)皆未受影響。
