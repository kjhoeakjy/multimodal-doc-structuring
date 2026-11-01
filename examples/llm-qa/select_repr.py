"""질문별 입력 표현 선택 규칙과 그 평가.
규칙의 입력은 질문 문장과 입력 판별 결과(도면 경로 여부)로 한정한다. 문항 파일의 type·focus·answers는 쓰지 않는다.
  1) 도면 경로(P&ID 등 관계 그래프 입력)이고 질문에 관계 단서가 있으면 full(관계 그래프 직렬화)
  2) 도면 경로이고 관계 단서가 없으면 both(문자 인식 텍스트 + 관계 그래프 직렬화)
  3) 쪽·도해 경로(표·본문·기계 도면)이면 → ocr(문자 인식 텍스트)
규칙은 개발 세트(현재 240문항)에서 확정하고 이후 바꾸지 않는다. 미사용 평가 세트에서 그대로 적용해 효과를 잰다.
사용: python select_repr.py <결과 이름>, 결과는 results/<결과 이름>-select.md
      both 조건 응답이 결과 파일에 없으면 그 문항은 full 응답으로 대신하고 표에 대체 수를 적는다."""
import os, sys, json, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 관계 단서: 연결·경로·위치 관계·개수·접속 속성을 묻는 일반 어휘(한·영). 특정 문항의 정답 문자열은 넣지 않음
CUE = re.compile(r'연결|도달|따라|거치|경유|이어지|이어진|사이|몇\s*개|개수|접속구|노즐|라인\s*번호|배관|계기|흐름|상류|하류|'
                 r'connect|between|upstream|downstream|how\s+many|number\s+of|nozzle|line\s+number|pipe|piping|flow|route|path', re.I)

def is_graph_route(doc):
    from prepare_docs import catalog
    return catalog()[doc]['kind'] == 'graph'

def choose(question, graph_route):
    if not graph_route:
        return 'ocr'
    return 'full' if CUE.search(question) else 'both'

def main(label):
    Q = json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8'))
    rows = [json.loads(l) for l in open(os.path.join(HERE, 'results', f'{label}.jsonl'), encoding='utf-8')]
    R = {(r['id'], r['cond']): r for r in rows}
    routes = {}
    sel, sub, picks = {}, 0, collections.Counter()
    for q in Q:
        if q['doc'] not in routes:
            routes[q['doc']] = is_graph_route(q['doc'])
        c = choose(q['question'], routes[q['doc']]); picks[c] += 1
        r = R.get((q['id'], c))
        if r is None and c == 'both':
            r = R.get((q['id'], 'full')); sub += 1
        sel[q['id']] = r
    have = [q for q in Q if sel[q['id']] is not None and all((q['id'], c) in R for c in ('ocr', 'full'))]
    def acc(get):
        v = [get(q) for q in have]; return sum(v) / len(v) * 100 if v else 0
    def chars(get):
        v = [get(q) for q in have]; return sum(v) / len(v) if v else 0
    oracle = lambda q: max(R[(q['id'], 'ocr')]['correct'], R[(q['id'], 'full')]['correct'])
    L = [f'# 질문별 표현 선택 · {label}', '', f'문항 {len(have)}. 선택 분포 {dict(picks)}. both 응답이 없어 full로 대체한 문항 {sub}.', '',
         '| 방식 | 정답률 | 평균 입력 문자 수 |', '|---|---|---|']
    for name, c in [('ocr 고정', 'ocr'), ('full 고정', 'full')] + ([('retrieved 고정', 'retrieved')] if all((q['id'], 'retrieved') in R for q in have) else []):
        L.append(f"| {name} | {acc(lambda q: R[(q['id'], c)]['correct']):.1f}% | {chars(lambda q: R[(q['id'], c)]['chars']):.0f} |")
    L.append(f"| 규칙 선택 | {acc(lambda q: sel[q['id']]['correct']):.1f}% | {chars(lambda q: sel[q['id']]['chars']):.0f} |")
    L.append(f"| 상한(문항마다 맞는 쪽, 참고) | {acc(oracle):.1f}% | - |")
    open(os.path.join(HERE, 'results', f'{label}-select.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))

if __name__ == '__main__':
    main(sys.argv[1])
