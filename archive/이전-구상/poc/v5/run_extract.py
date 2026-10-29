"""전 문서 추출, 연결 확인, 재해석 실행 후 연결 정확도와 처리 시간 기록."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import extract

D = Path(__file__).parent / "data"
truth = {t["id"]: t for t in json.loads((D / "truth.json").read_text(encoding="utf-8"))}


def score(st, t):
    got_p = {p["label"]: p["zone"] for p in st["parts"] if p["label"]}
    part_ok = sum(got_p.get(p) == str(z) for p, z in t["parts"].items())
    cells = [(z, v, c) for z, vs in t["table"].items() for v, c in vs]
    val_ok = cond_ok = 0
    for z, v, c in cells:
        r = st["rows"].get(z)
        if r and v in r["vals"]:
            val_ok += 1
            m = r["marks"][r["vals"].index(v)]
            got = st["notes"].get(m, {}).get("text", "") if m else ""
            norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
            if (not c and not m) or (c and norm(c)[:15] in norm(got) or (c and _sim(norm(c), norm(got)) > 0.8)):
                cond_ok += 1
    return {"part_zone": f"{part_ok}/{len(t['parts'])}", "value": f"{val_ok}/{len(cells)}", "value_condition": f"{cond_ok}/{len(cells)}",
            "_n": (part_ok, len(t["parts"]), cond_ok, len(cells))}


def _sim(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def main(modes=("digital", "scan")):
    res = []
    for did in sorted(truth):
        for mode in modes:
            t0 = time.time()
            fp = extract.first_pass_digital(D / f"{did}.pdf") if mode == "digital" else extract.first_pass_scan(D / f"{did}_scan.png")
            t1 = time.time()
            st = extract.structure(fp)
            before = score(st, truth[did])
            gaps = [g["type"] for g in st["gaps"]]
            log = extract.repair(fp, st)
            t2 = time.time()
            after = score(st, truth[did])
            f = extract.facts(st, did)
            (D / f"{did}_{mode}_facts.json").write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
            r = {"doc": did, "mode": mode, "first_pass_sec": round(t1 - t0, 1), "repair_sec": round(sum(l["sec"] for l in log), 1),
                 "vlm_calls": len(log), "gaps": gaps, "before": {k: v for k, v in before.items() if k[0] != "_"},
                 "after": {k: v for k, v in after.items() if k[0] != "_"}, "_b": before["_n"], "_a": after["_n"]}
            print(json.dumps({k: v for k, v in r.items() if k[0] != "_"}, ensure_ascii=False)); sys.stdout.flush()
            res.append(r)
    (D / "extract_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("digital", "scan"))
