# 結構擴充 SOP（加 bone / 重綁 slot / reparent）

> 當動畫 patch 沒辦法解決問題，因為「該動的部位沒對應的 bone」，就要動骨架本身。

---

## 何時需要結構擴充

| 徵兆 | 解法 |
|---|---|
| 「某個部位想單獨動，但目前綁在一塊大 bone 上」（例：胸口收回受限於 bady_up 是整塊上身） | **加新 bone + 重綁 slot** |
| 「兩個部位視覺上連體，但結構上獨立，動畫期間分離」（例：胸口下沉但頭沒跟著） | **Reparent 一方到另一方下、用 transform mode 控制繼承** |
| 「想加新配件（劍、披風、光環），目前沒對應骨頭」 | **加 bone + slot + attachment**（attachment 可引用既有 atlas region） |

---

## SOP A：加 child bone + 重綁 slot

**前提**：某既有 slot 的 attachment 想要獨立位移/縮放，目前因綁在大 bone 上做不到。

### 步驟

```python
# 1. 加 bone（插入位置在 parent 之後，便於 hierarchy 視覺對齊）
new_bone = {
    "name": "main_chest",
    "parent": "bady_up",
    # x, y 預設 (0, 0)，scale 預設 (1, 1) → setup pose 視覺中性
}
# 不寫 x/y/scaleX/scaleY 是關鍵 → 既有動畫不受影響

bones_new = []
for b in data["bones"]:
    bones_new.append(b)
    if b["name"] == "bady_up":  # 插在 parent 之後
        bones_new.append(new_bone)
data["bones"] = bones_new

# 2. 重綁 slot
for s in data["slots"]:
    if s["name"] == "body_up":
        s["bone"] = "main_chest"   # 從 "bady_up" → "main_chest"
        break

# 3. 加一支驗證動畫
data["animations"]["Fg_Main_Chest_Demo"] = {
    "slots": { ... 攔截 attachment 顯示 ... },
    "bones": {
        "main_chest": {
            "translate": [
                {"time": 0.0, "y":  0},
                {"time": 1.0, "y": -7},
                {"time": 2.0, "y":  0},
            ]
        }
    }
}
```

### 不變式（違反就破壞既有動畫）

1. **新 bone setup pose 必須是 (0, 0, scale 1, 1)**
2. **新 bone name 不能撞**（既有動畫不會引用新名稱）
3. **被重綁的 slot 的 attachment offset (x, y) 不變**
4. **新 bone 是 parent 的 child**（這樣 parent 的既有動畫自動繼承）

只要這 4 條成立，**所有既有動畫播放結果視覺完全不變**。

### 為什麼能做到不變？

新 bone 在 setup pose = (0, 0)，是 parent 的「子層」但與 parent 重合。Slot 重綁到新 bone 後，attachment 的 anchor 從「parent 原點 + 偏移」變成「新 bone 原點 + 偏移」。但新 bone 的世界座標 = parent 世界座標 + (0, 0) = parent 世界座標。所以 attachment 視覺位置等同前。

既有動畫只動 parent（不動新 bone），新 bone 跟著 parent transform 繼承（normal 模式），slot 的 attachment 跟著新 bone → 跟著 parent → 與前一致。

---

## SOP B：Reparent + transform mode（修「視覺連體但結構分離」）

**前提**：A 已經加好新 bone，動畫期間發現某個既有 bone（如 head）沒跟著動，視覺上脫離。

### 步驟

```python
# 1. 計算新 parent 的世界座標相對位置
# 假設 head 原本是 main 的 child，現在要 reparent 到 main_chest（main 的 grandchild）
# main_chest 在 main 的世界座標：bady_up.y + main_chest.y = 77.56 + 0 = 77.56
# head 原本相對 main 的 y = 236.59
# head 新相對 main_chest 的 y = 236.59 - 77.56 = 159.03

for b in data["bones"]:
    if b["name"] == "main_head":
        b["parent"] = "main_chest"     # 改 parent
        b["x"] = 31.96                  # 原 x (main_chest 在 main 的 x = 0)
        b["y"] = 159.03                 # 補償後的 y → 維持世界座標不變
        b["transform"] = "onlyTranslation"  # ← 關鍵！
        break
```

