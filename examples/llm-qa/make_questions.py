"""정답이 있는 자료에서 질문을 만든다.
P&ID: DEXPI XML(연결·노즐 수·노즐 호칭 지름·라인 속성·계기 기능 문자). 합성 문서: 생성 스크립트의 값. FAA 쪽: 원문(AC 43.13-1B) 대조 값.
출력 questions.json: id, doc, type, question, answers(허용 답 목록, 집합형은 set), focus(부분 그래프 기준 태그), source"""
import os, sys, json, re, collections, xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'examples', 'dexpi-reference-pid'))
import evaluate as ev
PID_IN = os.path.join(ROOT, 'examples', 'public-documents', 'pid', 'input')
Q = []
def add(doc, typ, question, answers, focus=None, source='', kind='single'):
    Q.append(dict(id=f"q{len(Q):03d}", doc=doc, type=typ, question=question, answers=answers, focus=focus, source=source, kind=kind))

# ---------- P&ID: XML 정답 ----------
def pid_questions(xml_path, docs, page_h, source):
    comps, conns, labels = ev.load_gt(xml_path, page_h)
    pairs = ev.gt_adjacency(comps, conns)
    adj = collections.defaultdict(set)
    for a, b in pairs:
        adj[a].add(b); adj[b].add(a)
    def name(cid):
        c = comps[cid]
        if c['kind'] == 'Equipment' and c['tag']:
            return c['tag'].replace(' ', '')
        if c['kind'] == 'ProcessInstrumentationFunction':
            return None
        return None
    named = {cid for cid in comps if name(cid)}
    # 연결: 이름 있는 장비에서 이름 없는 부품을 지나 처음 만나는 이름 있는 장비들
    def reach(start):
        out, seen, frontier = set(), {start}, [start]
        while frontier:
            nxt = []
            for v in frontier:
                for w in adj[v]:
                    if w in seen:
                        continue
                    seen.add(w)
                    if w in named:
                        out.add(name(w))
                    else:
                        nxt.append(w)
            frontier = nxt
        return out
    for cid in sorted(named, key=name):
        r = reach(cid)
        if r:
            for doc in docs:
                add(doc, '연결', f"장비 {name(cid)}에서 배관을 따라가면 (다른 장비를 거치지 않고) 바로 도달하는 장비 태그는 무엇인가? 태그만 모두 나열하라.", sorted(r), focus=name(cid), source=source, kind='set')
    # 노즐 수
    for cid in sorted(named, key=name):
        n = [k for k in comps[cid]['children'] if comps[k]['kind'] == 'Nozzle']
        if n:
            for doc in docs:
                add(doc, '개수', f"장비 {name(cid)}의 노즐(접속구) 수는 몇 개인가? 숫자만 답하라.", [str(len(n))], focus=name(cid), source=source)
    # 노즐 호칭 지름: 노즐 소속 Text 중 N번호와 숫자
    by_owner = collections.defaultdict(list)
    for l in labels:
        by_owner[l['owner']].append(l['text'])
    for cid in sorted(named, key=name):
        for k in comps[cid]['children']:
            if comps[k]['kind'] != 'Nozzle':
                continue
            ts = by_owner.get(k, [])
            nn = [t for t in ts if re.match(r'^N\d+$', t)]; dn = [t for t in ts if re.match(r'^\d{2,3}$', t)]
            if len(nn) == 1 and len(dn) == 1 and int(dn[0]) <= 600:
                for doc in docs:
                    add(doc, '노즐', f"장비 {name(cid)}의 노즐 {nn[0]}의 호칭 지름(DN) 숫자는? 숫자만 답하라.", [dn[0]], focus=name(cid), source=source)
    # 라인 속성
    root = ET.parse(xml_path).getroot()
    for el in root.iter('PipingNetworkSystem'):
        ga = {g.get('Name'): g.get('Value') for g in el.findall('GenericAttributes/GenericAttribute')}
        ln = ga.get('LineNumberAssignmentClass'); dn = ga.get('NominalDiameterNumericalValueRepresentationAssignmentClass'); fc = ga.get('FluidCodeAssignmentClass'); pc = ga.get('PipingClassCodeAssignmentClass')
        if not ln or not re.match(r'^[\w.]+$', ln):
            continue
        line_i = sum(1 for q in Q if q['type'] == '라인' and q['source'] == source and q['doc'] == docs[0])   # 라인마다 속성 하나씩 돌아가며 질문
        for doc in docs:
            if line_i % 3 == 0 and dn:
                add(doc, '라인', f"라인 번호 {ln} 배관의 호칭 지름(DN) 숫자는? 숫자만 답하라.", [dn.lstrip('0') or dn, dn], focus=ln, source=source)
            elif line_i % 3 == 1 and pc:
                add(doc, '라인', f"라인 번호 {ln} 배관의 배관 등급(piping class) 코드는? 코드만 답하라.", [pc], focus=ln, source=source)
            elif fc:
                add(doc, '라인', f"라인 번호 {ln} 배관의 유체 코드(fluid code)는? 코드만 답하라.", [fc], focus=ln, source=source)
    # 계기 기능 문자
    for el in root.iter('ProcessInstrumentationFunction'):
        ga = {g.get('Name'): g.get('Value') for g in el.findall('GenericAttributes/GenericAttribute')}
        num = ga.get('ProcessInstrumentationFunctionNumberAssignmentClass'); cat = ga.get('ProcessInstrumentationFunctionCategoryAssignmentClass'); fn = ga.get('ProcessInstrumentationFunctionsAssignmentClass')
        if num and cat and fn and re.match(r'^[A-Z]+$', fn):
            for doc in docs:
                add(doc, '계기', f"계기 번호 {num}의 기능 문자(예: PI, TIC)는 무엇인가? 문자만 답하라.", [cat + fn], focus=cat + fn, source=source)

