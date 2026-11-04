"""연결 의존 문항 생성. 오류 통제 실험(noise.py)의 기준 그래프인 C01 벡터 추출 그래프(DEXPI XML 대비 배관 연결 재현율·정밀도 1.00)에서
연결을 따라가야 답할 수 있는 문항을 만든다. 장비 간 도달은 DEXPI XML 정답과 다시 대조한다.
문항 종류
  도달여부  두 장비가 다른 장비를 거치지 않고 이어져 있는가(예/아니오). 장비 쌍 전부
  라인도달  라인 번호가 붙은 선에서 연결을 따라가면 다른 장비를 거치지 않고 도달하는 장비 집합
  연결수    장비에 직접 붙은 연결선 수
  경로      이어진 두 장비 사이 최단 경로에서 지나는 분기점·기호 수
  라인경로  이어진 두 장비 사이의 경로(다른 장비를 지나지 않는 모든 단순 경로) 위 선에 붙은 라인 번호 집합. 라벨 오귀속에 반응
모든 문항은 요소 속성 줄만으로는 답할 수 없고 연결을 따라가야 답이 나옴(needs_relation=True).
도달 규칙은 직렬화의 '장비 간 배관 연결'과 같음(배관·신호 연결을 모두 따르고 분기점·밸브·기호·계기는 지나며 장비에서 멈춤).
사용: python make_conn_questions.py
결과: questions-conn.json, run_noise.py --qfile questions-conn.json 으로 실행"""
import os, sys, json, re, itertools, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'examples', 'public-documents', 'pid'))
import evaluate as ev
import serialize as sz
from noise import GRAPH, XML, DOC
from precompute import build, reach_from, shortest_inner, line_numbers, path_lines as _path_lines

def xml_reach():
    comps, conns, _ = ev.load_gt(XML, 297.053)
    adj = collections.defaultdict(set)
    for a, b in ev.gt_adjacency(comps, conns):
        adj[a].add(b); adj[b].add(a)
    named = {cid: c['tag'] for cid, c in comps.items() if c['kind'] == 'Equipment' and c['tag']}
    return {named[c]: {named[x] for x in reach_from([c], adj, named)} for c in named}

def main():
    g = json.load(open(GRAPH, encoding='utf-8'))
    nodes, adj, deg, equip, lift = build(g)
    tag = equip
    R = {e: reach_from([e], adj, equip) for e in equip}
    X = xml_reach()
    for e in equip:
        assert {tag[x] for x in R[e]} == X.get(tag[e], set()), (tag[e], R[e], X.get(tag[e]))
    Q = []
    def add(typ, question, answers, kind, focus=None):
        Q.append(dict(id=f"c{len(Q):03d}", doc=DOC, type=typ, question=question, answers=answers, focus=focus, source='DEXPI C01 기준 그래프', kind=kind))
    names = sorted(equip, key=lambda e: tag[e])
    for a, b in itertools.combinations(names, 2):
        yes = b in R[a]
        add('도달여부', f"두 장비 {tag[a]}, {tag[b]} 사이에 다른 장비를 거치지 않는 연결(배관·밸브·분기점) 경로가 있는가? 예 또는 아니오로 답하라.", ['예' if yes else '아니오'], 'yesno')
    by_line, run_lines = line_numbers(g, lift)
    for ln in sorted(by_line):
        ends = by_line[ln]
        out = {x for x in ends if x in equip} | reach_from([x for x in ends if x not in equip], adj, equip)
        if out:
            add('라인도달', f"라인 번호 {ln} 배관에서 연결을 따라가면 다른 장비를 거치지 않고 도달하는 장비 태그를 모두 나열하라. 태그만 쉼표로 나열하라.", sorted(tag[x] for x in out), 'set', focus=ln)
    for e in names:
        add('연결수', f"장비 {tag[e]}에 직접 붙은 연결선(배관·신호선)은 몇 개인가? 숫자만 답하라.", [str(deg[e])], 'single', focus=tag[e])
    for a, b in itertools.combinations(names, 2):
        if b in R[a]:
            k = shortest_inner(a, b, adj, equip)
            add('경로', f"장비 {tag[a]}에서 장비 {tag[b]}까지 가장 짧은 연결 경로에서 지나는 중간 요소(밸브·기호·분기점)는 몇 개인가? 숫자만 답하라.", [str(k)], 'single')
    def path_lines(a, b):
        return _path_lines(a, b, adj, equip, run_lines)
    for a, b in itertools.combinations(names, 2):
        if b in R[a]:
            ls = path_lines(a, b)
            if ls:
                add('라인경로', f"두 장비 {tag[a]}, {tag[b]} 사이를 (다른 장비를 거치지 않고) 잇는 배관에 붙은 라인 번호를 모두 나열하라. 번호만 쉼표로 나열하라.", sorted(ls), 'numset')
    for q in Q:
        q['needs_relation'] = True
    json.dump(Q, open(os.path.join(HERE, 'questions-conn.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    c = collections.Counter(q['type'] for q in Q)
    print(len(Q), dict(c))
    for q in Q:
        print(q['id'], q['type'], q['question'][:60], q['answers'])

if __name__ == '__main__':
    main()
