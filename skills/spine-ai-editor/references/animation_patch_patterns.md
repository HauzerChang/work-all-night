# 動畫 Patch 模式參考

> 給定一個 Spine skeleton（bones / slots / skins 已存在），純加 / 改 animations 區塊的常見 pattern。

---

## Pattern 1：Idle 呼吸（最簡單）

「角色站著做呼吸動作」—— 純 bone translate，loop 無接縫。

```python
"<animation_name>": {
    "slots": {
        # 確保所有部位都顯示（attachment timeline 第 0 幀）
        "head":     {"attachment": [{"name": "head"}]},
        "body_up":  {"attachment": [{"name": "body_up"}]},
        # ...其他部位
    },
    "bones": {
        # 軀幹整體上下浮動 = 呼吸感
        "main": {
            "translate": [
                {"time": 0.0, "y":  0},
                {"time": 1.0, "y": -2},  # 吸氣（沉下）
                {"time": 2.0, "y":  2},  # 呼氣（浮起）
                {"time": 3.0, "y":  0},
            ]
        },
        # 手臂微擺（增加生氣）
        "main_arm_L": {"rotate": [{}, {"time": 1, "angle": 2}, {"time": 2, "angle": -3}, {"time": 3}]},
        "main_arm_R": {"rotate": [{}, {"time": 1, "angle": -2}, {"time": 2, "angle": 3}, {"time": 3}]},
    }
}
```

**設計原則**：
- duration ≥ 2 秒（呼吸節奏自然）
- 所有 timeline 頭尾值相同 → loop 無接縫
- 振幅小（±2~5px translate、±3° rotate）→ 不誇張

---

## Pattern 2：節奏舞步（左右搖擺）

「3 frame loop 跳舞」—— 軀幹側傾 + 手臂推收 + 頭點。

```python
"Fg_Main_Dance_Storyboard": {
    "slots": { ... 標準顯示設定 ... },
    "bones": {
        # 整體下沉 + 重心 L/R
        "main": {"translate": [
            {"time": 0.0, "x":   0, "y": -3},
            {"time": 0.8, "x":  -8, "y": -2},
            {"time": 1.6, "x":   8, "y": -2},
            {"time": 2.4, "x":   0, "y": -3},
        ]},
        # 肩膀跟身體傾斜
        "bady_up": {"rotate": [
            {"time": 0.0, "angle":  0},
            {"time": 0.8, "angle":  4},
            {"time": 1.6, "angle": -4},
            {"time": 2.4, "angle":  0},
        ]},
        # 手臂推/收
        "main_arm_L": {"rotate": [
            {"time": 0.0, "angle":  0},
            {"time": 0.8, "angle": -15},   # F2 外推
            {"time": 1.6, "angle":   8},   # F3 內收
            {"time": 2.4, "angle":   0},
        ]},
        "main_arm_R": {"rotate": [ ...鏡像... ]},
    }
}
```

**設計原則**：
- 3 frame + loop（4 keys 總計）足夠表達節奏感
- 對稱動作必定鏡像 sign：arm_L = -15° 對應 arm_R = +15°
- 振幅控制在 ±15~20°（不超過合理範圍）

---

## Pattern 3：Frame-by-frame 特效（attachment 切幀）

「劍光殘影 11 幀切換」—— slot.attachment timeline 連續切。

```python
"sword_glow_00": {
    # 11 個 attachment 在 0.4 秒內依序顯示
    "attachment": [
        {"time": 1.3333, "name": "sword_glow_00"},
        {"time": 1.3667, "name": "sword_glow_01"},
        {"time": 1.4000, "name": "sword_glow_02"},
        {"time": 1.4333, "name": "sword_glow_03"},
        {"time": 1.4667, "name": "sword_glow_04"},
        {"time": 1.5000, "name": "sword_glow_05"},
        {"time": 1.5333, "name": "sword_glow_06"},
        {"time": 1.5667, "name": "sword_glow_07"},
        {"time": 1.6000, "name": "sword_glow_08"},
        {"time": 1.6333, "name": "sword_glow_09"},
        {"time": 1.6667, "name": None},          # null = 隱藏（特效結束）
    ],
    # 可選：搭配 color tint（飽和度漸變）
    "color": [{"color": "ffffff97"}],
}
```

**設計原則**：
- 每幀間隔約 33ms（30fps 等效）為佳
- 結尾用 `null` 隱藏（不留最後一張定住）
- attachment 名稱必須對應 skin 內已定義的 attachment key

---

## Pattern 4：隱藏配件（武器消失）

「跳舞時暫時不要顯示劍」—— slot.attachment 設 null。

