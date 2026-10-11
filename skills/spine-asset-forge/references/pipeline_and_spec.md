# spine-asset-forge — 產線與五段規格參考

> 本檔是 `spine-asset-forge` skill 的背景參考:輸入契約、五段需求規格格式、產線各步輸出、
> round-trip 保真閘判讀。真相以 repo `tools/` 的實際程式與 `check_readiness.py` 輸出為準。

## 1. 輸入契約

- **理想輸入 = 分層 PSD**:每個可動件/特效一層。PSD-first 契約讓整條 CPU 產線可自動化:
  切件、遮擋分析、補圖判定都靠圖層邊界,無需 GPU 影像理解。
- **平面(未分層)圖**:`segment_flat` 只能給 baseline——**同材質語意召回 ≈ 0**(CPU 到頂,需 GPU
  或人工)。這是**誠實負結果**,也是「要分層 PSD」契約的依據,不是本 skill 的自動能力。

## 2. 五段需求規格(`analyze_target` 產出)

以 `robot_parts.psd`(713×693,slot_bigwin)為例:

1. **運動構件(可動件)** — 每件:z 序、bbox、面積、質心。
2. **周邊特效分類** — 每件判「特效 vs 結構」+ 子類(如 glow/radial)+ 結構角色(body/head/limb)。
   分數為幾何/位置啟發式;角色分類目前是**輸入**(honest boundary),非全自動。
3. **動作腳本 / 分鏡(先驗提案)** — 依 genre 先驗(如 slot_bigwin 的 In/Loop/Out × 檔位)列每件每 beat
   的動作。**狀態 = PROPOSAL**:運動基元為手感先驗,緩動美感屬 A 類(留使用者),本 skill 不承諾動畫生成。
4. **拆圖策略(交付規格)** — 每件:slot 命名(`<檔名>/<圖層名>`)、切法(獨立件 + padding)、
   **region vs mesh** 建議(軟邊/大面積/易形變 → mesh)、pivot 提示。
5. **遮擋 / 露出 / 補圖分析** —
   - 5A 露出區:運動移開後露出、下層已完整 → 知會 rigger,不需補圖。
   - 5B 補圖候選(封閉破洞):分層完整時通常 0 破洞 → PSD-first 契約成立。

## 3. 產線各步輸出

| 步 | 工具 | 輸入 | 輸出 |
|---|---|---|---|
| 反推 | `analyze_target.py` | 分層 PSD | 五段規格(dict) |
| 切件 | `psd_slice.py` | PSD | 各件 PNG + `manifest`(offset/size/slot) |
| mesh | `generate_mesh_v2.py` | 件 PNG | strip mesh(vertices/uvs/triangles/hull);預設 rows=10 cols=3 = 30v |
| 組裝 | `build_spine.py` | PSD(呼叫上三者) | `skeleton.json` + atlas + png + `build_meta.json` |

**mesh 設計要點(來自 S3 研究)**:
- v1 散點 Delaunay 靜態 IoU 高但**真實 deform 會自交**(curtain_right / shadow)→ 不通用。
- **v2 strip** 對 4 mesh 全 deform 乾淨 → 設為預設。
- **IoU 由 rows 決定、cols 不影響覆蓋率**(S3 關鍵副產)。

## 4. round-trip 保真閘(`validate_build.py`)判讀

| AC | 量什麼 | 門檻 |
|---|---|---|
| AC1 結構 | bones/slots/skins 完整、命名一致 | 無缺漏 |
| AC2 setup 重建 | setup pose 可由 json 重建 | pass |
| **AC3 round-trip 重組** | 件依 atlas+json 重組回畫布 vs 原圖像素誤差 | `premult_rgb_mae` / `alpha_mae` < 3.0 |
| **AC4 無孤兒** | slot↔attachment 一一對應 | `orphan_ratio` ≈ 0 |

> round-trip 是本區塊達 **L3** 的關鍵:不只「長得像」,而是**切出去能無損組回來**,
> 證明 slot/atlas/uv/offset 全鏈一致。

## 5. 未涵蓋(走別的區塊 / skill)

- **會動**(animation timeline、主秀 beat、cascade、tier 變體):`spine-anim-forge`(HOLD,生成器未達 L3)
  / 落地 Cocos 走 `spine-ai-editor`。
- **weighted mesh + BBW 權重**:`spine-weighted-forge`(達門檻,另備套件)。
- **rig / 關節 pivot / 父子樹**:`spine-rig-pivot`(HOLD,缺多 rig 真值)。
- **變形品質體檢**(會不會破):`spine-mesh-doctor`。

## 6. Spine 3.8 地雷(詳見 repo CLAUDE.md)

1. 命名空間:WebGL 在 `spine.webgl.*`,核心在 `spine.*`。
2. PMA 要對齊 Cocos:建貼圖的 `UNPACK_PREMULTIPLY_ALPHA_WEBGL` 要與 `drawSkeleton(skel,pma)` 一致。
3. unweighted mesh:`vertices.length == uvs.length`;hull 頂點排最前。
4. 緊湊 bezier:`{"curve":..,"c2":..,"c3":..,"c4":..}` 散鍵(本 skill 靜態素材不產動畫曲線,但讀寫 json 須知)。
