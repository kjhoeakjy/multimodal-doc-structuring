"""표본 전부를 처리 묶음(app/pipeline.py)에 넣어 판별 결과·개수·시간을 표로 기록"""
import os, sys, json, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import pipeline as pl
IN, OUT = os.path.join(HERE, 'input'), os.path.join(HERE, 'output'); os.makedirs(OUT, exist_ok=True)
def run(files):
    res_ = pl.Resources()
    for f in files:
        d = os.path.join(OUT, os.path.splitext(f)[0]); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        steps = []
        t0 = time.time()
        try:
            r = pl.Job(d, f, open(os.path.join(IN, f), 'rb').read(), {}, res_, steps.append).run()
            c = r['counts']; det = r.get('detect', {})
            row = dict(file=f, kind=r['kind'], reason=det.get('reason'), dpi=r.get('dpi'), ocr_lang=det.get('ocr_lang'), nodes=c.get('nodes'), runs=c.get('runs'), texts=c.get('texts'), tables=c.get('tables'), figures=c.get('figures'), paragraphs=c.get('paragraphs'),
                       time=round(time.time() - t0, 1), peak_gb=r['memory']['peak_rss_gb'], embed=r['embedding'].get('available'))
        except Exception as e:
            row = dict(file=f, kind='오류', reason=f"{type(e).__name__}: {str(e)[:80]}", time=round(time.time() - t0, 1))
        print(row, flush=True)
        for big in ('graph_input.png', 'input_gray.png', 'input_raster.png', 'view.png', 'page-overlay.png'):
            p = os.path.join(d, big)
            if os.path.exists(p) and os.path.getsize(p) > 400_000:
                os.remove(p)
        for g in os.listdir(d):
            if g.startswith('input.'):
                os.remove(os.path.join(d, g))
# 전체 표는 폴더별 result.json에서 다시 모음(일부만 다시 돌려도 표가 유지됨)
def summarize():
    allrows = []
    for f in sorted(os.listdir(IN)):
        d = os.path.join(OUT, os.path.splitext(f)[0], 'result.json')
        if not os.path.exists(d):
            continue
        r = json.load(open(d, encoding='utf-8')); c = r.get('counts', {}); det = r.get('detect', {})
        allrows.append(dict(file=f, kind=r['kind'], reason=det.get('reason'), dpi=r.get('dpi'), dpi_source=det.get('dpi_source'), ocr_lang=det.get('ocr_lang'),
                            nodes=c.get('nodes'), runs=c.get('runs'), texts=c.get('texts'), tables=c.get('tables'), figures=c.get('figures'), paragraphs=c.get('paragraphs'),
                            callouts=c.get('callouts'), leaders=c.get('callouts_with_leader'), time=round(sum(r.get('times', {}).values()), 1), peak_gb=r.get('memory', {}).get('peak_rss_gb')))
    json.dump(allrows, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False, indent=1)
    return allrows
KIND_KO = {'vector': '벡터 도면', 'drawing': '래스터 도식', 'page': '표 · 본문 쪽', 'illustration': '도해 · 기계 도면', 'photo': '사진', '오류': '오류'}

def write_md(rows):
    L = ['| 파일 | 판별 | 근거 | 해상도 | 문자 | 결과 | 시간 | 최대 메모리 |', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        if r['kind'] in ('vector', 'drawing'):
            res = f"노드 {r['nodes']} · 간선 {r['runs']}" + (f" · 표 {r['tables']}" if r.get('tables') else '')
        elif r['kind'] == 'page':
            res = f"표 {r['tables']} · 그림 영역 {r['figures']} · 문단 {r['paragraphs']}"
        elif r['kind'] == 'illustration':
            res = f"주기 {r['callouts']} · 지시선 {r['leaders']}"
        else:
            res = '임베딩 대상'
        dpi = f"{r['dpi']} ({r['dpi_source']})" if r.get('dpi') else '-'
        L.append(f"| `{r['file']}` | {KIND_KO.get(r['kind'], r['kind'])} | {r['reason'] or ''} | {dpi} | {r['texts'] if r['texts'] is not None else '-'} | {res} | {r['time']}초 | {r['peak_gb']} GB |")
    open(os.path.join(OUT, 'results.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

if __name__ == '__main__':
    run(sorted(os.listdir(IN)) if len(sys.argv) < 2 else sys.argv[1:])
    write_md(summarize())
