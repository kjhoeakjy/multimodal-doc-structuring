"""합성 데이터 생성: 부품·개정별 STEP AP242(시맨틱 PMI), 도면 PDF(PMI 미포함 파일 대체), 검사 성적서 PDF, 정답표."""
import json, random, os
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_Dimension
from OCP.XCAFDimTolObjects import (XCAFDimTolObjects_DimensionType_Size_Diameter,
                                   XCAFDimTolObjects_DimensionType_Location_LinearDistance)
from OCP.TDataStd import TDataStd_Name
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.Interface import Interface_Static
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.Message import Message, Message_Gravity
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

random.seed(7)
OUT = "data"; os.makedirs(f"{OUT}/cad", exist_ok=True); os.makedirs(f"{OUT}/drawing", exist_ok=True); os.makedirs(f"{OUT}/inspection", exist_ok=True)

REVS = ["A", "B", "C"]
parts = {}
for i in range(30):
    pid = f"P-{101+i}"
    d = random.choice([6.0, 8.0, 10.0, 12.0])
    t = random.choice([4.0, 5.0, 6.0])
    revs = {}
    for k, r in enumerate(REVS):
        tol_d = [0.15, 0.10, 0.10][k] if random.random() < 0.6 else 0.10
        dd = d + (0.5 if (k == 2 and random.random() < 0.3) else 0.0)
        revs[r] = {"HOLE_DIA": {"nom": dd, "tol": tol_d}, "THICKNESS": {"nom": t, "tol": [0.20, 0.10, 0.05][k]}}
    parts[pid] = revs


def write_step(pid, rev, spec, path, semantic=True):
    s = spec
    box = BRepPrimAPI_MakeBox(40, 40, s["THICKNESS"]["nom"]).Shape()
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, -1), gp_Dir(0, 0, 1)), s["HOLE_DIA"]["nom"] / 2, 20).Shape()
    shp = BRepAlgoAPI_Cut(box, cyl).Shape()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()); dt = XCAFDoc_DocumentTool.DimTolTool_s(doc.Main())
    lab = st.AddShape(shp, False)
    TDataStd_Name.Set_s(lab, TCollection_ExtendedString(f"{pid} REV {rev}"))
    if semantic:
        hole = None; top = None; bot = None
        ex = TopExp_Explorer(shp, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face(ex.Current()); a = BRepAdaptor_Surface(f)
            if a.GetType() == GeomAbs_Cylinder: hole = f
            elif a.GetType() == GeomAbs_Plane and abs(a.Plane().Axis().Direction().Z()) > 0.9:
                if a.Plane().Location().Z() > 0.1: top = f
                else: bot = f
            ex.Next()
        for name, face, typ in [("HOLE_DIA", hole, XCAFDimTolObjects_DimensionType_Size_Diameter),
                                ("THICKNESS", top, XCAFDimTolObjects_DimensionType_Location_LinearDistance)]:
            fl = st.AddSubShape(lab, face)
            dl = dt.AddDimension(); da = XCAFDoc_Dimension.Set_s(dl)
            fl2 = st.AddSubShape(lab, bot) if name == "THICKNESS" else None
            o = da.GetObject(); o.SetType(typ)
            nom, tol = spec[name]["nom"], spec[name]["tol"]
            o.SetValue(nom); o.SetLowerBound(nom - tol); o.SetUpperBound(nom + tol)
            o.SetSemanticName(TCollection_HAsciiString(name))
            da.SetObject(o)
            if fl2 is None: dt.SetDimension(fl, dl)
            else: dt.SetDimension(fl, fl2, dl)
    w = STEPCAFControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP242DIS")
    w.SetDimTolMode(True); w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs); w.Write(path)


def write_drawing_pdf(pid, rev, spec, path):
    c = canvas.Canvas(path, pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 12); c.drawString(40, H - 50, "BRACKET PLATE - DETAIL DRAWING")
    c.setFont("Helvetica", 9)
    c.drawString(40, H - 70, f"PART NO: {pid}    REV: {rev}    UNITS: MM    SCALE 1:1")
    c.drawString(40, H - 85, "GENERAL NOTES: BREAK ALL SHARP EDGES. MATERIAL AL 7075-T6.")
    y = H - 120
    for name in ["HOLE_DIA", "THICKNESS"]:
        nom, tol = spec[name]["nom"], spec[name]["tol"]
        sym = "DIA " if name == "HOLE_DIA" else ""
        c.drawString(60, y, f"{name}"); c.drawString(200, y, f"{sym}{nom:.2f} +/- {tol:.2f}"); y -= 16
    c.save()