### Transform mode 選擇指南

| 場景 | 推薦 mode |
|---|---|
| head 跟著 chest 上下移動但**不想被 chest scale 擠扁** | `onlyTranslation` |
| head 跟著 chest 移動 + 旋轉（如 chest 整體傾斜），但**不想被 chest scale 擠扁** | `noScale` |
| 完整繼承（child 跟 parent 做所有事，包含 scale 縮放）| `normal`（預設） |
| 想完全獨立但 set up pose 跟 parent 對齊 | `onlyTranslation` 並且不在動畫期間改 parent 任何 transform |

### 不變式

1. **head 的 setup world position 必須不變**（用 x/y 補償）
2. **既有動畫的 head.translate / head.rotate 都是 delta，會自動沿用**
3. **若 parent chain 有 rotation 或 scale 在新位置上動，要選對 transform mode** 避免 cascade 出意外

### 何時 reparent 會破壞既有動畫

- 既有動畫 main_head.translate 是相對於 main 的 delta，OK
- 但若某動畫期待 head 跟 main 的旋轉（main rotate 90°，head 也跟著轉 90°），改成 `onlyTranslation` 後 head 不會轉 → 視覺改變
- 解決：選 `noScale` 而非 `onlyTranslation`（保留 rotation 繼承）

### 範例：修「胸口收回時頭部分離」

```python
# 結構面：head 從 main 移到 main_chest
main_head.parent = "main_chest"
main_head.x = 31.96
main_head.y = 159.03    # 236.59 - 77.56
main_head.transform = "onlyTranslation"

# 動畫面：chest 用純 translate 而非 scale（onlyTranslation 不傳遞 scale）
"main_chest": {
    "translate": [
        {"time": 0.0, "y":  0},
        {"time": 1.0, "y": -7},  # 純位移，等效於原本 -3 + scale 0.92
        {"time": 2.0, "y":  0},
    ]
    # 移除 scale timeline
}
```

---

## SOP C：加新配件（bone + slot + attachment，可選用既有 atlas region）

**前提**：想加一個全新視覺元件（如能量光環、披風、肩甲延伸）。

### 路線 C1：用既有 atlas region（零美術）

```python
# 1. 加 bone
data["bones"].append({
    "name": "main_aura",
    "parent": "main",
    "y": 100,           # 位置在角色中心區域
    "scaleX": 2, "scaleY": 2   # 放大現有 region
})

# 2. 加 slot
data["slots"].append({
    "name": "main_aura_slot",
    "bone": "main_aura",
    "blend": "additive"     # 光效用 additive
})

# 3. 加 attachment 在 default skin 內，引用既有 region
data["skins"][0]["attachments"]["main_aura_slot"] = {
    "main_aura_attachment": {
        "name": "hit_main_glow_00",   # ← 引用既有 atlas region
        "width": 250, "height": 250,
        "scaleX": 1, "scaleY": 1
    }
}

# 4. 加動畫驗證
data["animations"]["Fg_Main_Aura_Pulse"] = {
    "slots": {
        "main_aura_slot": {
            "attachment": [{"name": "main_aura_attachment"}],
            "color": [
                {"color": "ffffff00"},               # 透明
                {"time": 1.0, "color": "ffffffff"}, # 全亮
                {"time": 2.0, "color": "ffffff00"}, # 透明（loop）
            ]
        }
    }
}
```

**優點**：零美術成本，純測試結構擴充流程。

### 路線 C2：用新 PNG（要動 atlas）

