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

---

# v1.1 新增：loop 僵硬診斷與修復（實戰回饋）

以下 pattern 來自「待機 loop 動態僵硬」實戰修復，可重用程式全部收錄在
`assets/curve_tools.py`（import 即用）。先診斷再下藥：

| 症狀 | 成因 | Pattern |
|---|---|---|
| 節拍器感、機械重播 | key 全 linear（三角波：等速進出、極值瞬間反向） | 8a |
| 紙板感、全身一體搖 | 所有骨頭同刻到達極值（key 共用同一組時間網格） | 8b |
| 走走停停、每拍煞車 | ease-in-out 上在「連續揮動」的 timeline（每 key 速度歸零） | 9 |
| 末梢甩不開、僵直 | 鏈末端無振幅放大、或末節完全沒 key | 10 |
| 重心是死的 | 軀幹只有 rotate 沒有 translate（無 bounce） | 11 |

## Pattern 8：去同步僵硬（ease 化 + 環形相位平移）

```python
import curve_tools as ct

anim = data["animations"]["Idle"]
dur  = ct.anim_duration(anim)

LAG = {  # 幀 @30fps：駕駛骨 0，越末梢越慢
  "body": 0, "head": 2, "ear_root": 3, "ear_tip": 5,
  "hair_root": 3, "hair_mid": 5, "hair_tip": 7,
  "arm": 1, "hand": 3, "finger": 5,
}
for bone, tls in anim["bones"].items():
    lag = LAG.get(bone, 2) / ct.FPS
    for prop, frames in tls.items():
        ct.to_ease(frames)                                   # 8a
        tls[prop] = ct.phase_shift(frames, prop, lag, dur)   # 8b
```

要點：
- `phase_shift` 是環形平移：曲線先取值再平移，首尾自動閉合，不會 pop。
- lag 派發**照骨架層級**，同一條鏈內根→尾遞增才有鞭子感；
  不同鏈之間同 lag 沒關係（共享同一個 driver 是自然的）。

## Pattern 9：穿透式切線（修「走走停停」）

ease-in-out 的本質是每個 key 速度歸零 —— 對「擺動折返型」正確，
對「空中連續揮動型」（舉起的手、掃視的頭）就是生硬的來源。

```python
for bone in ("R_hand1", "R_hand2", "R_hand3"):
    fr = anim["bones"][bone].get("rotate")
    if fr: ct.catmull_smooth(fr, "angle", 0.0, dur)
```

- Catmull-Rom 過每個 key 算切線 → 轉 bezier，運動流過中間 key，
  只在真正極值減速；loop 邊界斜率也閉合。
- 產生的 c2/c4 會超出 [0,1]（過衝）——**刻意設計**，Spine runtime 支援；
  validator_v1 已對此豁免（info 不 warn）。
- 選擇依據：折返型（值 A-B-A 來回）→ Pattern 8 的 ease；
  連續型（值 A-B-C-D 掃過）→ 本 pattern。混用時以視覺回報為準。

## Pattern 10：follow-through（末梢誇張 + 衍生末節）

```python
for tip in ("ear_tip", "hair_tip"):                 # 振幅 ×1.1 繞均值
    for prop, fr in anim["bones"].get(tip, {}).items():
        ct.amp_gain(fr, prop, 1.10)

parent = anim["bones"]["R_hand2"]["rotate"]         # 沒 key 的末節：衍生
anim["bones"]["R_hand3"] = {
    "rotate": ct.derive_tip(parent, dur, gain=0.7, lag_frames=5)
}
```

## Pattern 11：軀幹重心 bounce（律動的根）

僵硬常常不是四肢的錯，是軀幹沒有重心運動 —— 四肢的擺動全掛在
「固定鐵架」上。給 body 一條 translate Y：

```python
A = 4.0                                   # px，保守起手
anim["bones"]["body"]["translate"] = [
    dict(ct.EASE, time=0.0,      x=0, y=0),
    dict(ct.EASE, time=dur*0.25, x=0, y=-A),
    dict(ct.EASE, time=dur*0.50, x=0, y=0),
    dict(ct.EASE, time=dur*0.75, x=0, y=-A),
    dict(ct.EASE, time=dur,      x=0, y=0),
]
```

- 節奏遊戲對齊 BPM：1.0s loop 兩次下沉 = 120 BPM。
- 搭配頭部反向 bob（+2 幀滯後、幅度 ~40%）脖子就活了。
- 胸腔呼吸：scale（脹縮）疊 translate（推擠），只有 translate 是「平移感」。
- 疊加前先看原檔胸口/身體的既有節奏（可能是 3Hz jiggle 而非慢呼吸），
  新 bounce 與既有頻率的關係（同步 or 複節奏）要在預覽時確認。

## 量化驗收（修復前後各跑一次）

```python
before = ct.stiffness_metric(anim_old, dur)   # key 處速度不連續量
after  = ct.stiffness_metric(anim_new, dur)   # 預期降 40%+
assert not ct.loop_closure_report(anim_new, dur)
```

或 `python validator_v1.py Main.json --metric`。
經驗參考：linear 三角波 ~30+；ease+相位後 ~15；殘餘多來自美術自訂
bezier（保留是對的）。時長放慢版數值天然更低，跨時長不要直接比。