pid_questions(os.path.join(PID_IN, 'C01V04-VER.EX01.xml'), ['pid-standard-vector', 'pid-standard-200dpi', 'pid-standard-scan'], 297.053, 'DEXPI C01 XML')
pid_questions(os.path.join(PID_IN, 'C02V03-VER.EX02.xml'), ['pid-c02-vector'], 594.1, 'DEXPI C02 XML')
pid_questions(os.path.join(PID_IN, 'C03V04-VER.EX02.xml'), ['pid-c03-vector'], 594.1, 'DEXPI C03 XML')

# ---------- 합성 보고서(영문): make_samples.py의 값 ----------
for doc in ('en-report-synthetic-vector', 'en-report-synthetic-scan150'):
    s = 'make_samples.py 생성 값'
    add(doc, '표', "What is the part number of the L/H MLG actuator?", ['114A3200-5'], focus='114A3200-5', source=s)
    add(doc, '표', "What is the measured leakage (cc/min) of the R/H MLG actuator?", ['1.9'], focus='R/H MLG', source=s)
    add(doc, '표', "What is the part number of the NLG steering actuator?", ['114A3410-2'], focus='114A3410-2', source=s)
    add(doc, '표', "What action is listed for the L/H MLG actuator?", ['Replace'], focus='L/H MLG', source=s)
    add(doc, '표', "Which actuator has leakage 1.1 cc/min?", ['NLG steering', 'NLG'], focus='1.1', source=s)
    add(doc, '그림', "What leakage limit (cc/min) is drawn in Figure 1?", ['4.0', '4'], focus='Figure 1', source=s)
    add(doc, '본문', "At what pressure (psi) was internal leakage measured?", ['3000'], focus='psi', source=s)
    add(doc, '본문', "What does Table 1 show? Answer with the table caption.", ['Leakage by actuator'], focus='Table 1', source=s)
    add(doc, '본문', "How many quarters/inspections are plotted in Figure 1?", ['5', 'five'], focus='Figure 1', source=s)
