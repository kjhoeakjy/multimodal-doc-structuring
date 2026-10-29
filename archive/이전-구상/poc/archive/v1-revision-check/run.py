"""추출 -> 연결 -> 검증 파이프라인과 단계별 비교."""
import json, re, glob, sqlite3, os, sys, io, contextlib
from collections import Counter
import pdfplumber
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_Dimension
from OCP.TDF import TDF_AttributeIterator
from OCP.TDataStd import TDataStd_Name
from OCP.OCP.collections import Sequence_TDF_Label
from rdflib import Graph, Namespace, Literal, RDF, XSD
from pyshacl import validate

D = "data"
truth = json.load(open(f"{D}/truth.json"))

# ---------- 1. 추출 ----------
def read_step(path):
    r = STEPCAFControl_Reader(); r.SetGDTMode(True); r.SetNameMode(True)
    r.ReadFile(path); doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF")); r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()); dt = XCAFDoc_DocumentTool.DimTolTool_s(doc.Main())
    free = Sequence_TDF_Label(); st.GetFreeShapes(free)
    name = None
    for l in free:
        it = TDF_AttributeIterator(l)
        while it.More():
            a = it.Value()
            if isinstance(a, TDataStd_Name): name = a.Get().ToExtString()
            it.Next()
    seq = Sequence_TDF_Label(); dt.GetDimensionLabels(seq)
    rows = []
    for l in seq:
        it = TDF_AttributeIterator(l)
        while it.More():
            a = it.Value()
            if isinstance(a, XCAFDoc_Dimension):
                o = a.GetObject()
                rows.append({"feature": "HOLE_DIA" if "Diameter" in str(o.GetType()) else "THICKNESS", "nom": o.GetValue(),
                             "lo": o.GetLowerBound(), "hi": o.GetUpperBound()})
            it.Next()
    return name, rows

def read_drawing(path):
    txt = pdfplumber.open(path).pages[0].extract_text()
    m = re.search(r"PART NO:\s*(\S+)\s+REV:\s*(\S+)", txt)
    rows = []
    for f, nom, tol in re.findall(r"(HOLE_DIA|THICKNESS)\s+(?:DIA\s+)?([\d.]+)\s*\+/-\s*([\d.]+)", txt):
        rows.append({"feature": f, "nom": float(nom), "lo": float(nom) - float(tol), "hi": float(nom) + float(tol)})
    return m.group(1), m.group(2), rows, txt

specs = []  # (part, rev, feature, nom, lo, hi, source, source_kind)
src_count = Counter()
with contextlib.redirect_stdout(io.StringIO()):
    step_files = sorted(glob.glob(f"{D}/cad/*.stp"))
    step_out = [(p, read_step(p)) for p in step_files]
drawing_text = {}
for p, (name, rows) in step_out:
    pid, _, rev = name.partition(" REV ")
    if rows:
        src_count["CAD 직접(시맨틱 PMI)"] += 1
        for r in rows: specs.append((pid, rev, r["feature"], r["nom"], r["lo"], r["hi"], os.path.basename(p), "CAD"))
    else:
        dp = p.replace("/cad/", "/drawing/").replace(".stp", ".pdf")
        dpid, drev, drows, _ = read_drawing(dp)
        src_count["도면 대체(PMI 없음)"] += 1
        for r in drows: specs.append((dpid, drev, r["feature"], r["nom"], r["lo"], r["hi"], os.path.basename(dp), "DRAWING"))
for dp in glob.glob(f"{D}/drawing/*.pdf"):
    drawing_text[os.path.basename(dp)] = pdfplumber.open(dp).pages[0].extract_text()

# 추출 정확도: 정답 사양과 대조
ok_fields = tot_fields = 0
for pid, rev, feat, nom, lo, hi, *_ in specs:
    t = truth["parts"][pid][rev][feat]; tot_fields += 1
    ok_fields += abs(t["nom"] - nom) < 1e-6 and abs((t["nom"] - t["tol"]) - lo) < 1e-6 and abs((t["nom"] + t["tol"]) - hi) < 1e-6

# 성적서 표 추출
records = []; report_text = {}
for p in sorted(glob.glob(f"{D}/inspection/*.pdf")):
    txt = pdfplumber.open(p).pages[0].extract_text(); report_text[os.path.basename(p)] = txt
    for line in txt.splitlines():
        f = line.split()
        if f and f[0].startswith("QR-") and len(f) == 6:
            records.append({"id": f[0], "part": f[1], "rev": "" if f[2] == "-" else f[2], "feature": f[3],
                            "value": float(f[4]), "unit": f[5], "src": os.path.basename(p)})
T = {r["id"]: r for r in truth["records"]}
rec_ok = sum(1 for r in records if T[r["id"]]["part"] == r["part"] and T[r["id"]]["rev"] == r["rev"] and abs(T[r["id"]]["value"] - r["value"]) < 1e-9 and T[r["id"]]["unit"] == r["unit"])

# ---------- 2. 관계 저장(SQLite) ----------
db = sqlite3.connect(":memory:")
db.execute("create table spec(part, rev, feature, nom, lo, hi, src, kind)")
db.executemany("insert into spec values(?,?,?,?,?,?,?,?)", specs)
db.execute("create table rec(id, part, rev, feature, value, unit, src)")
db.executemany("insert into rec values(:id,:part,:rev,:feature,:value,:unit,:src)", records)

def norm_id(s):
    m = re.match(r"(?i)p-?0*(\d+)$", s)
    return f"P-{int(m.group(1))}" if m else s

