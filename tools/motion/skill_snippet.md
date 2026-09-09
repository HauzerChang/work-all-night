# 給 spine-motion-skill 的補充章節（可直接貼進 SKILL.md）

> 這段描述本 repo 的軌跡工具鏈與它產出的 `motion spec` 契約。
> skill 讀到一份 `spine-motion-spec/1` 的 JSON，就知道「使用者要調什麼、預期會變成怎樣、怎麼驗」。

## 工具化的第 2–6 步

skill 的標準流程第 2–6 步（世界座標取樣 → 分離自身位移 → 量化 → 設計新 timeline → 寫入驗證）
已有工具實作，不必每次重寫腳本：

```bash
python3 tools/motion/analyze_trajectory.py --json <Main.json> --anim <動畫> \
    --bone <目標骨骼> --body <主體骨骼> --out out/traj.json --csv out/07_對照表.csv
# → 瀏覽器開 spine_trajectory_editor.html 調曲線，匯出 spec
python3 tools/motion/apply_motion_spec.py --spec out/<新動畫>.spec.json --write
```

`apply_motion_spec.py` 寫檔前會跑 skill 第 6 步的完整驗證清單（V1–V7）加三條量化閘（Q1–Q3），
**未全過不寫檔**；輸出可直接抄進回覆。

## motion spec 契約（`spine-motion-spec/1`）

| 欄位 | 意義 |
|---|---|
| `source` | 來源 JSON / 動畫 / fps / 總長 / 幀數 |
| `target.bone` `target.point` | 目標骨骼與**追蹤點**（骨骼原點對 rotate-only 配件不動，預設取 attachment 中心） |
| `body.bone` `body.beats` `body.periodFrames` | 主體骨骼、節拍幀、擺動週期 |
| `edit.keys` | **世界座標**的自身位移關鍵幀 `{frame, wx, wy, curve}`（curve = 3.8 緊湊 bezier 散鍵 / `"stepped"` / 省略=線性） |
| `edit.lag` `edit.scale` `edit.scaleX` `edit.scaleY` | 四個旋鈕：延後幀數、整體幅度、各軸幅度（以震盪中心縮放，靜止偏移不變） |
| `edit.resolvedKeys` | 套完旋鈕、處理完迴圈邊界後的關鍵幀（工具已算好，可直接讀） |
| `predicted` | 編輯器預測的世界軌跡（Q1 用它與實測比對，證明「畫的」==「做出來的」） |
| `metrics.before/after` | 幅度、相關、相位的前後對照，可直接寫進回覆 |
| `skill.notes` | 需主動告知使用者的副作用（例如互補導致世界總幅縮小） |

## 這條迴路守住的 skill 底線

- **分析先於修改**：spec 一定帶 `metrics.before`，是從實測軌跡算出來的，不是估的。
- **主體逐 byte 不變**：V2 只允許目標骨骼有差異；V4/V5/V6 保證原動畫、skins、其他動畫沒被碰。
- **總長不變**：V1 + V7（V7 以**原**總長為準）；跨迴圈邊界的段用 de Casteljau 切開，
  t=0 與 t=總長 放同一內插值 → loop 無縫。
- **幅度與時間差分開**：`lag` 只改 time；`scale` 以震盪中心縮放，靜止偏移不動。
- **自身位移的正確定義**：`actual = rigid + rotOwn + transOwn`，可回寫 translate 的只有 `transOwn`；
  拿總量回寫會把 rotate 的貢獻重複計入。