# ---------- 합성 보고서(한글) ----------
doc = 'ko-report-synthetic'; s = 'make_samples.py 생성 값'
add(doc, '표', "L/H MLG 작동기의 부품 번호는?", ['114A3200-5'], focus='114A3200-5', source=s)
add(doc, '표', "R/H MLG 작동기의 조치는?", ['추적 점검'], focus='R/H MLG', source=s)
add(doc, '표', "L/H MLG 작동기 교체 기한은?", ['2026-11-30'], focus='2026-11-30', source=s)
add(doc, '표', "유압유의 부품 번호(규격)는?", ['MIL-PRF-83282'], focus='MIL-PRF-83282', source=s)
add(doc, '표', "NLG 조향 작동기의 부품 번호는?", ['114A3410-2'], focus='114A3410-2', source=s)
add(doc, '그림', "그림 1에서 L/H MLG의 누설량 값은?", ['3.2'], focus='그림 1', source=s)
add(doc, '그림', "그림 1에 표시된 허용 한계 값은?", ['4.0', '4'], focus='허용 한계', source=s)
add(doc, '본문', "점검 기준이 된 정비 교범의 장 번호는?", ['32'], focus='교범', source=s)
add(doc, '본문', "표 1의 제목은?", ['조치 사항'], focus='표 1', source=s)
# ---------- 한글 표·본문(korean-ocr 정답) ----------
doc = 'ko-table-text-scan200'; s = 'korean-ocr make_page.py 생성 값'
add(doc, '표', "AN3-5A의 체결 토크(in-lb) 범위는?", ['20-25', '20~25'], focus='AN3-5A', source=s)
add(doc, '표', "NAS6204-10의 명칭은?", ['고강도 볼트, 합금강', '고강도 볼트'], focus='NAS6204-10', source=s)
add(doc, '표', "MS20365-428의 나사 규격은?", ['1/4-28'], focus='MS20365-428', source=s)
add(doc, '표', "AN960-416의 명칭은?", ['평와셔, 카드뮴 도금', '평와셔'], focus='AN960-416', source=s)
add(doc, '표', "체결 토크 50-70 in-lb인 부품 번호를 모두 나열하라.", ['AN4-7A', 'MS21042-4'], focus='50-70', source=s, kind='set')
add(doc, '본문', "윤활 시 표 값의 몇 %를 적용하는가? 숫자만 답하라.", ['80'], focus='윤활', source=s)
add(doc, '본문', "토크 렌치 측정 범위의 몇 % 이하 구간은 사용하지 않는가? 숫자만 답하라.", ['20'], focus='토크 렌치', source=s)
add(doc, '본문', "표 7-1의 제목은?", ['체결 토크'], focus='표 7-1', source=s)
# ---------- 합성 기계 도면 ----------
for doc in ('mech-flange-synthetic-vector', 'mech-flange-synthetic-200dpi'):
    s = 'make_samples.py 생성 값'
    add(doc, '치수', "What is the outer diameter of the flange (mm)? Number only.", ['120'], focus='120', source=s)
    add(doc, '치수', "How many bolt holes are there and what is their diameter? Answer as 'N x D'.", ['8 x 9', '8x9', '8 x Ø9', '8xØ9'], focus='THRU', source=s)
    add(doc, '치수', "What is the bolt circle diameter (mm)? Number only.", ['92'], focus='B.C.', source=s)
    add(doc, '치수', "What is the flange thickness shown on the side view (mm)? Number only.", ['14'], focus='14', source=s)
    add(doc, '치수', "What is the bore diameter and its fit class?", ['56 H7', 'Ø56 H7'], focus='H7', source=s)
    add(doc, '표', "What is the part number in the title block?", ['FL-2040-A'], focus='PART NO', source=s)
    add(doc, '표', "What material is specified?", ['AL 6061-T6', '6061-T6'], focus='MATERIAL', source=s)
    add(doc, '표', "What is the drawing title?", ['FLANGE, MOUNTING', 'FLANGE MOUNTING'], focus='TITLE', source=s)
    add(doc, '주석', "What tolerance applies unless noted (±)?", ['0.2', '±0.2'], focus='TOLERANCE', source=s)
    add(doc, '치수', "What is the fillet radius (R) shown on the side view (mm)? Number only.", ['4'], focus='R4', source=s)