# 1) CAD·도면: 개정별 파일. 약 20%는 시맨틱 PMI 없이 형상·이름만(그래픽 PMI 가정) -> 도면 PDF로 보완
manifest = []
for pid, revs in parts.items():
    for r, spec in revs.items():
        sem = random.random() >= 0.2
        p = f"{OUT}/cad/{pid}_REV{r}.stp"
        write_step(pid, r, spec, p, semantic=sem)
        dp = f"{OUT}/drawing/{pid}_REV{r}.pdf"; write_drawing_pdf(pid, r, spec, dp)
        manifest.append({"part": pid, "rev": r, "semantic_pmi": sem, "step": p, "drawing": dp})

# 2) 검사 기록: 부품·개정·특성별 측정. 오류 유형을 의도적으로 주입
#    정답 판정: 기록에 명시된 개정의 기준으로 판정. 개정 미기재는 '보류'.
records = []
rid = 0
for pid, revs in parts.items():
    for r in ["B", "C"]:
        for feat in ["HOLE_DIA", "THICKNESS"]:
            for _ in range(5):
                rid += 1
                nom, tol = revs[r][feat]["nom"], revs[r][feat]["tol"]
                kind = random.choices(["ok", "ng", "rev_trap", "unit_in", "id_variant", "rev_missing"],
                                      [0.55, 0.10, 0.12, 0.08, 0.08, 0.07])[0]
                truth = "OK"
                val = nom + random.uniform(-0.8, 0.8) * tol
                if kind == "ng":
                    val = nom + random.choice([-1, 1]) * tol * random.uniform(1.1, 2.0); truth = "NG"
                if kind == "rev_trap":
                    # 기록 개정 기준으로는 정상, 다른 개정(최신 C 또는 이전 B) 기준으로는 판정이 달라지는 값
                    other = "C" if r == "B" else "B"
                    on, ot = revs[other][feat]["nom"], revs[other][feat]["tol"]
                    lo, hi = nom - tol, nom + tol; olo, ohi = on - ot, on + ot
                    cands = [v / 1000 for v in range(int(lo * 1000), int(hi * 1000) + 1, 5) if not (olo <= v / 1000 <= ohi)]
                    if cands:
                        val = random.choice(cands)
                    else:
                        # 기록 개정 기준 NG, 다른 개정 기준 OK
                        cands = [v / 1000 for v in range(int(olo * 1000), int(ohi * 1000) + 1, 5) if not (lo <= v / 1000 <= hi)]
                        if cands: val = random.choice(cands); truth = "NG"
                        else: kind = "ok"
                rec = {"id": f"QR-{rid:04d}", "part": pid, "rev": r, "feature": feat, "value": round(val, 3), "unit": "MM", "kind": kind, "truth": truth}
                if kind == "unit_in":
                    rec["value"] = round(val / 25.4, 4); rec["unit"] = "IN"
                if kind == "id_variant":
                    rec["part"] = random.choice([pid.replace("-", ""), pid.replace("-", "-0"), pid.lower()])
                if kind == "rev_missing":
                    rec["rev"] = ""; rec["truth"] = "HOLD"
                rec["true_part"] = pid; rec["true_rev"] = r
                records.append(rec)

# 성적서 PDF: 10건씩 묶음
from reportlab.lib.pagesizes import A4
for b in range(0, len(records), 10):
    c = canvas.Canvas(f"{OUT}/inspection/IR-{b//10+1:03d}.pdf", pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 12); c.drawString(40, H - 50, f"DIMENSIONAL INSPECTION REPORT IR-{b//10+1:03d}")
    c.setFont("Helvetica", 9)
    hdr = ["REC ID", "PART NO", "REV", "CHARACTERISTIC", "MEASURED", "UNIT"]
    xs = [40, 110, 190, 230, 350, 430]
    y = H - 80
    for x, h in zip(xs, hdr): c.drawString(x, y, h)
    for rec in records[b:b + 10]:
        y -= 15
        for x, v in zip(xs, [rec["id"], rec["part"], rec["rev"] or "-", rec["feature"], f'{rec["value"]}', rec["unit"]]):
            c.drawString(x, y, str(v))
    c.save()

json.dump({"parts": parts, "manifest": manifest, "records": records}, open(f"{OUT}/truth.json", "w"), indent=1)
from collections import Counter
print(len(manifest), "files; semantic", sum(m["semantic_pmi"] for m in manifest))
print(len(records), "records", Counter(r["kind"] for r in records), Counter(r["truth"] for r in records))
