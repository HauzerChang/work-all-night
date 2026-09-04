"""S4 候選17:獨立(不依賴 Photoshop)的 OpenAI images/edits 呼叫模組 + 用量記錄。

背景見 `knowledge/s4-gptfill-plugin-knowledge.md`(mask 慣例知識來源,非程式碼複製)、
`STATE_S4.md` chunk 34/35。這支模組只抽「mask+prompt→補圖」這個核心能力,**不含**插件的
五層像素對位管線(那是給「生成結果會漂移」這個問題用的,屬於候選17後續才要解的問題,見
`s4-gptfill-plugin-knowledge.md` 第3節)——先驗證核心能力本身對本專案素材有沒有用。

安全性:key 只能從環境變數 `OPENAI_API_KEY` 讀,絕不寫死、絕不記錄明文(log 只記 metadata)。

mask 編碼採 OpenAI 官方慣例(與插件一致):RGBA PNG,alpha 通道 **0 = 可編輯區,255 = 保留原樣**
(等於 `alpha = 255 - selection`,selection=1 表示要編輯)。
"""
import io
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid

import numpy as np
from PIL import Image

API_URL = "https://api.openai.com/v1/images/edits"
# 放在 tools/mesh_gen/(S4 工具目錄)而非 log/,以符合檔案隔離契約
# (log/ 只保留 s4-YYYY-MM-DD-NNN.md 這種單次 chunk 記錄;這支是持續累加的用量明細)。
USAGE_LOG = os.path.join(os.path.dirname(__file__), "s4_data", "openai_usage.jsonl")


def _rgba_to_png_bytes(rgba):
    arr = np.clip(rgba, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def _mask_to_png_bytes(mask_bool):
    """mask_bool: True = 要編輯的區域。轉成 OpenAI 慣例(alpha: 0=可編輯,255=保留)。"""
    h, w = mask_bool.shape
    alpha = np.where(mask_bool, 0, 255).astype(np.uint8)
    rgb = np.full((h, w, 3), 255, dtype=np.uint8)
    rgba = np.dstack([rgb, alpha])
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def _multipart_encode(fields, files):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    for name, (filename, content, ctype) in files.items():
        parts.append(
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
             f"Content-Type: {ctype}\r\n\r\n").encode() + content + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def _append_usage_log(record):
    os.makedirs(os.path.dirname(USAGE_LOG), exist_ok=True)
    with open(USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def edit_image(rgba, mask_bool, prompt, model="gpt-image-2", size="1024x1024",
               quality="low", tag=""):
    """呼叫 OpenAI images/edits。rgba: HxWx4 float/uint8 array(要編輯的完整畫布,通常是
    貼回真實場景上下文的裁切,不是孤立圖層——見 s4-gptfill-plugin-knowledge.md §4 的
    512px 上下文下限知識,呼叫端自行決定要不要套用)。mask_bool: HxW bool,True=要編輯。
    回傳 (edited_rgba 或 None, usage_record dict)。任何失敗都記錄進 usage log 再拋出,
    不靜默吞錯。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未設定(只讀環境變數,不接受硬編碼)")

    image_png = _rgba_to_png_bytes(rgba)
    mask_png = _mask_to_png_bytes(mask_bool)

    fields = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": "1"}
    files = {
        "image": ("image.png", image_png, "image/png"),
        "mask": ("mask.png", mask_png, "image/png"),
    }
    body, content_type = _multipart_encode(fields, files)

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tag": tag,
        "model": model,
        "size": size,
        "quality": quality,
        "prompt_chars": len(prompt),
        "image_px": f"{rgba.shape[1]}x{rgba.shape[0]}",
        "mask_coverage_pct": round(100.0 * mask_bool.sum() / mask_bool.size, 3),
    }

    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", content_type)

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            elapsed = time.time() - t0
            payload = json.loads(resp.read())
            record["http_status"] = resp.status
            record["elapsed_s"] = round(elapsed, 2)
            record["usage"] = payload.get("usage")
            _append_usage_log(record)
            b64 = payload["data"][0]["b64_json"]
            import base64
            out_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
            out_rgba = np.array(out_img).astype(np.float64)
            return out_rgba, record
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        body_txt = e.read().decode(errors="replace")
        record["http_status"] = e.code
        record["elapsed_s"] = round(elapsed, 2)
        record["error"] = body_txt[:500]
        _append_usage_log(record)
        raise RuntimeError(f"OpenAI API error {e.code}: {body_txt[:500]}") from e
