#!/usr/bin/env python3
"""validate_rules.py — 驗證 rules.json(結構 + 語意)。

用法: python3 validate_rules.py <rules.json> [--schema <rules.schema.json>]
- 有安裝 jsonschema 時跑完整 JSON Schema 驗證;否則跑內建結構檢查。
- 語意檢查(不論有無 jsonschema 都跑):
  S1 rowsPerReel 長度 == reels
  S2 ways: waysCount == Π rowsPerReel
  S3 lines: 每條線長度 == reels 且列索引在範圍內
  S4 symbol id 唯一;feature / trigger 引用的 symbol 存在
  S5 flow: initial / transitions 的 from、to 都在 states 中;每個 state 可從 initial 抵達
  S6 'feature:<id>' 形式的引用必須指向存在的 feature
  S7 multiplierLadder.ladder 遞增且 >= 1
離開碼: 0 = PASS, 1 = FAIL。
"""
import json, re, sys, os
from functools import reduce

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def basic_struct(r, errs):
    for k in ["schemaVersion", "game", "board", "evaluation", "symbols", "features", "flow"]:
        if k not in r:
            errs.append(f"缺少必要欄位: {k}")

def semantic(r, errs, warns):
    b, ev = r.get("board", {}), r.get("evaluation", {})
    rows, n = b.get("rowsPerReel", []), b.get("reels")
    if n is not None and len(rows) != n:
        errs.append(f"S1 rowsPerReel 長度 {len(rows)} != reels {n}")
    if ev.get("type") == "ways":
        prod = reduce(lambda a, c: a * c, rows, 1)
        if "waysCount" in ev and ev["waysCount"] != prod:
            errs.append(f"S2 waysCount {ev['waysCount']} != Π rowsPerReel {prod}")
    if ev.get("type") == "lines":
        for i, ln in enumerate(ev.get("lines", [])):
            if len(ln) != n:
                errs.append(f"S3 lines[{i}] 長度 {len(ln)} != reels {n}")
            for ri, row in enumerate(ln):
                if ri < len(rows) and row >= rows[ri]:
                    errs.append(f"S3 lines[{i}] 第 {ri} 軸列索引 {row} 超出 {rows[ri]}")
    ids = [s.get("id") for s in r.get("symbols", [])]
    if len(ids) != len(set(ids)):
        errs.append("S4 symbol id 重複")
    idset = set(ids)
    for s in r.get("symbols", []):
        for sub in s.get("substitutes", []):
            if sub not in idset:
                errs.append(f"S4 {s['id']}.substitutes 引用不存在的 symbol {sub}")
        for rr in s.get("reels", []):
            if n is not None and rr >= n:
                errs.append(f"S4 {s['id']}.reels 含超出範圍的軸 {rr}")
        if s.get("tbd"):
            warns.append(f"symbol {s['id']} 為 tbd 佔位")
    fids = {f.get("id") for f in r.get("features", [])}
    for f in r.get("features", []):
        sym = f.get("trigger", {}).get("symbol")
        if sym and sym not in idset:
            errs.append(f"S4 feature {f['id']} trigger.symbol {sym} 不存在")
        if f.get("type") == "multiplierLadder":
            lad = f.get("params", {}).get("ladder", [])
            if not lad or lad[0] < 1 or any(a >= c for a, c in zip(lad, lad[1:])):
                errs.append(f"S7 {f['id']}.ladder 需 >=1 且嚴格遞增: {lad}")
        if f.get("type") == "respin":
            for rr in f.get("params", {}).get("fullReelWild", []):
                if n is not None and rr >= n:
                    errs.append(f"S4 {f['id']}.fullReelWild 軸 {rr} 超出範圍")
    fl = r.get("flow", {})
    states = set(fl.get("states", []))
    init = fl.get("initial", "Idle")
    if init not in states:
        errs.append(f"S5 initial {init} 不在 states")
    adj = {}
    for t in fl.get("transitions", []):
        for k in ("from", "to"):
            if t.get(k) not in states:
                errs.append(f"S5 transition {t} 的 {k}={t.get(k)} 不在 states")
        adj.setdefault(t.get("from"), set()).add(t.get("to"))
        for txt in (t.get("on", ""), t.get("guard", "")):
            for ref in re.findall(r"feature:([A-Za-z0-9_]+)", txt or ""):
                if ref not in fids:
                    errs.append(f"S6 transition 引用不存在的 feature:{ref}")
    for f in r.get("features", []):
        for v in json.dumps(f.get("params", {}), ensure_ascii=False).split('"'):
            for ref in re.findall(r"^feature:([A-Za-z0-9_]+)$", v):
                if ref not in fids:
                    errs.append(f"S6 {f['id']}.params 引用不存在的 feature:{ref}")
    seen, stack = {init}, [init]
    while stack:
        for nx in adj.get(stack.pop(), ()):
            if nx not in seen:
                seen.add(nx); stack.append(nx)
    for s in sorted(states - seen):
        errs.append(f"S5 state {s} 從 {init} 無法抵達")
    for s in sorted(states):
        if s not in adj:
            warns.append(f"state {s} 沒有離開的轉移(死路)")
    if r.get("openQuestions"):
        warns.append(f"{len(r['openQuestions'])} 個待確認問題")

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(2)
    path = args[0]
    here = os.path.dirname(os.path.abspath(__file__))
    schema_p = args[args.index("--schema") + 1] if "--schema" in args else \
        os.path.normpath(os.path.join(here, "../../../schemas/rules.schema.json"))
    r = load(path); errs, warns = [], []
    try:
        import jsonschema
        v = jsonschema.Draft7Validator(load(schema_p))
        for e in v.iter_errors(r):
            errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message}")
        mode = "jsonschema"
    except ImportError:
        basic_struct(r, errs); mode = "builtin"
    semantic(r, errs, warns)
    print(f"[{mode}] {path}")
    for w in warns: print("  WARN", w)
    for e in errs: print("  FAIL", e)
    print("PASS" if not errs else f"FAIL ({len(errs)})")
    sys.exit(0 if not errs else 1)

if __name__ == "__main__":
    main()
