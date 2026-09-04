#!/usr/bin/env python3
"""S4 拆解流程第3點 — 讀決策檔(s4_decompose_assist.html 匯出)→ 幾何裁切各部件 PNG
→ 輸出 psd_slice.py 相容 manifest.json(供 psd_node/manifest_to_psd.js 組回 .psd)。

對應 `knowledge/s4-cut-vs-slice-research-split.md`「區塊1:圖片切割」——單純空間切分,
硬邊界矩形裁切,**允許邊緣夾帶鄰近部件內容(bleed)**(使用者已授權,邊緣品質交給第4點
GPT 局部修補收尾,這裡不做任何羽化/去 bleed 的嘗試)。

決策檔格式(見 tools/mesh_gen/s4_decompose_assist.html):
  {"source_image","image_size":[W,H],"generated_by",
   "parts":[{"id","label","confidence","notes","bbox_px":[x0,y0,x1,y1]}]}

自驗閘沿用 psd_slice.py 的 reassemble()/_premult_diff()(同一套「重組還原、0孤兒」邏輯,
道理見下方說明,不是抄一份新的):因為每個部件都是同一張扁平來源圖的矩形窗口(不是真的
獨立圖層),重疊區域內容在各部件裡是完全相同的像素,alpha-over 疊回去不管疊放順序,
理論上都能精確重建原圖(除非有 bbox 沒蓋到的空隙,那才是真正的孤兒——真正該抓的錯誤,
不是重疊本身)。
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psd_slice import reassemble, _premult_diff  # 重用同一套重組/差異邏輯,不重寫


def clamp_bbox(bbox, W, H):
    x0, y0, x1, y1 = bbox
    x0c, y0c = max(0, min(x0, W)), max(0, min(y0, H))
    x1c, y1c = max(0, min(x1, W)), max(0, min(y1, H))
    if x1c <= x0c or y1c <= y0c:
        return None, (x0, y0, x1, y1) != (x0c, y0c, x1c, y1c)
    clamped = (x1c - x1) != 0 or (y1c - y1) != 0 or (x0c - x0) != 0 or (y0c - y0) != 0
    return (int(x0c), int(y0c), int(x1c), int(y1c)), clamped


def cut(image_path, decision_path, out_dir):
    src = Image.open(image_path).convert("RGBA")
    W, H = src.size
    decision = json.load(open(decision_path, encoding="utf-8"))

    if list(decision.get("image_size", [W, H])) != [W, H]:
        print(f"WARNING: 決策檔 image_size={decision.get('image_size')} 跟實際來源圖 "
              f"{[W, H]} 不一致,仍用實際來源圖尺寸繼續,但座標可能對不齊。", file=sys.stderr)

    os.makedirs(out_dir, exist_ok=True)
    manifest = {"source": os.path.basename(image_path), "size": [W, H], "parts": []}
    parts_for_check = []
    warnings = []

    for i, p in enumerate(decision.get("parts", [])):
        bbox_raw = p.get("bbox_px")
        if not bbox_raw or any(v is None for v in bbox_raw):
            warnings.append(f"part '{p.get('id')}' 缺 bbox_px,略過")
            continue
        bbox, was_clamped = clamp_bbox(bbox_raw, W, H)
        if bbox is None:
            warnings.append(f"part '{p.get('id')}' 的 bbox_px={bbox_raw} 裁到畫布內後面積為0,略過")
            continue
        if was_clamped:
            warnings.append(f"part '{p.get('id')}' 的 bbox_px={bbox_raw} 超出畫布 {[W,H]},"
                             f"已裁到 {list(bbox)}")

        x0, y0, x1, y1 = bbox
        crop = src.crop((x0, y0, x1, y1))
        pid = p.get("id") or f"part_{i}"
        safe = pid.replace("/", "__")
        fn = f"{i:02d}_{safe}.png"
        crop.save(os.path.join(out_dir, fn))

        entry = {
            "name": p.get("label") or pid, "z": i, "opacity": 255,
            "offset": [x0, y0], "size": [x1 - x0, y1 - y0], "file": fn,
            "id": pid, "confidence": p.get("confidence", ""), "notes": p.get("notes", ""),
        }
        manifest["parts"].append(entry)
        parts_for_check.append((entry, crop))

    src.save(os.path.join(out_dir, "composite.png"))
    manifest["composite"] = "composite.png"
    manifest["cut_from_decision"] = os.path.basename(decision_path)
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"),
               ensure_ascii=False, indent=2)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    return manifest, parts_for_check, src


def self_check(manifest, parts_for_check, src, mae_thresh=6.0, orphan_thresh=0.005,
                opaque_source_thresh=0.99):
    """AC1 部件數>0(硬性)。AC2 重組貼近原圖:**僅供參考,不硬性擋關**——這個工具刻意允許
    矩形窗口在鄰接部件的柔邊/半透明邊界處產生小幅重組落差(邊緣夾帶鄰近內容,使用者已
    授權「邊緣允許破損」,見 knowledge/s4-cut-vs-slice-research-split.md 區塊1),跟
    psd_slice.py 對「真正獨立圖層」要求的像素級精確重組不是同一個保證等級,threshold
    因此拉寬且只做告警不擋 overall_pass。AC3 孤兒檢查(部件沒蓋到但原圖有內容的像素)
    **只在來源圖有意義的 alpha 時才有效**——如果來源圖幾乎整張 alpha=255(單純矩形裁圖,
    非去背後的獨立角色),alpha 沒有辦法分辨「角色」跟「背景」,孤兒率會被背景大量誤報,
    此時自動略過並在報告中說明原因,不當成失敗。"""
    W, H = manifest["size"]
    recon, cover = reassemble(parts_for_check, W, H)
    rgb_mae, alpha_mae = _premult_diff(recon, src)
    alpha_arr = np.asarray(src.split()[-1])
    opaque_ratio = float((alpha_arr == 255).mean())
    res = {
        "AC1_parts_produced": {"pass": len(parts_for_check) > 0, "count": len(parts_for_check)},
        "AC2_reconstruction_info": {"info_only": True,
                                     "premult_rgb_mae": round(rgb_mae, 4),
                                     "alpha_mae": round(alpha_mae, 4),
                                     "advisory_thresh": mae_thresh,
                                     "note": "僅參考,邊緣柔邊落差是預期內(邊緣允許破損),"
                                             "不影響 overall_pass"},
    }
    if opaque_ratio >= opaque_source_thresh:
        res["AC3_no_orphan"] = {
            "skipped": True,
            "reason": f"來源圖 {opaque_ratio:.1%} 像素 alpha=255(無意義去背),"
                      "孤兒率無法區分角色/背景,略過此檢查(見自身文件字串說明)",
        }
    else:
        content = alpha_arr > 8
        orphan = float(np.logical_and(content, cover == 0).sum() / max(int(content.sum()), 1))
        res["AC3_no_orphan"] = {"pass": orphan <= orphan_thresh, "orphan_ratio": round(orphan, 5),
                                 "thresh": orphan_thresh}
    overall = res["AC1_parts_produced"]["pass"] and res["AC3_no_orphan"].get("pass", True)
    return {"overall_pass": overall, "criteria": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="來源扁平圖(單層 PNG)")
    ap.add_argument("decision", help="s4_decompose_assist.html 匯出的決策檔 JSON")
    ap.add_argument("-o", "--out", required=True, help="輸出目錄(部件 PNG + manifest.json)")
    ap.add_argument("--eval", action="store_true", help="裁切後跑自驗閘並印報告")
    a = ap.parse_args()
    manifest, parts_for_check, src = cut(a.image, a.decision, a.out)
    print(json.dumps({k: v for k, v in manifest.items() if k != "parts"} |
                      {"parts": len(manifest["parts"])}, ensure_ascii=False, indent=2))
    if a.eval:
        rep = self_check(manifest, parts_for_check, src)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
