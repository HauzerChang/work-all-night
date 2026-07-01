# S5 — mesh 權重綁定(bind_weights.py):unweighted mesh → Spine weighted mesh

- **結論**:S5 最後的可自動塊完成 —— `bind_weights.py` 把 rig 骨架上的 unweighted mesh 轉成 Spine
  **weighted mesh**,綁到對應骨。端到端產出 `assets/robot_parts_rigged.json`(6 bones/5 slots/
  3 weighted mesh/2 region),過 `evaluate_skeleton`;變形測試證明「轉某骨→該件繞 pivot 旋轉、
  其他件不動、θ=0 版面保真」皆 **0.0px 誤差**。**這隻機器人從「靜態擺放」變成「可依骨架變形的 rig」。**
- **信心**:高(evaluate_skeleton AC3 + 變形數值測試)。
- **階段**:第 2/3 階段 / S5(可自動部分全數完成)。

## 技術判斷:為何是 rigid 而非完整 BBW(誠實)

真正的 **BBW**(Bounded Biharmonic Weights)解決「**單一連續 mesh 橫跨多根骨**」的平滑混合。
本資產是**各件獨立 mesh、各掛自己的骨**(左手 mesh 全屬左手骨),關節活動由**骨架階層**負責 →
正確且穩健的綁定是 **rigid(每頂點權重 1 給自身件骨)**,BBW 的跨骨平滑在此無用武之地
(強行跨件混合反而讓件互相牽連)。

- `mode=rigid`(預設,對 part-based rig 正確):每頂點 → `[1, 自身骨index, bindX, bindY, 1.0]`。
- `mode=blend`(選用,給連續 mesh):inverse-distance² 到「自身+相鄰(父/子)骨」正規化,取 top-k。
  **⚠️ 是 inverse-distance 近似,非完整 FEM BBW**;對獨立件通常不需要(已驗權重合法但不建議用於本資產)。

## weighted 格式與 bind 座標

- Spine weighted:`vertices = [boneCount,(boneIdx,bindX,bindY,weight)*count, ...]`;`len(vertices)!=len(uvs)`。
- rig_draft 之後 mesh 頂點已在**骨-local**(相對 bone 原點=pivot)→ rigid 的 bindX/bindY 即該 local 座標。
- 多骨(blend)時 bindX/bindY = 頂點世界 − 該骨 setup 世界原點(setup 無旋轉,世界=平移鏈)。

## 自我驗證(機讀 + 數值)

| 檢查 | 方法 | 結果 |
|---|---|---|
| 權重合法 | evaluate_skeleton AC3(bone 索引在範圍、每頂點權重和≈1) | ✅ 和=1.0 |
| θ=0 版面保真 | 綁定後世界頂點 vs rest | 0.0px |
| 繞 pivot 旋轉 | 轉該骨 90°,對比「繞骨世界原點(=pivot)的 R90」 | 0.0px |
| 其他件不受影響 | 轉某骨後其他 mesh 世界頂點位移 | 0.0px |

- 對 `光暈` 與 `左手`(肢體)分別測試皆 0.0px;左手繞肩 pivot 乾淨旋轉。
- **測試 harness bug 留痕**:初版 `--test-bone` 與被測 slot 脫鉤(硬編第一個 mesh)→ 假性失敗;
  修為「test_slot = 綁在 test_bone 上的 mesh」。是 harness 錯,非 rig 錯(預設一致案例早已 0.0px)。

## 端到端 pipeline(現況)

`psd_slice`(切件)→ `generate_mesh`(件→mesh)→ `skel_to_json`(件→skeleton JSON)→
`rig_draft`(骨架階層 + 功能性 pivot + 人為 config)→ **`bind_weights`(→ weighted mesh)**。
產出 `assets/robot_parts_rigged.json` = **可變形的完整 rig**(差人微調 pivot + 配動畫)。

## 可重現

```
python3 tools/mesh_gen/rig_draft.py assets/robot_parts.psd --prefix 機器人拆件 \
    --rig-config assets/robot_parts.rig.json -o /tmp/rig.json
python3 tools/mesh_gen/bind_weights.py /tmp/rig.json --mode rigid -o assets/robot_parts_rigged.json
```

## 下一步

- 人微調 `robot_parts.rig.json` 的 pivot(A 類,可隨時做)。
- 配動畫 timeline:用 S1 影片分析(塊2 分群成件 + 運動型態)驅動骨骼旋轉/位移 → 逼近目標運動。