# ---------- FAA AC 43.13-1B 표 7-1 (원문 대조) ----------
TQ = [('8-36', '12-15', '7-9', '20', '12'), ('10-32', '20-25', '12-15', '40', '25'), ('1/4-28', '50-70', '30-40', '100', '60'), ('5/16-24', '100-140', '60-85', '225', '140'),
      ('3/8-24', '160-190', '95-110', '390', '240'), ('7/16-20', '450-500', '270-300', '840', '500'), ('1/2-20', '480-690', '290-410', '1100', '660'), ('9/16-18', '800-1000', '480-600', '1600', '960'),
      ('5/8-18', '1100-1300', '600-780', '2400', '1400'), ('3/4-16', '2300-2500', '1300-1500', '5000', '3000')]
for doc in ('faa-torque-table', 'faa-torque-table-scan'):
    s = 'FAA AC 43.13-1B Table 7-1'
    for i, (ts, tn, sn, tmax, smax) in enumerate(TQ):
        if i % 2 == 0:
            add(doc, '표', f"Fine thread series, thread size {ts}: what is the recommended torque range (in-lb) for tension type nuts (MS20365 and AN310)?", [tn, tn.replace('-', '–')], focus=ts, source=s)
        else:
            add(doc, '표', f"Fine thread series, thread size {ts}: what is the maximum allowable tightening torque (in-lb) for shear type nuts (MS20364 and AN320)?", [smax], focus=ts, source=s)
    add(doc, '표', "Fine thread series, thread size 1/4-28: what is the recommended torque range (in-lb) for shear type nuts?", ['30-40'], focus='1/4-28', source=s)
    add(doc, '표', "Coarse thread series, thread size 1/4-20: what is the recommended torque range (in-lb) for tension type nuts?", ['40-50'], focus='1/4-20', source=s)
    add(doc, '표', "Coarse thread series, thread size 1/2-13: what is the maximum allowable tightening torque (in-lb) for tension type nuts (MS20365 and AN310)?", ['880'], focus='1/2-13', source=s)
    add(doc, '본문', "What condition must be met for the torque values in the table to apply to the threads (what plating)?", ['cadmium', 'cadmium plated', 'oil free cadmium plated'], focus='CAUTION', source=s)
# ---------- FAA 볼트 표(7-11, 7-12) ----------
doc = 'faa-bolt-table-illustrations'; s = 'FAA AC 43.13-1B Table 7-12'
for num, desc in [('AN3-20', 'machine'), ('AN21-36', 'clevis'), ('AN42-49', 'eye'), ('AN73-81', 'machine, drilled'), ('AN173-186', 'close tolerance'), ('AN774', 'flared tube'), ('AN775', 'universal fitting')]:
    add(doc, '표', f"In the table of bolts, what is the description of bolt number {num}?", [desc], focus=num, source=s)
add(doc, '표', "Which bolt number range is described as 'Bolt, clevis'?", ['AN21-36'], focus='clevis', source=s)
# ---------- FAA 본문 쪽(7-67~7-73) ----------
doc = 'faa-text-page'; s = 'FAA AC 43.13-1B par. 7-67~7-73'
add(doc, '본문', "Which nut is AN316?", ['checknut', 'check nut'], focus='AN316', source=s)
add(doc, '본문', "Which nut is AN350?", ['wingnut', 'wing nut'], focus='AN350', source=s)
add(doc, '본문', "Which nut is AN365?", ['sheet spring nut', 'speed nut'], focus='AN365', source=s)
add(doc, '본문', "Which nut is AN320?", ['castellated shear nut', 'castellated'], focus='AN320', source=s)
add(doc, '본문', "What are AN315 and AN335?", ['plain nut'], focus='AN315', source=s)
add(doc, '본문', "What are AN340 and AN345?", ['light hex nut'], focus='AN340', source=s)
add(doc, '본문', "Which paragraph numbers are reserved?", ['7-73 through 7-84', '7-73', '7-84'], focus='RESERVED', source=s)
add(doc, '본문', "What type of nut is commonly called a speed nut?", ['sheet spring nut'], focus='speed nut', source=s)

json.dump(Q, open(os.path.join(HERE, 'questions.json'), 'w'), ensure_ascii=False, indent=1)
c = collections.Counter((q['doc'].split('-')[0], q['type']) for q in Q)
print(len(Q), '문항'); print(collections.Counter(q['doc'] for q in Q)); print(collections.Counter(q['type'] for q in Q))
