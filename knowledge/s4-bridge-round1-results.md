# S4 Codex bridge 第一輪結果與驗收 (chunk 309, 2026-11-06)
使用者本機跑 bridge(model gpt-6.1-sol),6 張任務 5 成功、1 失敗;結果 `chunk60/filled/`、驗收 `chunk60/verify/`(report.json、montage.png、composed/、decisions.json)。

## 結果
| 件 | bridge | 閘 | 目視 | 決定 |
|---|---|---|---|---|
| head | done | boundary_gap 0.28 → fail | 臉側/耳/頸延伸自然;紅標殘洞都在 choker/肩線真實輪廓 | **accept(目視覆核)** |
| sleeve_left | done | boundary_gap 0.24、grad_ratio 1.26 → fail | 紗袖下擺延續自然 | **accept(目視覆核)** |
| skirt | done | 1b pass(edge → None) | 佳 | accept |
| leg_left | done | 1b 不適用 → None | 膚色延伸合理 | accept |
| tails_mass | done | 無洞、tone_gap 50(白毛偏亮)→ None | 1b 寬鬆閘可接受;殘洞 168px nearest 自動補 | accept |
| leg_right | **failed**(image tool sexual-content filter 拒絕「大腿皮膚」) | — | CPU nearest/telea/ns 皆拉出靴色褐帶 | reject → 第二輪換措辭 |

**Codex 保住黑區逐像素不變(black_region_MAE 全 0)**:它用腳本做遮罩內編輯,不是整圖重生。

## 閘的教訓(第 5 次 miscalibration 類)
- 外推任務的遮罩是「寬鬆延伸帶」,bridge 只在合理輪廓內畫、其餘留透明是**正確**行為 → `alpha_gap` 不能當硬門檻(head 0.57 目視佳)。改為 `boundary_gap`(貼原輪廓 4px 帶的透明率)後仍有誤擋(真實輪廓貼著 choker/手)。
- 結論:**外推任務的自動閘只能擋粗錯(沒畫/噪聲/尺寸錯/貼邊大洞),品質判定靠目視**;判定最多到 None(需目視),目視覆核寫進 `decisions.json`,不再調門檻追 sample(避免過擬合 5 個樣本)。
- `s4_apply_fills.py` 依 decisions 把合成寫回切件(重算 tight bbox/offset)→ `cut_sam_v4_filled/` → `jiuwei_yanlian_decompose_v5_filled.psd`(19 層)。

## 第二輪任務包(todo 3 張)
01_tails_mass 髮遮擋增量 12664 px(ref = 第一輪合成)、06_leg_right 換措辭、07_hair_main 7797 px。pull 時用 `--round 2` → `filled_round2/`,驗收 `--filled-dir ... --bridge-dir`(須指向該輪 ref;ref 版本隨 git commit 追溯)。
