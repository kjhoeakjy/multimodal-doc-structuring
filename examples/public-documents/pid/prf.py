"""정답 대조 결과(output/<폴더>/*.md)를 모아 배관 연결의 재현율·정밀도·F1과 요소 라벨 대응 정확도를 도면·조건별 표로 씀.
재현율 = 복원한 정답 인접 쌍 / 정답 인접 쌍. 정밀도 = 정답에 있는 추출 쌍 / (추출 쌍 - 신호선 쌍). 신호선 쌍은 배관 정답의 범위 밖이라 분모에서 뺌.
사용: python prf.py [폴더 이름, 기본 current]  → output/<폴더>/prf.md"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r'정답 인접 쌍 (\d+)개 중 (\d+)개 복원.*?추출 인접 쌍 (\d+)개 중 정답에 없는 쌍 (\d+)개\. 이 중 (\d+)개는 계측 신호선', re.S)
LAB = re.compile(r'요소 라벨 (\d+)개 중 소속이 맞는 라벨 (\d+)개')

def read(path):
    s = open(path, encoding='utf-8').read()
    m = PAT.search(s); l = LAB.search(s)
    gt, rec, ex, extra, sig = map(int, m.groups())
    lab_n, lab_ok = map(int, l.groups()) if l else (0, 0)
    return dict(gt=gt, rec=rec, ex_pipe=ex - sig, ok=ex - extra, lab_n=lab_n, lab_ok=lab_ok)

def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0

def main(folder='current'):
    d = os.path.join(HERE, 'output', folder)
    rows = []
    for f in sorted(os.listdir(d)):
        if f.endswith('.md') and f != 'prf.md':
            v = read(os.path.join(d, f)); v['name'] = f[:-3]; rows.append(v)
    L = ['# 배관 연결 정밀도·재현율·F1과 요소 라벨 대응', '',
         '| 도면·조건 | 정답 쌍 | 복원 | 재현율 | 추출 배관 쌍 | 정답 일치 | 정밀도 | F1 | 요소 라벨 |', '|---|---|---|---|---|---|---|---|---|']
    for v in rows:
        r = v['rec'] / v['gt']; p = v['ok'] / max(1, v['ex_pipe'])
        lab = f"{v['lab_ok']}/{v['lab_n']} ({v['lab_ok'] / v['lab_n']:.2f})" if v['lab_n'] else '문자 없음'
        v.update(r=r, p=p, f=f1(p, r))
        L.append(f"| {v['name']} | {v['gt']} | {v['rec']} | {r:.2f} | {v['ex_pipe']} | {v['ok']} | {p:.2f} | {v['f']:.2f} | {lab} |")
    for title, sel in [('문자가 있는 조건', [v for v in rows if v['lab_n']]), ('전체 조건', rows)]:
        if not sel:
            continue
        n = len(sel)
        mr = sum(v['r'] for v in sel) / n; mp = sum(v['p'] for v in sel) / n; mf = sum(v['f'] for v in sel) / n
        gr = sum(v['rec'] for v in sel) / sum(v['gt'] for v in sel); gp = sum(v['ok'] for v in sel) / max(1, sum(v['ex_pipe'] for v in sel))
        lab = [v for v in sel if v['lab_n']]
        ml = sum(v['lab_ok'] / v['lab_n'] for v in lab) / len(lab) if lab else 0
        gl = sum(v['lab_ok'] for v in lab) / max(1, sum(v['lab_n'] for v in lab))
        L.append(f"| {title} {n}개 평균 | | | {mr:.3f} | | | {mp:.3f} | {mf:.3f} | {ml:.3f} |")
        L.append(f"| {title} {n}개 합산 | {sum(v['gt'] for v in sel)} | {sum(v['rec'] for v in sel)} | {gr:.3f} | {sum(v['ex_pipe'] for v in sel)} | {sum(v['ok'] for v in sel)} | {gp:.3f} | {f1(gp, gr):.3f} | {gl:.3f} |")
    open(os.path.join(d, 'prf.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))

if __name__ == '__main__':
    main(*sys.argv[1:])
