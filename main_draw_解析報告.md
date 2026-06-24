# `main_draw` Spine 解析報告

> Spine 3.8.99 / Cocos Creator 3.7.3 適用 · 解析對象：`main_draw.json` + `main_draw.atlas` + `main_draw.png`


## 1. 檔案總覽

| 項目 | 值 |
|---|---|
| Spine 版本 | 3.8.99 |
| Bones（骨頭）| 28 |
| Slots（插槽）| 40 |
| Skins（皮膚）| 1（`default`）|
| Animations（動畫）| 9 |
| Attachment 類型 | region×69, **mesh×4**, clipping×1 |

這是一支 slot game「開獎/主秀」動畫：紅色舞台**窗簾**、金色貓咪角色、爆炸光芒、星星、速度線、閃電等特效。其中**會變形的網格（mesh）只有窗簾與陰影**——這正是你要研究的部分。


## 2. Mesh 網格系統（重點）

### 2.1 mesh 與 region 的差別

`region` attachment 是一張**剛性矩形貼圖**，只能整張跟著骨頭平移/旋轉/縮放。
`mesh` attachment 則把貼圖切成一張**可變形的三角網格**：每個頂點都能獨立移動，於是能做出窗簾被拉開、布料飄動這類「形狀本身在變」的效果。

### 2.2 本檔的 4 個 mesh

| slot | atlas region | 控制 bone | 頂點數 | 三角形 | hull | edges | 綁骨頭? |
|---|---|---|---|---|---|---|---|
| `image/curtain_left` | `image/curtain_left` | `curtain` | 21 | 24 | 16 | 32 | 否 |
| `image/curtain_right` | `image/curtain_right` | `curtain` | 21 | 24 | 16 | 32 | 否 |
| `image/shadow` | `image/shadow` | `shadow_L` | 12 | 10 | 12 | 12 | 否 |
| `image/shadow2` | `image/shadow` | `shadow_R` | 12 | 10 | 12 | 12 | 否 |

> 注意：`shadow` 和 `shadow2` 兩個 slot 共用同一張 atlas region `image/shadow`，但各自是獨立的 mesh、由不同 bone（`shadow_L` / `shadow_R`）控制。

### 2.3 一個 mesh 的解剖 — 以 `curtain_left` 為例

Spine mesh attachment 由這幾個陣列組成，逐一說明：

**`width` / `height`** — 來源貼圖原始尺寸：
```
width=346, height=535
```

**`vertices`** — setup pose（初始）頂點座標，共 21 個點，格式 `[x,y, x,y, ...]`（本檔為**非綁骨頭**，所以是純座標）：
```
[5.09, 234.85, 5.09, 158.12, 5.09, 60.73, 5.09, -20.27, 5.08, -118.78, 5.09, -204.18] ...（共 42 值 = 21 點 × 2）
```
**`uvs`** — 每個頂點對應到貼圖上的紋理座標（0~1），長度與頂點數一致：
```
[1, 0.179, 1, 0.323, 1, 0.505, 1, 0.656, 1.0, 0.84, 1, 1] ...（共 42 值）
```
**`triangles`** — 把頂點連成三角面的索引，每 3 個一組，共 24 個三角形：
```
[12, 13, 14, 16, 14, 15, 12, 14, 16, 16, 15, 0, 17, 16, 0, 16, 11, 12] ...（共 72 個索引）
```
**`hull`** — 外框輪廓頂點數 = `16`，代表前 16 個頂點構成網格外緣，其餘為內部頂點。
**`edges`** — 編輯器顯示用的邊線（不影響運行渲染），共 32 條。

### 2.4 weighted（綁骨）vs unweighted — 本檔全是 unweighted

這是 mesh 最容易看錯的地方，務必記住辨別法則：

- **unweighted（自由網格）**：`vertices` 長度 = 頂點數 × 2，純 `[x,y]`。頂點變形只靠 `deform` timeline 直接改座標。**本檔 4 個 mesh 全屬此類**，最單純、最適合入門研究。
- **weighted / skinned（綁骨網格）**：`vertices` 是壓縮格式 `[骨頭數, boneIndex, x, y, 權重, ...]`，每個頂點跟著一根或多根骨頭加權移動。辨別法：`len(vertices) ≠ 頂點數×2`。

