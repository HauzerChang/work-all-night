# spine-ai-editor 2.0 — B4 序列組合入口(compose / crossfade / loop)+ 序列層雙真值閘

> 2026-10-14 run 005(排程主線 = 產出 spine-ai-editor 2.0;MERGE_PLAN Phase **B4**)。承 B1(橋接閘)/
> B2(單 beat 生成入口)/B3(繞關節 pivot)。把 repo 的**跨 beat 序列組合**抽成 skill 入口,並在**序列層**
> 機械化驗 G2 雙真值 —— **MERGE_PLAN 指名的「G1 真正戰場」,本 run 以實測把 B1 的假設關掉**。

## 做了什麼(全新增,無改任何生成/產線值)

1. **skill 入口** `skills/spine-ai-editor/assets/gen_lib/sequence.py`(承 make_beat 的 `_wire_repo_tools`/
   `_assemble_skeleton`/`DEMO_PARTS`/`IDLE_DEMO_PARTS`,包 repo `gen_animations` 的序列函式成對外契約):
   - `build_beat_library(parts, beats)` → `(skel_scaffold, anims)`:一次 `build_animations` 產出所有獨立 beat clip。
   - `seal_sequence(skel, anims, order, mode, xf, ramp, apply_g1)` → 把 order 以 compose/crossfade 串成**單一**
     composed animation,塞回獨立 skeleton,**過 G1**(deepcopy scaffold,可對同一 library 反覆 seal)。
   - `compose_bigwin_sequence(parts, order)` → 純時間平移+接點去重的**一次性**大獎序列 `In→hit→combo→charge→cascade→Loop→Out`。
   - `crossfade_bigwin_sequence(parts, order, xf, ramp)` → 接點重疊 xf 秒 + C1 斜坡混合(smoothstep → 相異接點 C1 連續)。
   - `compose_idle_loop(parts, repeats)` → Loop 重複 N 次串成 **loopable** idle 序列(首==尾)。
   - `write_sequence(parts, out, mode)` + CLI(`--mode compose/crossfade/idle`、`--self-test`)。
2. **序列層雙真值閘** `tools/analyzer/validate_b4_sequence.py`(5 AC;從 skill 公開 API 生成 → subprocess 呼叫
   **真正的** v1.3.0 `validator_v1`)。
3. `gen_lib/__init__.py` 匯出 B4 入口;`tools/check_readiness.py` 新增 cap `b4_sequence`。

## 為什麼這個 chunk 有價值(序列層 = 「X 就緒 ≠ 產線成立」在組合層的實例)

