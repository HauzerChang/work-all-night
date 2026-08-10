# Cocos Creator MCP 推送與預覽 SOP

> 把改好的 Spine JSON 推進 Cocos Creator 編輯器，並讓使用者立刻在 preview 看到結果。

---

## 適用 MCP

- **DaxianLee/cocos-mcp-server**（推薦，158 tools）
- RomaRogov/cocos-mcp（已停止維護，但仍能用基本功能）
- 任何相容 mcp-spec 的 Cocos editor MCP

連線方式通常是 Streamable HTTP，預設 URL `http://127.0.0.1:3000/mcp`。

---

## 完整 9 步流程

### Step 1：覆寫 JSON 資產

```typescript
// MCP 工具
mcp__plugin_cocos-creator-mcp_cocos-creator__assetAdvanced_asset_operations
  action: "create"
  url: "db://assets/aiSpine/new_spine/new_spine.json"
  overwrite: true
  content: <minified JSON string>
```

**Tips**：
- JSON 內容要先 **minify**（用 `json.dumps(d, separators=(',', ':'))`），不然 50KB pretty-printed 會超過工具 input 限制
- `overwrite: true` 必填，不然回 "already exists" error
- url 必須以 `db://assets/` 開頭

### Step 2：Refresh asset DB

```typescript
mcp__plugin_cocos-creator-mcp_cocos-creator__assetAdvanced_asset_system
  action: "refresh"
  folder: "db://assets/aiSpine/new_spine"
```

讓 Cocos 重新 parse 已覆寫的 spine 資產。**沒這步 sp.SkeletonData 不會更新**。

### ⚠️ Step 3-5：補設 sp.Skeleton 屬性（救命三步）

`asset_system.refresh` 會 **重置 sp.Skeleton 的下面屬性為預設值（多數 false）**：

| 屬性 | 預設 | 通常要設 |
|---|---|---|
| `loop` | `false` | `true`（多數動畫要 loop） |
| `premultipliedAlpha` | `false` | `true`（Spine 預設 PMA） |
| `useTint` | `false` | `true`（若 spine 有 color timeline） |

**忽略這三步 = 動畫只播一次 + additive blend 看起來不對 + color tint 失效**。

```typescript
mcp__plugin_cocos-creator-mcp_cocos-creator__component_set_component_property
  nodeUuid: "<Skeleton node UUID>"
  componentType: "sp.Skeleton"
  properties: {
    "loop":               { "type": "boolean", "value": true },
    "premultipliedAlpha": { "type": "boolean", "value": true },
    "useTint":            { "type": "boolean", "value": true }
  }
```

可以與 Step 6 合併成單次 batch call。

### Step 6：設 defaultAnimation

```typescript
mcp__plugin_cocos-creator-mcp_cocos-creator__component_set_component_property
  nodeUuid: "<Skeleton node UUID>"
  componentType: "sp.Skeleton"
  property: "defaultAnimation"
  propertyType: "string"
  value: "<new_animation_name>"
```

進 preview / 編輯器都會用這個 default 播放。

### Step 7：Save scene

```typescript
mcp__plugin_cocos-creator-mcp_cocos-creator__scene_scene_management
  action: "save"
```

不存場景的話下次重開 Cocos defaultAnimation 設定會掉。

### Step 8：Sanity check console

```typescript
mcp__plugin_cocos-creator-mcp_cocos-creator__debug_debug_console
  action: "get_logs"
  filter: "error"
  limit: 10
```

預期 0 error。若有錯通常是：
- "spine version mismatch"（罕見，3.8 vs 3.7 通常相容）
- "atlas region not found"（spine.json 引用了不存在的 region）
- "Cannot read property ... of undefined"（spine 結構錯，validator 漏抓）

### Step 9：請使用者預覽

回報模板：

```
✅ 部署完成。請預覽：

1. 動畫名：<animation_name>
2. 預期視覺：<具體描述，如「劍尖微擺 ±2°」「胸甲下沉 7px」>
3. 驗證點：
   - <要看到的東西 1>
   - <要看到的東西 2>
   - <回歸測試：切回 Fg_Main_Idle 應與之前一致>

如果視覺不對，告訴我看到什麼，我這邊可以快速調整：
- 振幅過大/過小 → 改值
- 方向反了 → 翻 sign
- 時序不對 → 改 keyframe time
```

---

## 一次完成的 batch call 範例

把 Step 3-6 合併：

