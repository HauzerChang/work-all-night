# 2.0 (B2) — gen_lib 生成庫入口:cascade/pop/wobble/twist → v1.3.0 `validator_v1`

> 排程主線 = **產出 spine-ai-editor 2.0**(2026-10-12 使用者拍板)。路線圖 `skills/spine-ai-editor/MERGE_PLAN_2.0.md`。
> 本篇 = **Phase B2**(承 B1)。入口:`skills/spine-ai-editor/assets/gen_lib/make_beat.py`;閘:`tools/analyzer/validate_b2_genlib.py`。

## 這個 chunk 在解什麼問題

B1(`validate_v2_bridge.py`)證明了「repo 的**一支** cascade beat」能過 v1.3.0 `validator_v1`——但 skeleton 是在閘裡
**臨時**組的,流程沒有對外介面。B2 把那條流程抽成**可重用的 skill 層級入口**,並涵蓋 4 種大獎單件運動基元,
讓「用 skill 生成大獎節拍 → 雙真值驗收」成為一條固定、可機讀的對外契約(MERGE_PLAN Phase B2)。

## 做了什麼(純新增,無改任何既有生成/產線值)

1. **`assets/gen_lib/` 套件**(skill 層級生成入口):
   - `make_beat.py`:公開 API `generate_bigwin(parts, beat=...)` / `write_bigwin(...)` / `parts_from_psd(...)`,
     + CLI(`--beat`/`--out`/`--psd`/`--cascade-*`/`--self-test`)。內建 `DEMO_PARTS`(5 件機器人,無需 PSD 即可示範)。
   - `__init__.py`:對外匯出。
   - 支援 beat:**cascade / pop / wobble / twist**(`SUPPORTED_BEATS`)。"pop" = cascade 的單件運動基元 → 走 cascade 預設(pop)波。
2. **G 護欄內建**:輸出前一律過 **G1**(`curve_tools.strip_last_frame_curves`,地雷 #12);**G3** 從零生成新 skeleton 不碰既有檔。
3. **過渡期相依**(MERGE_PLAN 明列):`make_beat` 透過 `_wire_repo_tools()` 路徑 shim import repo `tools/analyzer`
   (`gen_animations.build_animations` + beat_templates + tier_variants);**G5 的 self-contained bundle 留 Phase E1**。
4. **Pattern 12** 寫進 `references/animation_patch_patterns.md`(確定性大獎生成 SOP:何時用、4 基元、生成/驗證清單、地雷)。
5. **閘** `validate_b2_genlib.py`(5 AC,透過**公開 API** 生成、subprocess 跑真正的 validator_v1)。

## 5 AC(全 PASS,真實 DEMO robot 骨架)

- **B2-1 entrypoint+schema**:`generate_bigwin(DEMO_PARTS,"cascade")` 經公開 API 產 schema 合法完整 Spine JSON(5 bone/1 effect slot,v0 0 schema error);證非臨時腳本。
- **B2-2 four-beat-import**:cascade/pop/wobble/twist **四種**皆經同一入口 → `validator_v1` **0 error**(含末鍵 curve 地雷 #12 檢查)→ 遊戲能播 **且** 編輯器能匯入。
- **B2-3 loop-closure**:四 beat(皆首尾 identity 的 pop/shear 波)loop 閉合 **0 問題**。
- **B2-4 stiffness**:validator_v1 --metric 回報 **cascade 16.46 / wobble 62.16 / twist 107.05**(有限可量)。
- **B2-5 roundtrip+G1+負對照**:
  - `write_bigwin` 寫檔 → 重讀 → validator_v1 **0 error**(證 skill 流程端到端到「可載入檔」);
  - **G1 wired**:`apply_g1=False` 生成後注入末鍵 curve → validator_v1 抓到 `b_body.scale 最後一鍵帶 curve`(AIOOBE);入口預設 `apply_g1=True` → 輸出乾淨;
  - 破壞首尾 identity(開環)→ loop 閉合抓到 `b_body.scale.y: open loop 1.0 != 1.5`。
  - → 證此閘非恆真,且 G1 確實是入口的一環。

## 關鍵發現

1. **「用 skill 生成 → 雙真值驗收」可固化成對外契約**:不再每次手搭 skeleton。`generate_bigwin`/`write_bigwin`
   是一條穩定、可機讀 pass/fail 的流程,4 種 beat 類型一致適用。
2. **4 beat 類型全過 editor 真值閘**:cascade/pop/wobble/twist 經同一入口 + G1,validator_v1 全 0 error、loop 閉合全過。
   (reveal 入場波因首幀 collapsed 本就不該過 loop 閉合,故不納入 SUPPORTED_BEATS 的 loopable 承諾——留 B4 以 `--loop-anims` 排除驗。)
3. **stiffness 有通道差異**:scale 脈衝(cascade 16.46)< shear 晃動(wobble 62.16)< 雙軸 shear 扭轉(twist 107.05);
   數值是量化指標非品質判準(不同通道/幅度天然不同,勿跨 beat 直接比)。
4. **B1 的 G1 洞見在 B2 延續**:單 beat 下 repo `_bez` 只 curve `frames[:-1]`,故 G1 通常拔 0 條;
   末鍵 curve 的真正風險仍在**序列 compose/crossfade**(Phase B4)——B2 只把單 beat 入口的 G1 關卡機械化。

## honest boundary

- **viewer / Cocos 實機載入 = 使用者端**(排程 scope 邊界):排程純 CPU 無 Cocos,用 `validator_v1`(spine-webgl 無頭等價)
  + `validate_b2_genlib` 替代;最終視覺確認在 `spine-viewer.html` / Cocos 由使用者完成。AC「在 spine-viewer.html 可載入播放」
  的 CPU 可自主部分(schema 合法 + editor 可匯入 + loop 閉合)已過,實機播放待使用者端。
- **過渡期相依 repo tools**:`gen_lib` 目前 import repo `tools/analyzer`;純使用者端 standalone 須等 **E1** bundle。
- **哪個 beat / 多爆 / 多快屬美術手感**(A 類 PROPOSAL):入口只給確定性結構(跨件錯開、阻尼振盪、首尾 identity 介面)。
- 單一真值資產(DEMO robot / robot_parts)。

## 回歸

`check_readiness` 新增 cap `b2_genlib`(L2,role=pipeline,併入 `spine-anim-forge` 仍 HOLD);既有閘不受影響(純新增檔 + 純新增 gen_lib 套件,未改 gen_animations/curve_tools/validator_v1 任何值)。
