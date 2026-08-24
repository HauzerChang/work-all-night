# S1 分鏡 → 動畫 keyframe(storyboard → Spine animations)+ 自我品質閘

- **結論**:把 `analyze_target` 的 #3 分鏡(beats: In/Loop/Out,每件帶 role)用「角色參數化」的
  **確定性規則**轉成 Spine 3.8 `animations`(bone rotate/translate/scale + slot color alpha),
  寫回 `build_spine` 產出的 `skeleton.json`,讓素材從「setup 可載入」升級為「會動」。
  純 CPU、無 ML;配套評估器閘 `validate_animation.py`(9 檢查 + 4 負對照)自主驗收。
- **信心**:高(9 檢查全 PASS;4 負對照各被指定檢查抓到 → 閘有鑑別力;round-trip 回歸仍 PASS)。
- **階段**:第 2 階段 / S1(STATE 候選 0d,session 004 定的最高優先「讓素材會動」)。
- **工具**:`tools/analyzer/build_animation.py`(產出)、`tools/analyzer/validate_animation.py`(閘)。

## 標準指令
```
python3 tools/analyzer/build_spine.py     assets/robot_parts.psd                       # setup 素材
python3 tools/analyzer/build_animation.py assets/robot_parts.psd specs/robot_parts_spine  # 寫入 animations
python3 tools/analyzer/validate_animation.py specs/robot_parts_spine --selftest        # 閘 + 負對照
```
`--selftest` 會先斷言生成動畫 PASS,再注入 4 種壞況斷言各被抓到。

## 角色 → 動作規則(確定性)
| role | Loop(待機,無縫循環) | In(入場) | Out(退場) |
|---|---|---|---|
| body | 呼吸 scale ±3% + 微上抬 ty | 彈入 0.2→1.1 overshoot→1,墜入 ty | 縮到 0.05 |
| head | 微點頭 rotate −2° + ty 2 | 隨身回正 scale/rotate | 縮出 |
| limb | 末梢擺盪 rotate ±6°,**左右相位相反** | 大幅甩入 rotate ±45°→0 + 位移 | 縮出 |
| 特效 | 脈動 scale ±5% + 緩轉 ±3° + slot alpha 1→0.7→1 | 炸開 scale 0→1.3→1 + alpha 0→1 | 收斂淡出 alpha→0 |

- 曲線:ease-in-out 緊湊 bezier(`curve/c2/c3/c4` 散鍵,對齊 3.8 慣例)。
- Loop 首尾同值 → 可 seamless 循環;兩肢 t=0 rotate 反號 → 破除紙板同步感。

## 校準真值(定「合理待機」量化帶)
量自真實 slot loop `main_draw_loop`:身體 scale 變化 ~6%、hand rotate peak-to-peak ~10°、循環 ~0.67s。
據此設閘帶:body 呼吸 scaleVar ∈ [0.005, 0.12]、limb 擺盪 rotPP ∈ [2°, 25°]、head ≤ 8°、loop 時長 ∈ [0.3, 2.0]s。

## 評估器閘(`validate_animation.py`)9 檢查
C1 完整性(每件 bone 在 In/Loop/Out 皆有 timeline)· C2 Loop 無縫(首尾同值)·
C3 角色幅度(落校準帶且非零)· C4 相位錯開(兩肢反號)· C5 In 大動作且末幀回 neutral ·
C6 Out 塌陷(scale≈0 或 alpha≈0)· C7 非退化(**scale==0 僅在首/末 keyframe 合法**=不可見邊界;
中段 scale≤0=塌陷、負 scale=翻面、NaN、>5 才判退化)· C8 世界位移(FK 折算 px:Loop 細微、In 顯著)·
C9 loop 時長 sanity。

負對照(4/4 抓到):零運動→C3/C4/C8;斷 loop 縫→C2/C8;中段 scale=0→C7;缺件→C1。

## 驗收結果
| 標的 | 件數 | 檢查 | 世界位移(Loop/In) | 判定 |
|---|--:|---|---|---|
| robot_parts | 5 | 9/9 PASS + selftest 4/4 | 40 / 491 px | PASS |
| Symbol_Ww | 18 | 9/9 PASS | 12 / 121 px | PASS |

## 誠實界定
- 閘驗的是**動畫的幾何/結構品質**(會動、無縫、幅度合理、不退化),**非藝術手感**
  (緩動舒服度、重量感)——後者主觀,依 RULES 留給使用者。
- **角色語意近似**:role 由 genre-prior 對件名推定。對大獎主角(robot)合理;對非角色符號
  (Symbol_Ww:墨鏡/框/音符 被歸 limb)只保證「結構有效、會動」,語意分派不保證最佳。
- FK 世界位移用**剛體單骨變換**(件綁單一 bone,parent=root)——確定性正確,
  不涉及 mesh deform;故不受「stress_field 未校準」那條雷點影響(那是 mesh 變形閘的事)。
- 未做:真實 Spine runtime 回放(CDN 被政策擋);mesh deform 動畫(窗簾式);多檔位 tier 變體展開。