驗證：`curtain_left` 頂點數 21，vertices 長度 42，剛好 = 21×2 → 確認 unweighted。

### 2.5 `deform` timeline — mesh 怎麼「動」起來

光有 mesh 還是靜止的。讓頂點移動的是動畫裡的 `deform` timeline，它記錄**每個頂點相對 setup pose 的偏移量**（`vertices` 偏移陣列 + `offset` 起始位移 + `curve` 緩動）。

下表是每支動畫對各 mesh 做了幾個 deform keyframe：

| 動畫 | 長度 | curtain_left | curtain_right | shadow | shadow2 |
|---|---|---|---|---|---|
| `main_draw_close` | ~0.67s | 4 | 4 | – | – |
| `main_draw_comeout` | ~0.67s | 1 | 1 | – | – |
| `main_draw_hit` | ~0.67s | 1 | 1 | – | – |
| `main_draw_loop` | ~0.67s | 1 | 1 | – | – |
| `main_draw_open` | ~2.67s | 3 | 3 | 2 | 2 |
| `main_idle` | ~0.67s | 1 | 1 | 1 | 1 |
| `main_idle2` | ~1.00s | 6 | 6 | 5 | 5 |
| `main_idle3` | ~0.00s | 1 | 1 | 1 | 1 |
| `main_static` | ~0.00s | 1 | 1 | – | – |

可見**窗簾在 9 支動畫中全部都有變形**（開獎主軸就是拉開/收合窗簾），陰影則只在 `open / idle / idle2 / idle3` 跟著變形。`main_idle2` 的窗簾有 6 個 keyframe，是飄動最細緻的一支。

一個 deform keyframe 實際長相（`main_draw_close` 的 curtain_left 第 0 幀）：

```json
{ "time": 0, "offset": 0, "vertices": [-78.68, 20.89, -139.46, 24.33, -184.7, 21.77, -237.38, -35.64] ... (42 個偏移值) }
```
`vertices` 這串是「每個頂點要從 setup 位置偏移多少」，runtime 把它加到 2.3 的初始座標上算出該幀的網格形狀。


## 3. Bone 階層（28 根）
```
root
  └ curtain
    └ shadow
    └ shadow2
  └ main
    └ face
      └ bell
      └ eye
        └ eye_lift
        └ eye_right
    └ hand_lift
    └ hand_right
    └ tail
  └ shine
  └ shine2
  └ circle_light
  └ star
  └ star2
  └ speed_line
  └ speed_line2
  └ lignting
  └ lignting2
  └ lignting3
  └ lignting4
  └ cat-glow
  └ shadow_R
  └ shadow_L
  └ main_shadow
```

與 mesh 相關的關鍵骨頭：`curtain`（掌管左右窗簾兩個 mesh）、`shadow_L` / `shadow_R`（各掌管一個 shadow mesh）。


## 4. 動畫清單

| 動畫 | 長度 | 含 deform | 用途推測 |
|---|---|---|---|
| `main_draw_close` | ~0.67s | ✓ | 窗簾收合 |
| `main_draw_comeout` | ~0.67s | ✓ | 角色登場 |
| `main_draw_hit` | ~0.67s | ✓ | 命中/中獎 |
| `main_draw_loop` | ~0.67s | ✓ | 待機循環 |
| `main_draw_open` | ~2.67s | ✓ | 窗簾拉開（最長 2.67s） |
| `main_idle` | ~0.67s | ✓ | 待機 |
| `main_idle2` | ~1.00s | ✓ | 待機（窗簾飄動最細） |
| `main_idle3` | ~0.00s | ✓ | 待機變化 |
| `main_static` | ~0.00s | ✓ | 靜態定格 |

## 5. 研究建議

既然要重新研究 mesh，這支檔案是很好的入門教材：

1. **全是 unweighted mesh**，沒有綁骨複雜度，先把「vertices / uvs / triangles / hull / deform」這五件事吃透。
2. **從 `curtain_left` 下手**：21 點、24 三角形，規模剛好，又在每支動畫都有 deform，可以對照不同動畫看同一網格的形變差異。
3. **下一步若要自己加 mesh 變形**：注意純 JSON patch 可以改 deform 偏移值，但「新建 mesh 拓樸／綁骨」仍需 Spine 編輯器。
4. 想實際看效果可推進 Cocos Creator 預覽（這個 skill 有現成的 9 步推送流程）。
