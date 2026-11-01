"""이전 실행의 응답 가운데 질문 문장과 문맥이 지금과 같은 (문항, 조건)만 새 결과 파일로 옮겨 재호출을 줄임.
사용: python seed_results.py <이전 결과 이름> <새 결과 이름> [이전 문맥 파일]
이전 문맥 파일을 주지 않으면 문맥 길이(chars)와 질문 문장이 같은 것만 옮김. retrieved는 검색 방식이 바뀌어 옮기지 않음."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_LEN_PAD = len("[자료]\n") + len("\n\n[질문]\n")

def main(old, new):
    Q = {q['id']: q for q in json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8'))}
    C = json.load(open(os.path.join(HERE, 'contexts.json'), encoding='utf-8'))
    out = os.path.join(HERE, 'results', f'{new}.jsonl')
    if os.path.exists(out):
        print('이미 있음', out); return
    n = 0
    with open(out, 'w', encoding='utf-8') as f:
        for line in open(os.path.join(HERE, 'results', f'{old}.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            q = Q.get(r['id'])
            if not q or r['cond'] in ('retrieved',) or r['cond'] not in C[r['id']]:
                continue
            if r['question'] != q['question'] or r['chars'] != len(C[r['id']][r['cond']]) + len(q['question']) + SYSTEM_LEN_PAD:
                continue
            r['seeded_from'] = old
            f.write(json.dumps(r, ensure_ascii=False) + '\n'); n += 1
    print(f'{n}건 옮김 → {out}')

if __name__ == '__main__':
    main(*sys.argv[1:3])