```python
"slots": {
    "sword":         {"attachment": [{"name": None}]},  # 武器隱藏
    "sword-glow":    {"attachment": [{"name": None}]},
    "sword_glow_00": {"attachment": [{"name": None}]},
    # ...其他正常顯示...
}
```

**使用時機**：動畫期間角色不該拿武器（如跳舞、待機某些 idle 變體）。注意 bone 還在動，但 attachment 不顯示就「看不到」武器。

---

## Pattern 5：Color 漸變（淡入淡出）

「整支動畫期間某個 slot 顏色變化」。

```python
"sword-glow": {
    "color": [
        {"time": 0.0,    "color": "ffffff00", "curve": "stepped"},   # 透明
        {"time": 0.6667, "color": "ffffff00", "curve": 0.191, "c3": 0.742},  # 還透明（Bezier ease in）
        {"time": 1.3333, "color": "ffffffff", "curve": 0.191, "c3": 0.742},  # 漸亮到全白
        {"time": 2.0,    "color": "ffffff00"},                                # 漸暗回透明
    ]
}
```

**color 格式**：8 字 hex `"RRGGBBAA"`，最後 2 字是 alpha（00 透明、ff 不透明）。

---

## Pattern 6：搭配多 bone 的協同（轉身 / 變身 crossfade）

兩套骨架（如 normal + hit）的 crossfade 切換。

```python
"Fg_Main_transform": {
    "slots": {
        # normal state 整套淡出
        "Hit_arm_L": {
            "color": [
                {"color": "ffffff8e", "curve": 0.191, "c3": 0.742},
                {"time": 0.1333, "color": "ffffff00"},   # 0.13s 內 fade out
            ],
            "attachment": [
                {"name": "Hit_arm_L"},
                {"time": 0.1333, "name": None},          # fade 完隱藏
            ],
        },
        # ...其他 Hit_ slots 同樣 crossfade...
        # normal slots 在 0.1333s 後顯示
        "arm_L": {"attachment": [{"time": 0.1333, "name": "arm_L"}]},
    }
}
```

**設計原則**：
- 同時操作多 slot 的 color + attachment 達成「淡出 A、淡入 B」
- 時間點集中（如 0.0~0.13s 內完成 crossfade）效果最戲劇化

---

## Pattern 7：Bezier easing（讓動作更流暢）

「線性 curve 太機械，要加緩動」。

```python
"main_arm_L": {
    "rotate": [
        {"time": 0.0, "angle": 0,
         "curve": 0.191, "c3": 0.742},      # ← 從這一幀到下一幀用 Bezier
        {"time": 1.0, "angle": 30,
         "curve": 0.25, "c2": 0.1, "c3": 0.75, "c4": 1.0},   # 自訂 Bezier
        {"time": 2.0, "angle": 0},          # 最後一幀通常不需要 curve（無下一幀）
    ]
}
```

**標準 Spine 緩動**：`{"curve": 0.191, "c3": 0.742}` = ease-in-out（最常見）

**Bezier 控制點對照**（cx1, cy1, cx2, cy2）：
- (0.25, 0.1, 0.25, 1) — ease（CSS 標準）
- (0.42, 0, 0.58, 1) — ease-in-out
- (0.42, 0, 1, 1) — ease-in
- (0, 0, 0.58, 1) — ease-out

---

## 加新動畫的標準步驟

```python
import copy, json

data = json.loads(open(spine_json_path).read())

new_anim = {
    "slots": { ... copy.deepcopy(slot_overrides) ... },
    "bones": { ... copy.deepcopy(bone_timelines) ... },
}

# 防呆：不覆蓋已存在的動畫
if anim_name in data["animations"]:
    raise RuntimeError(f"{anim_name} already exists")

# 防呆：確保引用的 bone / slot 都存在
bone_names = {b["name"] for b in data["bones"]}
slot_names = {s["name"] for s in data["slots"]}
for bn in bone_timelines:
    assert bn in bone_names, f"unknown bone: {bn}"
for sn in slot_overrides:
    assert sn in slot_names, f"unknown slot: {sn}"

data["animations"][anim_name] = new_anim
open(spine_json_path, "w").write(json.dumps(data, ensure_ascii=False, indent=2))
```

完整範本：`assets/patch_templates/add_animation.py`。

---

## 驗證新動畫的方法

跑 `validator_v0.py`：
```
python validator_v0.py spine.json spine.atlas
```

預期：
- `RESULT: valid` 或最多繼承自原檔的 typo warning
- 0 error
- `bones=<N> slots=<M> animations=<+1>`

進 Cocos 後：
- 在 `sp.Skeleton._animationIndex.enumList` 看到新動畫條目
- defaultAnimation 設為新動畫名能正常播放
- 切回既有動畫播放結果視覺不變（回歸測試）