各 beat 單獨過 validator_v1(B2)**不等於**串成序列仍過。B1 的洞見明記:`_bez` 只 curve `frames[:-1]`,
**單 beat 末鍵恆乾淨 → G1 的真正風險在序列 compose/crossfade**(相鄰 beat 接點去重可能把某段的 outgoing
curve 推到 timeline 末鍵 → 地雷 #12,runtime 不炸、editor 匯入 AIOOBE crash)。B4 把序列生成固化成對外契約,
並在序列層驗 G2 雙真值(遊戲能播 **且** 編輯器能匯入)。

## 關鍵發現 — B1 的「G1 真正戰場」假設被實測關掉:此生成器家族序列層**結構上 editor-safe**

**compose 與 crossfade 的多 beat 序列,末鍵 curve 實測恆 0**,原因是結構性的、非巧合:

1. **compose 接點去重『丟前者尾幀、保留後者首幀』** —— 前者尾幀必為該 clip 之末,而 `_bez` **從不** curve
   clip 末鍵 → 去重永遠丟「乾淨幀」;且序列最末幀 = 最後一個 beat 的末幀(亦乾淨)→ **compose 末鍵 curve 恆 0**。
   (序列內部仍保有各 beat 的 bezier——實測 28 條內部 curved 幀,**皆非末位**,editor 不炸。)
   > 注:candidate (L) 選「丟前者尾幀、留後者首幀」是為了**回切逐幀還原**(Spine 緩動掛起點幀,留後者首幀=保正確
   > outgoing curve)。這個「無損方向」的選擇**同時**保證了 editor-safe(丟掉的永遠是乾淨末幀)—— 一箭雙鵰。
2. **crossfade 把序列重取樣成純線性關鍵幀**(`crossfade_sequence` 只寫值、不寫 curve/c2/c3/c4)→ **末鍵 curve 恆 0**
   (同 B3 密網格重取樣 → 純線性 → 天生 editor-safe)。

即 **G1 在序列層拔 0 條**。閘仍**過 G1**(防禦縱深)並以**手動注入接點末鍵 curve 的負對照**證 validator_v1
抓得到地雷 #12(AIOOBE)→ 閘非恆真。**B1 假設(序列層才觸發地雷 #12)就此關掉:此家族的 compose(無損去重方向)
與 crossfade(純線性重取樣)兩條組合路徑都結構上不觸發。真正仍需 G1 的,會是未來引入「保留帶 curve 的末鍵」的
新組合器(目前沒有)。**

## 5 AC(全 PASS;真實 robot 骨架替身 = IDLE_DEMO_PARTS 5 件,standalone 無 PSD)

- **B4-1 entrypoint+schema**:`compose_bigwin_sequence` / `crossfade_bigwin_sequence` 經**公開 API** 產出 schema
  合法完整 Spine JSON(**單一** composed animation;validator_v1 底層 v0 0 schema error;非臨時腳本)。
- **B4-2 sequence editor-import 0 error**:compose 與 crossfade 的**多 beat 序列**皆過 validator_v1 **0 error**
  (含末鍵 curve 地雷 #12 檢查)→ 序列層遊戲能播 且 編輯器能匯入;序列層末鍵 curve **實測 0**(compose 內部
  28 條 bezier 皆非末位、crossfade 0 條=純線性)。
- **B4-3 distinct-beat junction C1**:純接續(compose 介面)`is_c1_continuous_sequence`==**False**(C0 全 0 無縫
  但每接點 C1 kink 15~114:In→hit 114/hit→combo 87/combo→charge 109/charge→cascade 33/cascade→Loop 15/
  Loop→Out 15,**非因 C0**);crossfade+**smoothstep** `is_c1_crossfade_sequence`==**True**(每接點閉式 kink 0);
  **linear** 斜坡==**False** → 證 **C1 斜坡(w'(0)=w'(1)=0)才是消 kink 的鑑別子**,非 crossfade 本身。
- **B4-4 loopable endpoints + stiffness 不升**:Loop beat `is_c1_loopable`==True;**Loop×2** 序列 validator_v1
  loop 閉合 **0 問題**(首==尾,首尾可接 Loop);crossfade 序列 stiffness **3.98** ≤ compose 序列 **29.53**
  → crossfade 接點平滑 → **stiffness 不升反降(~7×)**。
- **B4-5 roundtrip + G1 wired + 負對照**:`write_sequence` 寫檔→重讀→validator_v1 0 error(端到端到可載入檔);
  注入接點末鍵 curve → validator_v1 **抓到** editor-crash(AIOOBE)、預設 apply_g1=True → 乾淨(且 apply_g1=False
  亦乾淨=結構本就 editor-safe,證「拔 0」是實測非未跑);破壞 Loop 閉合 → loop 閘**抓到**開環。閘非恆真。

## 迭代踩雷(預算內自修)

初版閘對大獎序列傳 `--loop-anims Idle_Loop`(想「大獎序列非 loopable → 不做 loop 檢查」)→ stiffness 回 null。
根因:**validator_v1 的 `--metric` 與 loop 檢查共用 `loop_anims` 過濾**(validator_v1.py L71 `if loop_anims is
not None and aname not in loop_anims: continue`),傳不存在的 anim 名會把 metric 一起跳過。**修法:大獎一次性序列
不傳 --loop-anims**(取得 stiffness;其「首尾不閉合」是 warning 非 error、且一次性序列本就不該閉合,不 gate);
只對 **idle 序列** 傳 `--loop-anims` 檢 loop 閉合。

## honest boundary

- **beat 排序 / 哪些接點該平滑 / xf 多長**屬美術手感(A 類 PROPOSAL):大獎離散節拍的「撞擊感」本是設計,
  本 run 只客觀化機制(compose 可串接、crossfade+C1 斜坡可消 kink、crossfade 不升 stiffness),不替使用者決定套用策略。
- **Cocos / viewer 實機載入 = 使用者端**(排程 scope 邊界);本閘用 spine-webgl 無頭等價(validator_v1)替代。
- **序列層 editor-safe 是對目前兩個組合器(compose 去重 / crossfade 重取樣)成立**;若未來加「保留帶 curve 的
  末鍵」的新組合器,G1 就會真的拔到東西——本 run 把 G1 留在流程裡正是為此(防禦縱深)。
- 過渡期 import repo `tools/analyzer`(Phase E1 bundle 進 assets/ 後 standalone);單一真值資產(robot 替身)。
- cap `b4_sequence` L2 併入 `spine-anim-forge`(仍 HOLD:生成能力為手感先驗,未學自真值)。

## 檔案

- `skills/spine-ai-editor/assets/gen_lib/sequence.py` — B4 skill 入口(新)。
- `tools/analyzer/validate_b4_sequence.py` — B4 序列層雙真值閘(5 AC,新)。
- `skills/spine-ai-editor/assets/gen_lib/__init__.py` — 匯出 B4 入口。
- `tools/check_readiness.py` — 新增 cap `b4_sequence`。

相關:`knowledge/s2-v2-bridge-b1.md`(B1 橋接閘,提出「G1 真正戰場在序列」假設)、`s2-v2-genlib-b2.md`(B2 單 beat 入口)、
`s2-v2-pivot-b3.md`(B3 繞關節 pivot)、`s1-sequence-composition.md`(L compose)、`s1-sequence-crossfade.md`(L-6 crossfade)、
`s1-sequence-seam-c1.md`(L-5 相異接點 C1)、`s1-sequence-loop-c1.md`(L-4 自接點 C1)。