LATEST = {p: max(r for (q, r) in db.execute("select part, rev from spec where part=?", (p,))) for (p,) in db.execute("select distinct part from spec")}

# ---------- 3. 구조 검증(SHACL) ----------
EX = Namespace("http://ex.org/")
g = Graph()
spec_keys = set((p, r, f) for p, r, f, *_ in specs)
for p, r, f in spec_keys:
    g.add((EX[f"{p}_{r}_{f}"], RDF.type, EX.SpecifiedCharacteristic))
for rc in records:
    n = EX[rc["id"]]; g.add((n, RDF.type, EX.Inspection))
    key = (norm_id(rc["part"]), rc["rev"], rc["feature"])
    if key in spec_keys: g.add((n, EX.measures, EX[f"{key[0]}_{key[1]}_{key[2]}"]))
    g.add((n, EX.unit, Literal(rc["unit"])))
shapes = Graph().parse(data="""
@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <http://ex.org/> .
ex:InspShape a sh:NodeShape ; sh:targetClass ex:Inspection ;
  sh:property [ sh:path ex:measures ; sh:minCount 1 ; sh:maxCount 1 ; sh:class ex:SpecifiedCharacteristic ] ;
  sh:property [ sh:path ex:unit ; sh:minCount 1 ; sh:in ("MM" "IN") ] .
""", format="turtle")
conforms, rg, _ = validate(g, shacl_graph=shapes, inference="none")
sh = Namespace("http://www.w3.org/ns/shacl#")
shacl_fail = set(str(o).split("/")[-1] for o in rg.objects(None, sh.focusNode))

# ---------- 4. 단계별 판정 ----------
def judge(rc, stage):
    part = rc["part"] if stage == 1 else norm_id(rc["part"])
    rev = rc["rev"]
    if stage >= 3 and rev:
        use_rev = rev
    elif stage >= 4 and not rev:
        return "HOLD", None
    else:
        use_rev = LATEST.get(part)
    row = db.execute("select lo, hi, src from spec where part=? and rev=? and feature=?", (part, use_rev, rc["feature"])).fetchone()
    if row is None: return "UNLINKED", None
    v = rc["value"] * 25.4 if (stage >= 4 and rc["unit"] == "IN") else rc["value"]
    lo, hi, src = row
    return ("OK" if lo - 1e-9 <= v <= hi + 1e-9 else "NG"), src

STAGES = {1: "부품 번호 문자열 연결·최신 개정 기준", 2: "+ 부품 식별자 정규화", 3: "+ 개정 조건 연결", 4: "+ 단위 정규화·개정 미기재 보류"}
res = {}
for s in STAGES:
    c = Counter()
    for rc in records:
        t = T[rc["id"]]["truth"]; j, _ = judge(rc, s)
        c["n"] += 1; c[f"t_{t}"] += 1
        if t == "NG": c["ng_hit"] += (j == "NG")
        if t == "OK": c["fp"] += (j == "NG"); c["ok_hit"] += (j == "OK")
        if t == "HOLD": c["hold_hit"] += (j == "HOLD"); c["hold_forced"] += (j in ("OK", "NG"))
        c["correct"] += (j == t); c["unlinked"] += (j == "UNLINKED")
    res[s] = {"단계": STAGES[s], "위반 탐지율": c["ng_hit"] / c["t_NG"], "오탐률": c["fp"] / c["t_OK"],
              "판정 일치율": c["correct"] / c["n"], "연결 실패": c["unlinked"], "개정 미기재 건 확정 판정": c["hold_forced"]}

# 오류 유형별 4단계 결과
by_kind = Counter(); by_kind_ok = Counter()
for rc in records:
    k = T[rc["id"]]["kind"]; by_kind[k] += 1; by_kind_ok[k] += judge(rc, 4)[0] == T[rc["id"]]["truth"]
by_kind1 = Counter()
for rc in records:
    k = T[rc["id"]]["kind"]; by_kind1[k] += judge(rc, 1)[0] == T[rc["id"]]["truth"]

# ---------- 5. 질의당 입력 문자 수 ----------
# 텍스트 RAG: 해당 성적서 페이지 + 해당 부품 도면 전 개정 텍스트 / 구조화: 기준 1행 + 측정 1행
ctx_text = ctx_struct = 0
for rc in records:
    p = norm_id(rc["part"])
    ctx_text += len(report_text[rc["src"]]) + sum(len(v) for k, v in drawing_text.items() if k.startswith(p + "_"))
    row = db.execute("select * from spec where part=? and rev=? and feature=?", (p, rc["rev"] or LATEST[p], rc["feature"])).fetchone()
    ctx_struct += len(json.dumps(row)) + len(json.dumps([rc["id"], rc["part"], rc["rev"], rc["feature"], rc["value"], rc["unit"]]))

out = {"추출": {"원본 파일": dict(src_count), "사양 필드 정확도": f"{ok_fields}/{tot_fields}", "검사 기록 추출": f"{rec_ok}/{len(truth['records'])}"},
       "구조 검증(SHACL) 위반 기록": len(shacl_fail),
       "단계별": res,
       "4단계 유형별 일치": {k: f"{by_kind_ok[k]}/{by_kind[k]}" for k in by_kind},
       "1단계 유형별 일치": {k: f"{by_kind1[k]}/{by_kind[k]}" for k in by_kind},
       "질의당 평균 입력 문자 수": {"텍스트 검색": ctx_text / len(records), "구조화 조회": ctx_struct / len(records)}}
json.dump(out, open("result.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