1. 取得新 PNG（或自製）
2. 加進 atlas（手動編輯 .atlas 加 region 區段；或用 Spine editor / TexturePacker 重打包）
3. 在 default skin 加 attachment 引用新 region name
4. 後續同 C1

**注意**：手動編輯 atlas 風險高（座標、size、rotate 都要算對），建議用工具重打包。

---

## SOP D：對稱擴充（左/右配對結構）

當 Fg_Main 這類「main_* + Hit_*」雙骨架的角色，加 bone 通常要對稱：

```python
# 為 main_chest 對稱加 Hit_main_chest
data["bones"].insert(after_Hit_bady_up, {
    "name": "Hit_main_chest",
    "parent": "Hit_bady_up",
})

# 重綁 Hit_body_up slot
for s in data["slots"]:
    if s["name"] == "Hit_body_up":
        s["bone"] = "Hit_main_chest"
```

注意：對應的 Hit 動畫（Fg_Main_Hit）若要利用新 bone，需要再加 timeline。

---

## SOP E：繞關節 pivot 的 keyframe 級解法（**零結構改動**）

> **前提**：某件（limb/head）動畫期間 `rotate` 讓它繞**件中心**轉，但物理上該繞**關節**（手臂繞肩、頭繞頸）。
> 這是「件該動、骨架抽象卻不到位」的徵兆——但有時你**不想**動骨架（避免 Cocos 完整重 import、避免改既有綁定）。

`gen_animations` 產出的 `rotate` 讓 bone 繞**自身原點**轉。非 `--rig` 組裝時 bone 原點落在**件中心 O**，
故 limb 的 `rotate` 會讓件繞 O 轉——對肢體不物理。兩條互補解法：

| 解法 | 手段 | 代價 | 何時選 |
|---|---|---|---|
| **移 bone 到關節** | 結構改動（SOP A/B：加 bone / reparent，bone 原點搬到關節）| 改骨架 → Cocos 須完整重 import skeleton data | 該件長期需要正確旋轉軸、要進美術主檔 |
| **繞 pivot 補償**（本 SOP E）| **純 keyframe**：bone 留件中心，額外加一條補償 `translate`，使淨效果=繞關節 pivot P 轉 | **零**結構改動，可純 patch、可 diff、可回滾 | 一次性/實驗性動作、不想碰骨架、快速驗證「繞對軸」的視覺差 |

### 數學（確定性、無 ML）

設 bone setup 原點在 **O**（parent 座標）、該幀 local 2×2 變換為 **M**（Spine TRS：`M = R(θ)·scale·shear`）。
要讓「貼在該 bone、對應件關節 pivot」的局部點 ℓ_P = P−O 的**世界座標恆固定在 P**（對任意 θ、scale、shear）：

```
Δ = (M − I)(O − P)
```

把這個 Δ 當**額外的 translate** 疊到該 bone。不動點性質（純代數，對**任意 M** 成立）：

```
world(ℓ_P) = (O + Δ) + M·(P − O) = O + (M−I)(O−P) + M(P−O) = O + (P−O) = P   ∀ M
```

- **θ=0 且 scale=1、shear=0 → M=I → Δ=0**：setup / Loop 端點 / In-Out 介面**全保持 identity**（無縫性不被破壞；B1/B2 的 loop 閉合性質仍成立）。
- 純旋轉（scale=I）退化為 `Δ=(R(θ)−I)(O−P)`；一般仿射（非均勻 scale / shear）公式不變。

### ⚠️ 關鍵實作：**密網格重取樣**

Δ 對 θ、s **非線性**。若只在原 rotate keyframe 放 Δ，兩幀之間 `translate` 線性內插 ≠ 真值 → pivot 在**幀間**漂。
解法：把 rotate（及 scale/shear）通道**加密重取樣**成均勻密網格（`dt` 秒），rotate/translate 同格、同為線性鍵。
幀間殘差 ~ `(1/8)|O−P|·(dθ_rad)²`，`dt=1/60` 下 **<< 0.1px**（實測 0.01px 級）。

