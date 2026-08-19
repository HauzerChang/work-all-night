#!/usr/bin/env python3
"""分鏡先驗庫驗證 — 每個 validated 類型,其 beat 關鍵字能否覆蓋對應真實 spine 的動畫命名。

覆蓋率 = 真實動畫中「能被歸入某 beat」的比例。pass 門檻 0.9。
另報告:各真實動畫歸到哪個 beat、先驗中哪些 beat 沒被真實動畫命中(資訊)、觀測到的檔位。
未驗證(validated_against=None)的類型只列出,不判 pass。
"""
import argparse, json, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
import genre_priors as GP

GT_SPINE = {"Award": "assets/Award.json", "main_draw": "assets/main_draw.json"}


def anim_names(spine_path):
    return list(json.load(open(spine_path)).get("animations", {}).keys())


def validate_genre(genre, prior, repo_root):
    gt = prior.get("validated_against")
    if not gt:
        return {"genre": genre, "validated_against": None, "status": "UNVALIDATED(無真值,略過)"}
    path = os.path.join(repo_root, GT_SPINE[gt])
    names = anim_names(path)
    mapped, unmatched = {}, []
    for nm in names:
        b = GP.classify_anim(nm, prior)
        if b:
            mapped.setdefault(b, []).append(nm)
        else:
            unmatched.append(nm)
    coverage = (len(names) - len(unmatched)) / max(len(names), 1)
    prior_beats = [b["key"] for b in prior["beats"]]
    observed = list(mapped.keys())
    unused_beats = [b for b in prior_beats if b not in mapped]
    # 檔位觀測
    tiers = set()
    for nm in names:
        for t in (prior.get("tiers") or []):
            if t.lower() in nm.lower():
                tiers.add(t)
    return {
        "genre": genre, "validated_against": gt, "n_anims": len(names),
        "coverage": round(coverage, 3), "pass": coverage >= 0.9,
        "beat_of_anim": {b: v for b, v in mapped.items()},
        "unmatched_anims": unmatched,
        "prior_beats_unused": unused_beats,
        "tiers_declared": prior.get("tiers"), "tiers_observed": sorted(tiers),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    reports = [validate_genre(g, p, a.repo) for g, p in GP.PRIORS.items()]
    validated = [r for r in reports if r.get("validated_against")]
    allpass = all(r["pass"] for r in validated) and len(validated) > 0
    print(json.dumps({"overall_pass": allpass,
                      "n_validated": len(validated),
                      "n_unvalidated": len(reports) - len(validated),
                      "genres": reports}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
