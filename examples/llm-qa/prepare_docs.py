"""실험 문서 준비: 표본 결과(examples/sample-inputs/output)를 그대로 쓰고, DEXPI C02·C03 벡터 도면은 여기서 처리함."""
import os, sys, json, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import pipeline as pl
SAMPLES = os.path.join(ROOT, 'examples', 'sample-inputs', 'output')
PID_IN = os.path.join(ROOT, 'examples', 'public-documents', 'pid', 'input')
DOCS = os.path.join(HERE, 'docs')

# 문서 id → (결과 폴더, 종류, 정답 출처)
def catalog():
    cat = {}
    for stem, kind in [('pid-standard-vector', 'graph'), ('pid-standard-200dpi', 'graph'), ('pid-standard-scan', 'graph'),
                       ('en-report-synthetic-vector', 'page'), ('en-report-synthetic-scan150', 'page'), ('ko-report-synthetic', 'page'),
                       ('ko-table-text-scan200', 'page'), ('mech-flange-synthetic-vector', 'page'), ('mech-flange-synthetic-200dpi', 'page'),
                       ('faa-torque-table', 'page'), ('faa-torque-table-scan', 'page'), ('faa-bolt-table-illustrations', 'page'), ('faa-text-page', 'page')]:
        cat[stem] = dict(dir=os.path.join(SAMPLES, stem), kind=kind)
    for stem in ('C02', 'C03'):
        cat[f'pid-{stem.lower()}-vector'] = dict(dir=os.path.join(DOCS, f'pid-{stem.lower()}-vector'), kind='graph')
    return cat

def main():
    res = pl.Resources()
    for stem in ('C02', 'C03'):
        d = os.path.join(DOCS, f'pid-{stem.lower()}-vector')
        if os.path.exists(os.path.join(d, 'result.json')):
            continue
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        src = os.path.join(PID_IN, f'{stem}.svg')
        r = pl.Job(d, f'{stem}.svg', open(src, 'rb').read(), {}, res, lambda s: None).run()
        print(stem, r['kind'], r['counts'])
        for f in os.listdir(d):
            if f.startswith('input.') or f in ('view.png',):
                os.remove(os.path.join(d, f))

if __name__ == '__main__':
    main()
