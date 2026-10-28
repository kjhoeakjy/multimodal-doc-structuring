"""질의응답 비교. 동일 로컬 LLM, 동일 질문.
A 고정 길이 분할 텍스트 검색, B 전체 페이지 VLM 변환 결과 분할 검색, C 구조화 정보 기반 근거 구성."""
import json, re, sys, time
from pathlib import Path
import torch
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path(__file__).parent))
D = Path(__file__).parent / "data"
LLM = "ibm-granite/granite-4.1-3b"
SYS = ("Answer the question using only the context. Give the inspection interval in flight hours (FH). "
       "If the interval depends on conditions and the question does not specify one, list each value with its condition. "
       "If the context does not give an interval for the requested condition, answer 'Not specified.'")
_tok = _llm = None


def load_llm():
    global _tok, _llm
    if _llm is None:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        _tok = AutoTokenizer.from_pretrained(LLM)
        _llm = AutoModelForCausalLM.from_pretrained(LLM, dtype=torch.bfloat16).eval()
    return _tok, _llm


def ask(context, q, max_new_tokens=64, sys_prompt=None):
    tok, llm = load_llm()
    msgs = [{"role": "system", "content": sys_prompt or SYS}, {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {q}"}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
    if not isinstance(ids, torch.Tensor):
        ids = ids["input_ids"]
    t = time.time()
    with torch.no_grad():
        out = llm.generate(ids, max_new_tokens=max_new_tokens, do_sample=False)
    ans = tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()
    return ans, int(ids.shape[1]), time.time() - t


# ---------- 문맥 구성 ----------
def chunks(text, size=300, overlap=60):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size]); i += size - overlap
    return out


def bm25_ctx(text, q, k=3):
    cs = chunks(text)
    tk = lambda s: re.findall(r"[a-z0-9]+(?:-[0-9]+)?", s.lower())
    bm = BM25Okapi([tk(c) for c in cs])
    sc = bm.get_scores(tk(q))
    top = sorted(range(len(cs)), key=lambda i: -sc[i])[:k]
    return "\n---\n".join(cs[i] for i in sorted(top))


def page_text(fp):
    its = sorted(fp["items"], key=lambda i: (round(i["box"][1] / 12), i["box"][0]))
    return "\n".join(i["text"] for i in its)


STOP = set("a an the in of for and or from more than where is installed zone what interval inspection under operation environment".split())


def words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2}


def packet(facts, q):
    """질문의 대상과 조건에 해당하는 값, 조건, 출처로 근거 구성."""
    m = re.search(r"\b([A-H]-\d{2})\b", q)
    part = m.group(1) if m else None
    loc = [f for f in facts if f["대상"] == part and f["속성"] == "소속 구역"]
    if not loc:
        return f"No recorded zone for {part}."
    z = loc[0]["값"]
    vals = [f for f in facts if f["대상"] == f"ZONE {z}" and f["속성"].startswith("점검 주기")]
    lines = [f"- {part} is located in ZONE {z} (source: {loc[0]['출처']})."]
    cm = re.search(r"(?:in an?|under)\s+(.+?)\?$", q)
    if cm and len(vals) > 0:
        want = words(cm.group(1))
        match = [f for f in vals if f["조건"] and len(want & words(f["조건"])) / max(1, len(want)) >= 0.5]
        if not match:
            conds = "; ".join(f"{f['값']} FH ({f['조건'] or 'no condition stated'})" for f in vals)
            return "\n".join(lines + [f"- No interval is recorded for the requested condition '{cm.group(1)}'. Recorded: {conds}."])
        vals = match
    for f in vals:
        lines.append(f"- ZONE {z} inspection interval: {f['값']} FH" + (f", condition: {f['조건']}" if f["조건"] else "") + f" (source: {f['출처']}).")
    return "\n".join(lines)


def judge(ans, qd):
    nums = {int(n) for n in re.findall(r"\b(\d{3,4})\b", ans.replace(",", ""))}
    if qd.get("abstain"):
        a = ans.lower()
        return any(k in a for k in ("not specified", "not given", "no interval", "not provided", "does not"))
    return set(qd["expect"]) <= nums and not (set(qd["forbid"]) & nums)