### 用法（skill 公開 API，過渡期 import repo tools；E1 後 self-contained）

```python
from gen_lib.pivot_about_joint import pivot_about_joint

# anim 內「有 pivot」的 bone 會被**就地**轉成繞 pivot 版（回傳被轉的 bone 名）
converted = pivot_about_joint(
    anim,                                   # 單支 animation dict（就地改動！要存 A/B 先 deepcopy）
    bone_origin={"b_左手": (Ox, Oy)},       # bone setup 原點（parent 座標 = 件中心 O）
    pivot_of   ={"b_左手": (Px, Py)},       # 關節 pivot（如 tools/rig infer_pivots 推得的接觸縫）
    mode="rotate",                          # "rotate"(0i) / "scale"(R·S) / "affine"(含 shear)
)   # apply_g1=True（預設）→ 輸出前拔末鍵 curve（地雷 #12）
```

- **pivot 來源**：`tools/rig/infer_pivots.py`（S5，確定性接觸縫 pivot 推斷）或手量關節座標。
- **mode**：`rotate`=只補償 rotate（件繞 pivot 旋轉，scale 不動）；`scale`=R·S（繞 pivot 旋轉+縮放，如手臂從肩伸長）；`affine`=真實 Spine local 含 shear/非均勻 scale。
- **不變式**：pivot≈件中心（<0.5px）的 bone 自動跳過（繞件中心即繞 pivot，免贅餘 translate）；已存在的 `translate`（如 In 的徑向歸位）會被**疊加**，兩種位移語意共存。

### 驗收（純 CPU，`tools/analyzer/validate_b3_pivot.py`，5 AC 全 PASS）

- **B3-2 pivot-fixed**：真實 Award 左手繞肩 pivot，補償後不動點殘差 **0.0115px**（< 0.5）。
- **B3-3 負對照**：不補償（繞件中心）漂 **48.8px**（比值 4247×）；補償版件最遠點仍動 94px（沒凍住）。
- **B3-4 無縫**：θ=0 Δ=0、Loop 首尾 rotate/translate 端點相等。
- **B3-5 editor 雙真值**：補償後 skeleton 過 v1.3.0 `validator_v1`（0 error、editor 可匯入）+ loop 閉合；負對照注入末鍵 curve 被抓。
- 底層繞 pivot 數學的完整 7 AC（含剛性、bezier 容忍）見 repo `tools/analyzer/validate_pivot_rotation.py`。

> **Cocos 差異**：SOP E **不改骨架**，故**不需**本檔「結構擴充後 Cocos 推送」那套完整重 import——補償後的動畫是純 timeline 改動，走一般動畫 patch 推送即可。

---

## 結構擴充後的 Cocos 推送特殊注意事項

結構改變（加 bone / 改 slot.bone）後，Cocos 需要完整重新 import skeleton data：

1. `asset_operations.create` with `overwrite: true` ✓
2. `asset_system.refresh` ✓
3. **檢查 component_query 看 enumList 是否包含新動畫** —— 若不在，表示 spine 沒重 parse 成功，可能需要重啟編輯器
4. 補設 sp.Skeleton 的 loop / PMA / useTint（refresh 副作用）
5. Save scene

驗收必跑：
- 新動畫播放 → 看到新 bone 在動
- 任 2 支既有動畫播放 → 應與結構擴充前**視覺完全一致**

---

## 結語

Spine 骨架擴充的精髓不是「加東西」而是「**用 bone hierarchy 表達視覺元件的獨立性**」。每個視覺單元（胸甲、頭、武器、配件）都應該有自己的可動軸。當你發現「某個部位該動但沒辦法」就是骨架抽象沒做夠的訊號。

**Patch 化 SOP 的好處**：每次擴充都是可 diff、可重跑、可回滾的 Python 腳本。改錯就 git revert 重來。
