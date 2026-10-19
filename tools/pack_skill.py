# -*- coding: utf-8 -*-
"""pack_skill —— 把 skill 目錄打包成 `.skill` 交付檔(deterministic / reproducible)。

INSTALL.md 路線 B 的 `zip -r ../spine-ai-editor.skill .` 會因檔案 mtime 每次不同 →
產出的 zip 位元每次都變(binary churn 進版控)。本工具改用固定 date_time + 排序條目 +
排除 `__pycache__`/`*.pyc`,**同內容 → 同位元組**,可放心 commit 進 repo。

用法:
  python3 tools/pack_skill.py                       # 預設打包 spine-ai-editor
  python3 tools/pack_skill.py --skill spine-ai-editor --out skills/spine-ai-editor.skill

交付檔內部布局(解壓即是 skill 根,可直接丟進 Cowork / 複製進 plugin skills/):
  SKILL.md  INSTALL.md  MERGE_PLAN_2.0.md  references/...  assets/...
"""
from __future__ import annotations
import argparse
import os
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, ".."))

# 固定時戳(reproducible);1980-01-01 是 zip 最早可表示的日期。
_FIXED_DT = (1980, 1, 1, 0, 0, 0)
_EXCLUDE_DIRS = {"__pycache__", ".git"}
_EXCLUDE_EXT = {".pyc", ".pyo"}


def _iter_files(root):
    """回傳 (絕對路徑, zip 內相對路徑) 的排序列表,排除快取/編譯檔。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1] in _EXCLUDE_EXT:
                continue
            ap = os.path.join(dirpath, fn)
            rel = os.path.relpath(ap, root)
            out.append((ap, rel.replace(os.sep, "/")))
    return sorted(out, key=lambda t: t[1])


def pack(skill_dir, out_path):
    files = _iter_files(skill_dir)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    # deterministic:固定 date_time + 固定外部屬性 + 排序條目。
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ap, rel in files:
            with open(ap, "rb") as f:
                data = f.read()
            zi = zipfile.ZipInfo(rel, date_time=_FIXED_DT)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o644 & 0xFFFF) << 16  # 固定權限位 → 跨環境同位元
            zf.writestr(zi, data)
    return [rel for _, rel in files]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="spine-ai-editor",
                    help="skills/ 下的 skill 目錄名(預設 spine-ai-editor)")
    ap.add_argument("--out", default=None,
                    help="輸出 .skill 路徑(預設 skills/<skill>.skill)")
    args = ap.parse_args()

    skill_dir = os.path.join(_REPO, "skills", args.skill)
    if not os.path.isdir(skill_dir):
        raise SystemExit("skill 目錄不存在:{}".format(skill_dir))
    out_path = args.out or os.path.join(_REPO, "skills", args.skill + ".skill")

    rels = pack(skill_dir, out_path)
    size = os.path.getsize(out_path)
    print("打包完成:{}".format(out_path))
    print("  檔案數:{}  大小:{:,} bytes".format(len(rels), size))
    print("  條目(前 40):")
    for r in rels[:40]:
        print("    {}".format(r))
    if len(rels) > 40:
        print("    ...(+{} more)".format(len(rels) - 40))


if __name__ == "__main__":
    main()
