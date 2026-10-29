"""질의응답 실행. 방식별 정답률, 질의당 입력 토큰, LLM 처리 시간 기록."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import qa, extract

D = Path(__file__).parent / "data"


def main(mode, methods, docs=None):
    qs = json.loads((D / "questions.json").read_text(encoding="utf-8"))
    if docs:
        qs = [q for q in qs if q["doc"] in docs]
    texts = {}
    res = []
    for qd in qs:
        did = qd["doc"]
        for meth in methods:
            if meth == "A":
                if did not in texts:
                    fp = extract.first_pass_digital(D / f"{did}.pdf") if mode == "digital" else extract.first_pass_scan(D / f"{did}_scan.png")
                    texts[did] = qa.page_text(fp)
                ctx = qa.bm25_ctx(texts[did], qd["q"])
            elif meth in ("B", "S"):
                md = D / (f"{did}_scan_fullvlm.md" if meth == "B" else f"{did}_{mode}_std.md")
                if not md.exists():
                    continue
                ctx = qa.bm25_ctx(md.read_text(encoding="utf-8"), qd["q"])
            elif meth == "E":
                import e2e
                img = D / (f"{did}_scan.png" if mode == "scan" else f"{did}_view.png")
                if not img.exists():
                    continue
                ans, ntok, sec = e2e.ask(img, qa.SYS, qd["q"])
                ok = qa.judge(ans, qd)
                r = {"mode": mode, "method": meth, "doc": did, "type": qd["type"], "q": qd["q"], "ok": ok, "in_tokens": ntok, "sec": round(sec, 1), "ans": ans, "ctx": "(page image)"}
                res.append(r); print(json.dumps({k: r[k] for k in ("method", "doc", "type", "ok", "in_tokens", "sec", "ans")}, ensure_ascii=False)); sys.stdout.flush()
                continue
            else:
                facts = json.loads((D / f"{did}_{mode}_facts.json").read_text(encoding="utf-8"))
                ctx = qa.packet(facts, qd["q"])
            ans, ntok, sec = qa.ask(ctx, qd["q"])
            ok = qa.judge(ans, qd)
            r = {"mode": mode, "method": meth, "doc": did, "type": qd["type"], "q": qd["q"], "ok": ok, "in_tokens": ntok, "sec": round(sec, 1), "ans": ans, "ctx": ctx}
            res.append(r)
            print(json.dumps({k: r[k] for k in ("method", "doc", "type", "ok", "in_tokens", "sec", "ans")}, ensure_ascii=False)); sys.stdout.flush()
    (D / f"qa_{mode}_{''.join(methods)}{'_sub' if docs else ''}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], list(sys.argv[2]), sys.argv[3].split(",") if len(sys.argv) > 3 else None)
