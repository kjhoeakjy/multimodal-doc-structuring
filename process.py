"""그림 파일 폴더를 처리해 결과 폴더와 정적 HTML을 만든다. 실행: python app/process.py <입력 폴더> [출력 폴더]

- 입력 폴더의 PNG·JPG·TIF·SVG·PDF를 차례로 처리(한 번에 하나, 자원 설정 자동)
- 출력 폴더/input/에 원본 사본, output/<파일명>/에 결과, 문서-구조화.html에 전체 화면
"""
import os, sys, json, shutil, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pipeline as pl, build_page

EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp', '.svg', '.pdf')

def main(src, dst):
    IN, OUT = os.path.join(dst, 'input'), os.path.join(dst, 'output'); os.makedirs(IN, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    res = pl.Resources(); print('자원 설정', res.plan()['why'])
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith(EXTS):
            continue
        shutil.copy(os.path.join(src, f), os.path.join(IN, f))
        d = os.path.join(OUT, os.path.splitext(f)[0]); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        t0 = time.time()
        try:
            r = pl.Job(d, f, open(os.path.join(src, f), 'rb').read(), {}, res, lambda s: print(' ', s, flush=True)).run()
            print(f, r['kind'], r['detect'].get('reason'), f"{time.time() - t0:.1f}초")
        except Exception as e:
            print(f, '오류', f"{type(e).__name__}: {e}")
        for big in ('graph_input.png', 'input_gray.png', 'input_raster.png', 'view.png'):
            p = os.path.join(d, big)
            if os.path.exists(p):
                os.remove(p)
        for g in os.listdir(d):
            if g.startswith('input.'):
                os.remove(os.path.join(d, g))
    build_page.main(dst, os.path.join(dst, '문서-구조화.html'))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].rstrip('/\\') + '-결과')
