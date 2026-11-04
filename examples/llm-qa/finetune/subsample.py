"""큰 학습 자료에서 무작위 표본을 뽑는다(파일럿용). 파일을 한 줄씩 읽어 메모리를 적게 쓴다.
사용: python subsample.py train.jsonl train-8k.jsonl --n 8000 [--seed 0]"""
import sys, json, random, argparse, collections

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--n', type=int, default=8000); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(); rnd = random.Random(a.seed)
    keep = []     # 저수지 표본
    for i, line in enumerate(open(a.src, encoding='utf-8')):
        if i < a.n:
            keep.append(line)
        else:
            j = rnd.randrange(i + 1)
            if j < a.n:
                keep[j] = line
    rnd.shuffle(keep)
    open(a.out, 'w', encoding='utf-8').writelines(keep)
    c = collections.Counter(json.loads(l)['meta']['type'] for l in keep)
    print(f'{i + 1}개 중 {len(keep)}개 → {a.out}, 종류별 {dict(c)}')

if __name__ == '__main__':
    main()
