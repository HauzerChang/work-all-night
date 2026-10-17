#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spine 3.8 Validator — v1（v0 全部檢查 + 動態品質檢查）

v0 之上新增（v1.1 實戰回饋）：
  ✓ loop 閉合：每條 bone timeline 首尾值一致、首鍵在 0、末鍵在時長處
  ✓ key 時間單調（v0 只查 bone timeline，v1 連 slot/deform 一起）
  ✓ 穿透式切線豁免：c2/c4 超出 [0,1] 改為 [info]（刻意過衝，Spine 支援）
    ——僅 cx（curve / c3）超界才是 error
  ✓ --metric：輸出每支動畫的 stiffness（key 處速度不連續量），
    修僵硬前後對照用

用法：
  python validator_v1.py Main.json [Main.atlas] [--metric] [--loop-anims A,B]
  （--loop-anims 不給時，對所有動畫做 loop 閉合檢查，
    非循環動畫如 win/transition 可用此參數縮小範圍）
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validator_v0 import validate as validate_v0   # noqa: E402
import curve_tools as ct                            # noqa: E402
import json                                         # noqa: E402


def run_checks(json_path, atlas_path=None, loop_anims=None, want_metric=False):
    """執行 v1 的全部檢查,回傳 (report, demoted, metrics) 供程式化消費。

    這是 `main` 與 `validator_v2`(統一品質閘 D1)共用的單一真相來源:
      report  : validator_v0 的 Report(errors/warnings/info,errors 已含 v1 的 cx 升級與末鍵 curve)。
      demoted : 被降級為 info 的穿透式切線過衝(cy 超界)warning 清單。
      metrics : {anim: stiffness}(want_metric=True 時才填)。
    `main` 只做參數解析 + 印出,行為與輸出逐字不變(B1 bridge 解析其 stdout,不可回歸)。
    """
    json_path = Path(json_path)
    atlas_path = Path(atlas_path) if atlas_path is not None else None

    # ---- v0 全套 ----
    r = validate_v0(json_path, atlas_path)

    # v1 調整：cx 超界升級 error、cy 超界降級 info（穿透式切線豁免）
    keep_warn, promoted, demoted = [], [], []
    for w in r.warnings:
        if 'outside [0,1]' in w and ('c2=' in w or 'c4=' in w):
            demoted.append(w)
        elif 'outside [0,1]' in w and ('curve=' in w or 'c3=' in w):
            promoted.append(w)
        else:
            keep_warn.append(w)
    r.warnings = keep_warn
    r.errors += [f'(v1) bezier cx 超出 [0,1]，runtime 會解錯: {p}' for p in promoted]

    # ---- 末鍵 curve（editor 匯入 crash，v1.1.1 新增，全動畫必查）----
    data = json.loads(json_path.read_text(encoding='utf-8'))
    for aname, anim in data.get('animations', {}).items():
        for sec in ('bones', 'slots'):
            for tname, tls in anim.get(sec, {}).items():
                for prop, fr in tls.items():
                    if isinstance(fr, list) and fr and isinstance(fr[-1], dict) \
                       and any(k in fr[-1] for k in ('curve', 'c2', 'c3', 'c4')):
                        r.err(f'(v1) {aname} {tname}.{prop}: 最後一鍵帶 curve — '
                              f'Spine editor 匯入 AIOOBE crash（index=(key數-1)*19），'
                              f'runtime 會忽略但編輯器過不了。用 curve_tools.strip_last_frame_curves() 清')

    # ---- loop 閉合 + 動態品質 ----
    metrics = {}
    for aname, anim in data.get('animations', {}).items():
        if loop_anims is not None and aname not in loop_anims:
            continue
        dur = ct.anim_duration(anim)
        if dur <= 0:
            continue
        for prob in ct.loop_closure_report(anim, dur):
            r.warn(f'(v1 loop) {aname}: {prob}')
        if want_metric:
            metrics[aname] = ct.stiffness_metric(anim, dur)

    return r, demoted, metrics


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    args = [a for a in argv[1:] if not a.startswith('--')]
    json_path = Path(args[0])
    atlas_path = Path(args[1]) if len(args) >= 2 else None
    want_metric = '--metric' in argv
    loop_anims = None
    if '--loop-anims' in argv:
        loop_anims = argv[argv.index('--loop-anims') + 1].split(',')

    r, demoted, metrics = run_checks(json_path, atlas_path, loop_anims, want_metric)

    # ---- 輸出 ----
    print(f'=== validator_v1 on {json_path.name} ===')
    for n in r.info: print(f'  [info] {n}')
    for d in demoted[:3]:
        print(f'  [info] 穿透式切線過衝（正常）: {d.split(":")[-1].strip()}')
    if len(demoted) > 3:
        print(f'  [info] …其餘 {len(demoted)-3} 條 cy 過衝豁免')
    for w in r.warnings: print(f'  [warn] {w}')
    for e in r.errors: print(f'  [ERR ] {e}')
    if want_metric and metrics:
        print('  --- stiffness（key 處速度不連續量，越低越順）---')
        for k, v in sorted(metrics.items(), key=lambda x: -x[1]):
            print(f'    {k:28s} {v:8.2f}')
    print()
    if r.is_valid:
        print(f'RESULT: valid  ({len(r.warnings)} warnings)')
        return 0
    print(f'RESULT: INVALID  ({len(r.errors)} errors, {len(r.warnings)} warnings)')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
