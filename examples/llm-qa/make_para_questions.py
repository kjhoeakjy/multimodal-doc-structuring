"""같은 문항을 다른 말로 바꾼 평가 세트를 만든다(파인튜닝 모델이 문항 양식을 외운 것인지 확인하는 용도).
답·채점 방식·문항 id는 그대로 두고 질문 문장만 바꾼다. 학습 자료(finetune/qgen.py)는 원래 양식만 쓰므로 바꾼 문장은 학습에 없다.
사용: python make_para_questions.py  → questions-para.json(43문항), questions-conn-para.json(36문항)
실행: run_noise.py / finetune/eval_lora.py 에 --qfile questions-conn-para.json"""
import os, re, json
HERE = os.path.dirname(os.path.abspath(__file__))

RULES = [
    ('도달여부', r'두 장비 (\S+), (\S+) 사이에', lambda m: f"{m.group(1)}과 {m.group(2)}은 중간에 다른 장비 없이 배관이나 밸브, 분기점만 지나서 서로 이어져 있는가? 예/아니오 중 하나로만 답하라."),
    ('라인도달', r'라인 번호 (\S+) 배관', lambda m: f"{m.group(1)}번 라인의 배관을 끝까지 따라갔을 때, 다른 장비를 지나지 않고 닿게 되는 장비의 태그를 전부 써라. 쉼표로 구분한 태그만 답하라."),
    ('연결수', r'장비 (\S+)에 직접', lambda m: f"{m.group(1)}에 바로 이어진 선(배관과 신호선을 합쳐서)의 개수는? 숫자 하나로 답하라."),
    ('경로', r'장비 (\S+)에서 장비 (\S+)까지', lambda m: f"{m.group(1)}에서 출발해 {m.group(2)}에 이르는 가장 짧은 연결에서, 두 장비 사이에 놓인 요소(밸브, 기호, 분기점)의 개수는? 숫자 하나로 답하라."),
    ('라인경로', r'두 장비 (\S+), (\S+) 사이를', lambda m: f"{m.group(1)}과 {m.group(2)}을 다른 장비 없이 잇는 배관 구간에 적힌 라인 번호를 전부 써라. 쉼표로 구분한 번호만 답하라."),
    ('연결', r'장비 (\S+)에서 배관을', lambda m: f"{m.group(1)}의 배관을 따라갔을 때 다른 장비를 지나지 않고 처음 만나는 장비는 어떤 것들인가? 태그만 쉼표로 구분해 전부 답하라."),
    ('개수', r'장비 (\S+)의 노즐', lambda m: f"{m.group(1)}에 달린 접속구(노즐)는 모두 몇 개인가? 숫자 하나로 답하라."),
    ('노즐', r'장비 (\S+)의 노즐 (\S+)의', lambda m: f"{m.group(1)}의 접속구 {m.group(2)}에 적힌 호칭 지름 값은 얼마인가? DN 뒤의 숫자만 답하라."),
    ('라인', r'라인 번호 (\S+) 배관의 호칭 지름', lambda m: f"{m.group(1)}번 라인의 관 호칭 지름(DN) 값은? 숫자만 답하라."),
    ('라인', r'라인 번호 (\S+) 배관의 배관 등급', lambda m: f"{m.group(1)}번 라인에 지정된 배관 등급 코드는? 코드만 답하라."),
    ('라인', r'라인 번호 (\S+) 배관의 유체', lambda m: f"{m.group(1)}번 라인에 흐르는 유체의 코드는? 코드만 답하라."),
    ('계기', r'계기 번호 (\S+)의 기능', lambda m: f"번호 {m.group(1)}이 붙은 계기의 기능 기호(측정·제어 종류를 나타내는 알파벳)는? 기호만 답하라."),
]

def para(q):
    for typ, pat, f in RULES:
        if q['type'] == typ:
            m = re.search(pat, q['question'])
            if m:
                return f(m)
    raise ValueError(q['type'] + ' ' + q['question'])

def main():
    N = json.load(open(os.path.join(HERE, 'noise', 'contexts.json'), encoding='utf-8'))
    for src, out, keep in (('questions.json', 'questions-para.json', set(N['questions'])), ('questions-conn.json', 'questions-conn-para.json', None)):
        Q = json.load(open(os.path.join(HERE, src), encoding='utf-8'))
        P = []
        for q in Q:
            if q['doc'] != N['doc'] or (keep is not None and q['id'] not in keep):
                continue
            p = dict(q); p['question'] = para(q); p['source'] = q.get('source', '') + ' (바꿔 말한 문장)'; P.append(p)
        json.dump(P, open(os.path.join(HERE, out), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(out, len(P))
        for p in P[:3]:
            print(' ', p['type'], p['question'])

if __name__ == '__main__':
    main()
