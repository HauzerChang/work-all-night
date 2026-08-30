# S4 候選 4:LaMa(深度 inpaint)可行性探測

> 分支 `claude/spine-s4-inpainting`,2026-08-30(chunk 16)。承接 `handoff_S4.md`/`STATE_S4.md`
> 列的候選 4:「LaMa 等深度 inpaint 權重下載是否被網路政策擋?」。工具:
> `tools/mesh_gen/s4_lama_probe.py`(一次性 probe,不進 production pipeline)。

## 背景

`knowledge/s4-inpaint-evaluator.md` 量化出 CPU baseline(nearest / cv2.inpaint)在機械細節
紋理材質(`身體`/`左手`)1a 嚴格標準下任何洞尺寸皆 fail(ssim 上限 ~0.51)。候選 4 要回答
兩個問題:(1) 這條路網路/環境上走不走得通;(2) 若走得通,深度 inpaint 是否真能把這些案例
拉過 1a 門檻。

## 1. 網路政策探測(結論:部分允許,非全擋)

| host | 用途 | 結果 |
|---|---|---|
| `pypi.org`(預設 index) | `torch` wheel(526MB)、`simple-lama-inpainting` | ✅ 可下載,速度正常(526MB/21s) |
| `github.com` releases | `big-lama.pt` 模型權重(196MB,`simple-lama-inpainting` 預設來源) | ✅ 可下載 |
| `download.pytorch.org` | PyTorch 官方 CPU-only wheel index | ❌ `403 Forbidden`(proxy CONNECT 失敗) |
| `huggingface.co` | 常見模型 hub(LaMa 的另一個常見權重來源) | ❌ `403 Forbidden`(proxy CONNECT 失敗) |

**重要副作用**:因為 `download.pytorch.org` 被擋,只能從預設 PyPI 裝 `torch`——而預設 PyPI
的 `torch` wheel 預設帶一整包 NVIDIA CUDA 依賴(cublas/cudnn/cufft/nccl/triton…),即使本機
純 CPU 推論用不到,仍會多裝 ~2GB(`nvidia-cusparse`/`nvidia-cublas` 等單顆就 100~400MB)。
若真要採用,應改用 PyPI 上的 `torch==<ver>+cpu` 專屬 CPU wheel(通常仍在
`download.pytorch.org` 才有完整版本矩陣,但也有部分版本鏡像在 PyPI 本身,需要屆時另外確認
哪個版本組合可用)。**誠實結論**:能力上「裝得起來」,但目前唯一可行路徑會多付 ~2GB CUDA
依賴的代價,不是乾淨的 CPU-only 安裝。

## 2. 實際跑分(結論:比 CPU baseline 好一些,但仍過不了 1a 門檻)

用 `simple-lama-inpainting`(封裝好的 `big-lama.pt` TorchScript,advimman/lama 官方權重,
**未針對本專案素材微調**)對已知 1a fail 的機械紋理材質(機器人拆件 `身體`/`左手`,
`frac=0.12`,與既有 baseline 同一組挖洞參數,直接可比)跑分:

| 材質 | mode | 指標 | nearest | cv2_telea | cv2_ns | **LaMa** | THRESH(1a) |
|---|---|---|---:|---:|---:|---:|---:|
| 身體 | interior | ssim | 0.330 | 0.423 | 0.441 | **0.574** | >0.75 |
| 身體 | interior | premult_mae | 20.7 | 24.1 | 21.3 | **9.2** | <18.0 |
| 身體 | interior | seam_grad_diff | 28.6 | 27.8 | 27.4 | **22.3** | <12.0 |
| 左手 | interior | ssim | 0.140 | 0.190 | 0.177 | **0.260** | >0.75 |
| 左手 | interior | premult_mae | 69.4 | 66.4 | 67.4 | **57.7** | <18.0 |
| 左手 | interior | seam_grad_diff | 107.0 | 112.9 | 109.6 | **76.4** | <12.0 |
| 身體 | edge | ssim | 0.324 | 0.427 | 0.407 | **0.553** | >0.75 |
| 左手 | edge | ssim | 0.136 | 0.201 | 0.215 | **0.253** | >0.75 |

**核心結果**:LaMa 在 6/8 個指標上贏過全部 3 個 CPU baseline(ssim 更高、premult_mae/
seam_grad_diff 更低),`身體` 的 ssim 從 CPU 最佳 0.441 提升到 0.574(+30%),`左手` 的
premult_mae 從 CPU 最佳 66.4 降到 57.7。**但沒有一個案例跨過 1a 門檻**(`ssim>0.75` 全部
仍 fail,`左手` 離門檻還差得遠)。1b(防穿幫)標準下兩者本來就已經 pass(見
`s4-inpaint-1b-lenient-gate.md`),LaMa 也 pass,但不構成新增益——1b 這條線 CPU baseline
已經解決,不需要 LaMa。推論速度:CPU 推論 0.6~1.9 秒/件(432×425px 級別),速度本身不是問題。

## 誠實結論與建議

1. **網路政策不是本專案 LaMa 路線的阻礞**——GitHub release + 預設 PyPI 都通,只是要接受
   CUDA 依賴的安裝代價(或後續評估 PyPI 上是否有乾淨 CPU-only 版本)。
2. **但通用預訓練 LaMa 本身不足以解決 1a 嚴格標準**:它是穩定的量化改善,不是質變——在
   本專案的機器人拆件機械紋理材質上,遷移沒微調的通用權重離 1a 門檻仍有明顯差距
   (尤其 `左手` ssim 0.26 對比門檻 0.75)。要用 LaMa 真正解 1a,大機率需要針對本專案
   素材家族微調(fine-tune),這是全新的、成本高得多的工作項,超出「探測可行性」的範圍。
3. **對照候選 8/1b 的既有結論**:1b(防穿幫)才是本專案的實戰驗收線,而 1b 用 CPU
   baseline 已經 pass 機械紋理材質——LaMa 在當前優先序下**不建議投入**(裝置成本 ~2GB
   依賴 vs 換不到任何新增益,因為唯一可能受益的 1a 嚴格標準仍過不了)。
4. **不建議寫進 `requirements.txt`**:`torch`/`simple-lama-inpainting` 僅用於這次一次性
   探測,不進日常排程環境(避免每個 session 都重裝 ~2GB)。`tools/mesh_gen/s4_lama_probe.py`
   保留作為未來若決定投入微調路線的起點,但其對 `simple_lama_inpainting`/`torch` 的
   import 延遲到 `main()` 內,不裝這兩個套件也不影響其他 S4 工具的 import。

## 何時該重新評估

- 若之後真的走到情境 2(視角外推,需要生成式內容)——那本來就需要比 LaMa 更強的生成式
  模型(如擴散模型),LaMa 這條線的探測結果對那個情境沒有直接參考價值(LaMa 是修補既有
  紋理,不是生成新視角內容)。
- 若 1a 嚴格標準真的成為某個實際交付情境的硬需求(目前判斷 1b 已足夠),再評估「微調
  LaMa on 本專案素材」的成本是否划算,而不是直接套用通用權重。

## 復現

```bash
pip install torch simple-lama-inpainting   # 見上方 CUDA 依賴代價說明
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/slices
python3 tools/mesh_gen/s4_lama_probe.py /tmp/slices/03_身體.png /tmp/slices/04_左手.png \
  --modes interior edge
# 對照組:
python3 tools/mesh_gen/inpaint_eval.py /tmp/slices/03_身體.png /tmp/slices/04_左手.png \
  --modes interior edge
```
