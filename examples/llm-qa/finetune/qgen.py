"""graph.json만으로 질의응답 문항을 만든다(정답 XML 없이). 학습 자료 생성과 합성 도면 평가에 쓴다.
문항 종류와 형식은 make_questions.py(노즐 DN·개수·라인 속성·계기 기능·연결)와 make_conn_questions.py(도달여부·라인도달·연결수·경로·라인경로)와 같다.
답은 주어진 그래프에서 계산하므로 오류가 든 그래프에서는 오류가 답에 그대로 전파된다(문맥에 충실한 답). 그래프에 없는 태그를 묻는 '없음' 문항도 만든다.
사용: python qgen.py <graph.json> [--negatives N]"""
import os, sys, json, re, random, argparse, itertools, collections
HERE = os.path.dirname(os.path.abspath(__file__)); QA = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, QA); sys.path.insert(0, os.path.join(QA, '..', 'public-documents', 'pid'))
import serialize as sz
from precompute import build, reach_from, shortest_inner, line_numbers, path_lines

TAG = re.compile(r'^[A-Z]{1,2} ?\d{4}$')
NONE = '자료에 없음'

def questions(g, doc='synthetic', negatives=4, seed=0, max_pairs=12):
    rnd = random.Random(seed)
    nodes, adj, deg, equip, lift = build(g)
    equip = {e: t for e, t in equip.items() if TAG.match(t)}
    names = sorted(equip, key=lambda e: equip[e]); tag = equip
    Q = []
    def add(typ, question, answers, kind='single', focus=None, needs_relation=False):
        Q.append(dict(id=f"{doc}-{len(Q):03d}", doc=doc, type=typ, question=question, answers=answers, focus=focus, source='graph', kind=kind, needs_relation=needs_relation))
    R = {e: reach_from([e], adj, equip) for e in equip}
    for e in names:     # 연결(바로 도달 장비), 개수(접속구 수), 노즐 DN
        if R[e]:
            add('연결', f"장비 {tag[e]}에서 배관을 따라가면 (다른 장비를 거치지 않고) 바로 도달하는 장비 태그는 무엇인가? 태그만 모두 나열하라.", sorted(tag[x] for x in R[e]), 'set', tag[e], True)
        noz = sz.nozzles_of(nodes[e])
        if noz:
            add('개수', f"장비 {tag[e]}의 노즐(접속구) 수는 몇 개인가? 숫자만 답하라.", [str(len(noz))], 'single', tag[e])
        for z in noz:
            if ':DN' in z:
                nn, dn = z.split(':DN')
                add('노즐', f"장비 {tag[e]}의 노즐 {nn}의 호칭 지름(DN) 숫자는? 숫자만 답하라.", [dn], 'single', tag[e])
    i = 0
    for r in g['runs']:     # 라인 속성(DN·등급·유체 돌아가며)
        f = sz.line_fields(r['texts'])
        if not f:
            continue
        d = dict(re.findall(r'(\S+)=(\S+)', f))
        if i % 3 == 0:
            add('라인', f"라인 번호 {d['라인']} 배관의 호칭 지름(DN) 숫자는? 숫자만 답하라.", [d['DN'].lstrip('0') or d['DN'], d['DN']], 'single', d['라인'])
        elif i % 3 == 1:
            add('라인', f"라인 번호 {d['라인']} 배관의 배관 등급(piping class) 코드는? 코드만 답하라.", [d['등급']], 'single', d['라인'])
        else:
            add('라인', f"라인 번호 {d['라인']} 배관의 유체 코드(fluid code)는? 코드만 답하라.", [d['유체']], 'single', d['라인'])
        i += 1
    for n in g['nodes']:     # 계기 기능 문자
        if n['role'] == 'instrument' and len(n['texts']) >= 2 and re.fullmatch(r'[A-Z]{2,5}', n['texts'][0]) and re.fullmatch(r'[\dOIl.]+', n['texts'][1]):
            add('계기', f"계기 번호 {n['texts'][1]}의 기능 문자(예: FIC, LT)는 무엇인가? 문자만 답하라.", [n['texts'][0]], 'single', n['texts'][0])
    # 연결 의존 문항(장비 쌍은 수가 많으면 표본)
    pairs = list(itertools.combinations(names, 2)); rnd.shuffle(pairs); pairs = sorted(pairs[:max_pairs])
    for a, b in pairs:
        add('도달여부', f"두 장비 {tag[a]}, {tag[b]} 사이에 다른 장비를 거치지 않는 연결(배관·밸브·분기점) 경로가 있는가? 예 또는 아니오로 답하라.", ['예' if b in R[a] else '아니오'], 'yesno', None, True)
    by_line, run_lines = line_numbers(g, lift)
    for ln in sorted(by_line)[:max_pairs]:
        ends = by_line[ln]
        out = {x for x in ends if x in equip} | reach_from([x for x in ends if x not in equip], adj, equip)
        if out:
            add('라인도달', f"라인 번호 {ln} 배관에서 연결을 따라가면 다른 장비를 거치지 않고 도달하는 장비 태그를 모두 나열하라. 태그만 쉼표로 나열하라.", sorted(tag[x] for x in out), 'set', ln, True)
    for e in names:
        add('연결수', f"장비 {tag[e]}에 직접 붙은 연결선(배관·신호선)은 몇 개인가? 숫자만 답하라.", [str(deg[e])], 'single', tag[e], True)
    for a, b in pairs:
        if b in R[a]:
            add('경로', f"장비 {tag[a]}에서 장비 {tag[b]}까지 가장 짧은 연결 경로에서 지나는 중간 요소(밸브·기호·분기점)는 몇 개인가? 숫자만 답하라.", [str(shortest_inner(a, b, adj, equip))], 'single', None, True)
            ls = path_lines(a, b, adj, equip, run_lines)
            if ls:
                add('라인경로', f"두 장비 {tag[a]}, {tag[b]} 사이를 (다른 장비를 거치지 않고) 잇는 배관에 붙은 라인 번호를 모두 나열하라. 번호만 쉼표로 나열하라.", sorted(ls), 'numset', None, True)
    # 없음 문항: 그래프에 없는 태그
    have = set(tag.values())
    for _ in range(negatives):
        t = f"{rnd.choice(['H', 'P', 'T', 'E', 'K'])}{rnd.randrange(1000, 9999)}"
        if t in have:
            continue
        if rnd.random() < 0.5:
            add('없음', f"장비 {t}의 노즐(접속구) 수는 몇 개인가? 숫자만 답하라.", [NONE], 'none', t)
        else:
            add('없음', f"장비 {t}에서 배관을 따라가면 (다른 장비를 거치지 않고) 바로 도달하는 장비 태그는 무엇인가? 태그만 모두 나열하라.", [NONE], 'none', t)
    return Q

def answer_text(q):
    """학습 목표 문자열. 집합은 쉼표 나열, 나머지는 첫 답."""
    return ', '.join(q['answers']) if q['kind'] in ('set', 'numset') else q['answers'][0]

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('graph'); ap.add_argument('--negatives', type=int, default=4)
    a = ap.parse_args()
    Q = questions(json.load(open(a.graph, encoding='utf-8')), os.path.basename(os.path.dirname(os.path.abspath(a.graph))), a.negatives)
    print(len(Q), dict(collections.Counter(q['type'] for q in Q)))
    for q in Q:
        print(q['id'], q['type'], q['question'][:70], q['answers'])
