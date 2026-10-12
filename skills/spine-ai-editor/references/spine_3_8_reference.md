# Spine 3.8 JSON 結構快速參考

> 對應 Spine Runtime 3.8.99（最常見的 stable 版本，Cocos Creator 3.7.3 內建支援）

---

## Top-level keys

```json
{
  "skeleton": { "hash": "...", "spine": "3.8.99", "images": "./image/", "audio": "" },
  "bones": [ ... ],
  "slots": [ ... ],
  "skins": [ { "name": "default", "attachments": { ... } } ],
  "events": { ... },               // optional
  "animations": { ... },
  "ik": [ ... ],                   // optional
  "transform": [ ... ],            // optional
  "path": [ ... ]                  // optional
}
```

---

## Bones

```json
{
  "name": "main_arm_L",
  "parent": "bady_up",       // omitted if parent is root
  "x": 120.82,               // local position in parent's coords
  "y": 130.71,
  "rotation": 0,             // degrees, CCW positive
  "scaleX": 1,
  "scaleY": 1,
  "length": 0,               // visual aid, not transform
  "transform": "normal",     // ← inheritance mode!
  "color": "ffe500ff"        // optional, used in editor
}
```

### Transform inheritance modes

| Mode | Inherits from parent |
|---|---|
| `"normal"` (default) | translation + rotation + scale + shear |
| `"onlyTranslation"` | **only translation**（不繼承 rotation/scale）|
| `"noRotationOrReflection"` | translation + scale + shear (no rotation/reflection) |
| `"noScale"` | translation + rotation + shear (no scale) |
| `"noScaleOrReflection"` | like noScale + no reflection |

**最常用於 reparent**：`onlyTranslation`。例如把 head reparent 到 chest 之下，希望 head 跟 chest 一起位移但不繼承 chest 的 scale（否則 head 會被擠扁）。

---

## Slots

```json
{
  "name": "body_up",
  "bone": "main_chest",     // ← 哪個 bone 擔任此 slot 的 anchor
  "attachment": "body_up",  // setup pose 顯示的 attachment（null = 不顯示）
  "color": "ff9f0cff",      // optional tint
  "blend": "additive"       // optional: normal | additive | multiply | screen
}
```

**Slot 順序 = z-order**。陣列中越前面越底層。改 z-order 用 animations 內的 `draworder` timeline。

---

## Skins / Attachments

```json
{
  "name": "default",
  "attachments": {
    "<slot_name>": {
      "<attachment_key>": {
        "name": "<atlas_region_name>",  // omitted if same as attachment_key
        "type": "region",                // region | mesh | linkedmesh | boundingbox | path | clipping | point
        "x": 26.26, "y": 70.86,
        "rotation": 0,
        "scaleX": 1, "scaleY": 1,
        "width": 217, "height": 189
      }
    }
  }
}
```

**Region attachment** 是最簡單的：一張靜態圖切片，依 bone transform 走。

**Mesh attachment** 允許 vertex deform（真正的「胸口收回」效果需要 mesh + deform timeline），但需要 Spine editor 編輯，純 JSON patch 做不到。

**同一個 slot 可以有多個 attachment**（key 不同），動畫透過 `attachment` timeline 切換哪個顯示。

---

## Animations

```json
{
  "Fg_Main_Idle": {
    "bones": {
      "<bone_name>": {
        "rotate": [ { "time": 0, "angle": 0 }, ... ],
        "translate": [ { "time": 0, "x": 0, "y": 0 }, ... ],
        "scale": [ { "time": 0, "x": 1, "y": 1 }, ... ],
        "shear": [ ... ]
      }
    },
    "slots": {
      "<slot_name>": {
        "attachment": [ { "time": 0, "name": "<att_name>" }, ... ],  // null name = hide
        "color": [ { "time": 0, "color": "ffffffff" }, ... ]
      }
    },
    "draworder": [ { "time": 0, "offsets": [ ... ] } ],   // optional, z-order changes
    "deform": { "<skin>": { ... } },                       // optional, mesh deform
    "events": [ { "time": 0, "name": "<event_name>" } ]    // optional, fire events
  }
}
```

### Keyframe defaults

- 若 keyframe 缺 `time`，預設 0
- 若缺值（`angle`/`x`/`y`/etc.），預設**該 timeline 對應 bone setup pose 的值**
- 例：`{"rotate": [{}, {"time": 1, "angle": 5}]}` 第一個 key 等同 `{"time": 0, "angle": 0}`（assuming setup angle = 0）

---

## 緊湊 Bezier 格式（Spine 3.8 特色）

Spine 3.8 把 4 個 Bezier 控制點分散到 4 個鍵儲存：

```json
{
  "time": 0.333,
  "curve": 0.191,   // cx1
  "c2": 0,          // cy1 (省略 = 0)
  "c3": 0.742,      // cx2
  "c4": 1           // cy2 (省略 = 1)
}
```

對應 cubic Bezier `(cx1, cy1, cx2, cy2)`。**Validator/generator 必須支援這個分散儲存格式**，不能假設 curve 是 array。

| `curve` 值 | 意義 |
|---|---|
| 數字 | Bezier 第一個控制點 X，後面接 c2/c3/c4 |
| `"linear"` | 線性插值（也可以直接省略 curve 鍵）|
| `"stepped"` | 階梯（不插值，停在前一幀直到下一 key）|

---

## Atlas 檔結構

```
<page_name>.png
size: <W>,<H>
format: RGBA8888
filter: Linear,Linear
repeat: none
<region_name>
  rotate: false
  xy: <x>, <y>
  size: <w>, <h>
  orig: <ow>, <oh>
  offset: <ox>, <oy>
  index: -1
<region_name2>
  ...

<page_name_2>.png
size: ...
```

### 重要規則

- **多 page 用空白行分隔**。每個 page 開頭是 png 檔名
- **`xy` 是 atlas 內左上角座標**，y 軸**向下**
- **`rotate: true` 表示打包時旋轉 90°**，解碼時要 swap w/h
- **`orig` 是原圖真實大小**（去除 alpha trim 前），`size` 是 trim 後實際 region 大小
- **atlas page 引用必須對應實際 PNG 檔名**。改名 atlas 內的 page 名稱時，png 也必須同名

---

## Region 名稱 ↔ Attachment 名稱對應

```
slot "body_up" 的 attachment key = "body_up"
  → 該 attachment 的 "name" 鍵（若有）指向 atlas region
  → 若無 "name" 鍵，attachment key 本身 = atlas region name
```

```json
// 沒寫 name → atlas 內必須有 region "body_up"
"body_up": { "body_up": { "x": 26.26, "y": 70.86, ... } }

// 寫了 name → atlas 內必須有 region "body_up_v2"
"body_up": { "body_up": { "name": "body_up_v2", "x": 0, ... } }
```

---

## 一個 attachment 對應到 atlas 的完整 trace

```
JSON: skins.default.attachments.body_up.body_up
  → attachment_key = "body_up", name 省略 → region name = "body_up"
JSON: slots[i].name = "body_up", slot.bone = "main_chest"
  → 此 attachment 由 main_chest bone 控制 transform
Atlas: <page>.png 內找 region "body_up"
  → 取 xy / size / rotate / orig 渲染
```

走通這條 trace 就理解了 Spine 的「資料 → 視覺」管線。

---

## 結語

理解 Spine 3.8 JSON 不需要 Spine editor，**純讀 spec + 用 Python 試誤就能掌握**。本 skill 就是這個哲學的實作。