```python
# 在 sp.Skeleton node 上批次設 4 個屬性
mcp__plugin_cocos-creator-mcp_cocos-creator__component_set_component_property
  nodeUuid: "<uuid>"
  componentType: "sp.Skeleton"
  properties: {
    "defaultAnimation":   { "type": "string",  "value": "Fg_Main_Dance_Storyboard" },
    "loop":               { "type": "boolean", "value": true },
    "premultipliedAlpha": { "type": "boolean", "value": true },
    "useTint":            { "type": "boolean", "value": true }
  }
```

---

## 結構變更（加 bone）後的特殊處理

若 patch 涉及 **結構變更（bones 新增 / slot.bone 改）**，Cocos 需要重新 parse skeleton 整份結構：

```
1. asset_operations.create (overwrite)
2. asset_system.refresh
3. ⚠️ 用 component_query 驗證 _animationIndex.enumList 是否包含所有預期動畫
   - 若 enumList 數量不對（少於 JSON 內 animations 數）→ 結構 parse 有問題
   - 重試 refresh，或檢查 JSON 是否有語法錯
4. ... 後續同 Step 3-9
```

---

## 場景初始化（首次掛 Spine 節點）

完整建一個含 Spine 的 Cocos 2D 場景：

```python
# 1. 建場景
scene_management.create(sceneName="aiSpine", savePath="db://assets/aiSpine/aiSpine.scene")
scene_management.open(scenePath="db://assets/aiSpine/aiSpine.scene")

# 2. 建 Canvas
canvas_uuid = node_lifecycle.create(
    name="Canvas",
    components=["cc.Canvas", "cc.UITransform", "cc.Widget"]
)

# 3. 建 Camera（必須是 ortho 2D，不然 UI 不顯示）
camera_uuid = node_lifecycle.create(
    name="Camera",
    parentUuid=<scene_root_uuid>,
    components=["cc.Camera"]
)
component_set_component_property(
    nodeUuid=camera_uuid,
    componentType="cc.Camera",
    properties={
        "projection":  {"type": "integer", "value": 0},          # ORTHO
        "orthoHeight": {"type": "number",  "value": 819},        # 半螢幕高
        "visibility":  {"type": "integer", "value": 1107296256}, # UI_2D + DEFAULT
        "clearFlags":  {"type": "integer", "value": 7},          # SOLID_COLOR
        "clearColor":  {"type": "color",   "value": {"r":30,"g":30,"b":40,"a":255}},
        "far":         {"type": "number",  "value": 2000},
        "near":        {"type": "number",  "value": 0.1}
    }
)

# 4. 把 Camera 接到 Canvas.cameraComponent
# ⚠️ 這裡 value 要傳 NODE UUID（不是 component UUID）
component_set_component_property(
    nodeUuid=canvas_uuid,
    componentType="cc.Canvas",
    property="cameraComponent",
    propertyType="component",
    value=camera_uuid  # ← NODE UUID
)

# 5. 建 Spine 節點（child of Canvas）
spine_uuid = node_lifecycle.create(
    name="FgMainStage",
    parentUuid=canvas_uuid,
    components=["sp.Skeleton"]
)

# 6. 設 skeletonData + animation
component_set_component_property(
    nodeUuid=spine_uuid,
    componentType="sp.Skeleton",
    properties={
        "skeletonData":       {"type": "asset",   "value": "<spine_data_uuid>"},
        "defaultSkin":        {"type": "string",  "value": "default"},
        "defaultAnimation":   {"type": "string",  "value": "Fg_Main_Idle"},
        "loop":               {"type": "boolean", "value": True},
        "useTint":             {"type": "boolean", "value": True},
        "premultipliedAlpha": {"type": "boolean", "value": True}
    }
)

# 7. Save scene
scene_management.save()
```

---

## 已知 MCP bugs / workarounds

| Bug | Workaround |
|---|---|
| `node_transform` 寫 position 回 "Cannot use 'in' operator" | 用 cc.UITransform 改 anchor/contentSize，或建節點時用 `initialTransform` |
| `cameraComponent` 雖然 `propertyType: "component"`，但 value 要傳 NODE UUID | 記住這條反直覺規則 |
| Cocos 版本標籤回 "Unknown"（asset_system.get_comprehensive_status） | 不擋事，但確認 spine runtime 版本要靠載入測試 |

---

## 結語

Cocos MCP 是把「JSON patch + 視覺驗證」的迴圈從 5 分鐘縮到 30 秒的關鍵。但 MCP 有自己的怪癖（refresh 副作用、property type 反直覺、若干 tool bug），這份 SOP 把已知地雷都標出來。

**鐵則**：每次 patch + refresh 後一定補設 loop / PMA / useTint。漏一次調試 10 分鐘。
