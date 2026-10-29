"""로컬 화면 서버. 표준 라이브러리만 사용. 실행: python app/server.py [포트]

- GET  /                 화면
- GET  /api/system       코어·메모리와 처리 설정
- POST /api/analyze      {name, data(base64), opts{mode,dpi,lang,page}} → {job}
- GET  /api/job/<id>     진행 상태와 결과
- POST /api/query        {job, tag, depth} → 부분 그래프
- GET  /jobs/<id>/<file> 작업 파일(보기 그림 등)
"""
import os, sys, json, base64, uuid, threading, queue, time, mimetypes, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pipeline

JOBS_DIR = os.path.join(HERE, 'jobs')
os.makedirs(JOBS_DIR, exist_ok=True)
RES = pipeline.Resources()
JOBS, LOCK, Q = {}, threading.Lock(), queue.Queue()


def worker():
    while True:
        jid = Q.get()
        with LOCK:
            j = JOBS[jid]; j['status'] = 'running'; j['started'] = time.time()
        def progress(step):
            with LOCK:
                j['steps'].append(dict(name=step, t=round(time.time() - j['started'], 1)))
        try:
            res = pipeline.Job(os.path.join(JOBS_DIR, jid), j['name'], j['data'], j['opts'], RES, progress).run()
            with LOCK:
                j['status'] = 'done'; j['result'] = res; j['finished'] = time.time()
        except Exception as e:
            with LOCK:
                j['status'] = 'error'; j['error'] = f"{type(e).__name__}: {e}"; j['trace'] = traceback.format_exc(); j['finished'] = time.time()
        finally:
            j['data'] = None
            Q.task_done()

threading.Thread(target=worker, daemon=True).start()   # 작업은 한 번에 하나만 처리함(자원 보호)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def send_file(self, path):
        if not os.path.isfile(path):
            return self.send_json(dict(error='없음'), 404)
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        data = open(path, 'rb').read()
        self.send_response(200); self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text') else ''))
        self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        p = self.path.split('?')[0]
        if p in ('/', '/index.html'):
            return self.send_file(os.path.join(HERE, 'static', 'index.html'))
        if p == '/api/system':
            plan = RES.plan(); plan['queue'] = Q.qsize(); plan['ocr_loaded'] = sorted('+'.join(k) for k in pipeline._READERS)
            return self.send_json(plan)
        if p.startswith('/api/job/'):
            jid = p.split('/')[3]
            with LOCK:
                j = JOBS.get(jid)
                if not j:
                    return self.send_json(dict(error='작업 없음'), 404)
                pos = list(Q.queue).index(jid) + 1 if jid in list(Q.queue) else 0
                return self.send_json(dict(status=j['status'], steps=j['steps'], queue_position=pos, result=j.get('result'), error=j.get('error'),
                                           elapsed=round((j.get('finished') or time.time()) - (j.get('started') or time.time()), 1)))
        if p.startswith('/jobs/'):
            parts = p.split('/')
            if len(parts) == 4 and parts[2] in JOBS and '..' not in parts[3]:
                return self.send_file(os.path.join(JOBS_DIR, parts[2], parts[3]))
            return self.send_json(dict(error='없음'), 404)
        return self.send_json(dict(error='없음'), 404)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        if n > 120 * 2**20:
            return self.send_json(dict(error='파일이 너무 큼(120 MB 상한)'), 413)
        try:
            body = json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            return self.send_json(dict(error='요청 형식 오류'), 400)
        if self.path == '/api/analyze':
            name = os.path.basename(body.get('name', 'input.png'))
            if os.path.splitext(name)[1].lower() not in ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp', '.svg', '.pdf'):
                return self.send_json(dict(error='지원 형식: PNG JPG BMP TIF WEBP SVG PDF'), 400)
            jid = uuid.uuid4().hex[:12]
            os.makedirs(os.path.join(JOBS_DIR, jid), exist_ok=True)
            with LOCK:
                JOBS[jid] = dict(name=name, data=base64.b64decode(body['data']), opts=body.get('opts', {}), status='queued', steps=[], created=time.time())
            Q.put(jid)
            return self.send_json(dict(job=jid, queue_position=Q.qsize()))
        if self.path == '/api/query':
            jid = body.get('job')
            with LOCK:
                j = JOBS.get(jid)
            if not j or j['status'] != 'done':
                return self.send_json(dict(error='완료된 작업이 아님'), 400)
            g_path = os.path.join(JOBS_DIR, jid, 'graph.json')
            if not os.path.exists(g_path):
                return self.send_json(dict(found=False, lines=['관계 그래프가 없는 입력(표·본문·사진)'], nodes=[], runs=[]))
            g = json.load(open(g_path, encoding='utf-8'))
            return self.send_json(pipeline.subgraph(g, body.get('tag', '').strip(), int(body.get('depth', 3))))
        return self.send_json(dict(error='없음'), 404)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"http://127.0.0.1:{port}  코어 {RES.cores}  설정 {RES.plan()}")
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
