const pptxgen = require('pptxgenjs');
const OUT = process.argv[2] || 'out.pptx';

const BK = '111111', DK = '333333', MD = '767676', LT = 'CFCFCF', LL = 'EDEDED', WH = 'FFFFFF', AC = 'C8102E';
const FR = 'Pretendard', FM = 'Pretendard Medium', FS = 'Pretendard SemiBold';

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = '비정형 데이터 구조화 1차안';
const W = 13.333, ML = 0.45, CW = W - 2 * ML;
const s = pres.addSlide(); s.background = { color: WH };

function T(text, x, y, w, h, o = {}) {
  s.addText(text, Object.assign({ x, y, w, h, isTextBox: true, margin: 0, fontFace: FR, fontSize: 9.5, color: DK, valign: 'top', align: 'left', lineSpacingMultiple: 1.2, fit: 'none', charSpacing: -0.2 }, o));
}
function LINE(x1, y1, x2, y2, color = LT, width = 0.75) {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, line: { color, width } });
}
function SEC(label, x, y, w) {
  T(label, x, y, w, 0.24, { fontFace: FS, fontSize: 10.5, color: BK, valign: 'middle' });
  LINE(x, y + 0.3, x + w, y + 0.3, BK, 1);
}
const r = (text, o = {}) => ({ text, options: o });

/* 헤더 */
T('AI/AX 개발  |  주제 2  비정형 데이터 전처리·구조화', ML, 0.28, 8, 0.22, { fontSize: 9, color: MD, valign: 'middle' });
T('개정 상태까지 연결해 검증하는 항공 기술 데이터 구조화', ML, 0.52, CW, 0.5, { fontFace: FS, fontSize: 21, color: BK, valign: 'middle', charSpacing: -0.5 });
T('정보의 정확한 인용과 올바른 설계·부품·개정 적용은 별개의 문제이며 후자를 규칙으로 검증하는 데이터 구조 제안', ML, 1.04, CW, 0.26, { fontSize: 10.5, color: DK, valign: 'middle' });

const Y0 = 1.55;
const C1 = ML, W1 = 3.55;
const C2 = C1 + W1 + 0.35, W2 = 4.25;
const C3 = C2 + W2 + 0.35, W3 = W - ML - C3;

/* 1. 문제 */
SEC('01  문제', C1, Y0, W1);
const probs = [
  ['구조 손실', '텍스트 변환 시 표 행·열, 치수 대응, 부품 계층 소실'],
  ['관계 단절', '동일 부품의 도면·명세서·검사 기록 간 연결 부재'],
  ['검증 불가', '인용의 정확성과 개정·적용 조건의 정합성 미구분'],
];
let y = Y0 + 0.45;
probs.forEach(([k, v]) => {
  T(k, C1, y, 0.85, 0.42, { fontFace: FM, fontSize: 9.5, color: BK });
  T(v, C1 + 0.88, y, W1 - 0.88, 0.42, { fontSize: 9.5 });
  y += 0.5;
});

// 예시
y += 0.08;
T('예시  P-104 구멍 직경(가상 데이터)', C1, y, W1, 0.22, { fontFace: FM, fontSize: 9, color: MD });
y += 0.28;
const ex = [
  [r('구분', { bold: false, color: MD }), r('개정', { color: MD }), r('값(mm)', { color: MD }), r('판정', { color: MD })],
  ['설계 기준', 'C', '12.00 ± 0.10', '-'],
  ['검사 A', 'B', '12.08', 'Rev.B 기준 판정'],
  ['검사 B', 'C', '12.12', r('허용 범위 초과', { color: AC, fontFace: FM })],
];
s.addTable(ex.map((row, i) => row.map(c => (typeof c === 'string' ? { text: c, options: {} } : c)).map(c => ({ text: c.text, options: Object.assign({ fontFace: FR, fontSize: 9, color: DK, valign: 'middle', margin: [0.03, 0.04, 0.03, 0.04], border: [{ type: 'none' }, { type: 'none' }, { type: i === 0 || i === 3 ? 'solid' : 'solid', pt: 0.5, color: i === 0 ? BK : LL }, { type: 'none' }] }, c.options) }))),
  { x: C1, y, w: W1, colW: [0.85, 0.5, 1.05, 1.15], rowH: 0.26, autoPage: false });
y += 1.12;
T('부품 번호만 일치시키는 검색은 두 기록을 함께 반환함. 적용 개정의 판단을 언어 모델에 위임하는 구조', C1, y, W1, 0.5, { fontSize: 9, color: MD });

T([r('적용 경험  ', { fontFace: FM, color: BK }), r('제조 데이터마트 구축 시 기록 단위가 다른 공정·검사 데이터를 임의 결합하지 않고 현업 담당자와 식별자·데이터 의미를 검증한 절차의 확장', { color: DK })],
  C1, 6.05, W1, 0.62, { fontSize: 9, lineSpacingMultiple: 1.2 });

/* 2. 구조 */
SEC('02  구조', C2, Y0, W2);
const steps = [
  ['원본 구조 추출', ['CAD 시맨틱 PMI 직접 파싱(STEP AP242, OCCT)', '문서 레이아웃·표 행렬 복원(Docling)', 'PMI 부재·스캔 영역에 한정한 소형 VLM']],
  ['관계·개정 연결', ['키: 부품 ID · 개정 · 특성 · 적용 조건 · 원문 위치', '수치는 관계형 테이블, 문서 간 추적은 그래프']],
  ['규칙 검증', ['구조 규칙(SHACL): 연결·단위·개정 필수 속성', '업무 규칙(SQL): 해당 개정의 허용 범위 판정', '개정 미확인 연결은 확정하지 않고 검토 대상 분리']],
  ['근거 기반 활용', ['구조화 값은 직접 조회, 설명 질의에 한해 LLM 사용', '모든 판정에 설계·검사 원문 위치 병기']],
];
y = Y0 + 0.45;
steps.forEach(([k, items], i) => {
  T(String(i + 1).padStart(2, '0'), C2, y, 0.35, 0.24, { fontFace: FS, fontSize: 11, color: BK });
  T(k, C2 + 0.4, y, W2 - 0.4, 0.24, { fontFace: FM, fontSize: 10, color: BK });
  T(items.map(t => r(t, { bullet: { code: '2013', indent: 9 }, breakLine: true })), C2 + 0.4, y + 0.27, W2 - 0.4, items.length * 0.21 + 0.05, { fontSize: 9, lineSpacingMultiple: 1.15 });
  y += 0.32 + items.length * 0.21 + 0.17;
  if (i < steps.length - 1) LINE(C2 + 0.4, y - 0.1, C2 + W2, y - 0.1, LL, 0.75);
});
// 선행 연구 대비
T([r('선행 연구 대비  ', { fontFace: FM, color: BK }), r('멀티모달 그래프 검색(GEMS-RAG, 2026)과 설계·검사 지식그래프(NIST)는 관계 탐색에 집중. 본 제안은 관계의 성립 조건(개정·적용 범위) 검증과 미확인 연결 차단을 추가함', { color: DK })],
  C2, 6.05, W2, 0.62, { fontSize: 9, lineSpacingMultiple: 1.2 });

/* 3. 검증 */
SEC('03  검증  통제 실험(합성 데이터)', C3, Y0, W3);
T('부품 30종 × 개정 3단계, STEP AP242 90건(시맨틱 PMI 68·도면 대체 22), 검사 기록 600건, 주입 오류 5종(개정 불일치·허용 범위 초과·단위 혼용·식별자 변형·개정 미기재)', C3, Y0 + 0.42, W3, 0.62, { fontSize: 9, color: DK });

// 큰 숫자
const ky = Y0 + 1.15;
const kw = W3 / 2;
[[ '정상 기록의 위반 오판정', '27.7%', '0.0%' ], [ '질의당 입력 문자 수', '977', '119' ]].forEach(([lab, a, b], i) => {
  const x = C3 + i * kw;
  T(lab, x, ky, kw - 0.1, 0.22, { fontSize: 9, color: MD });
  T([r(a, { color: MD, fontSize: 15, fontFace: FM }), r('   ', {}), r(b, { color: BK, fontSize: 24, fontFace: FS })], x, ky + 0.24, kw - 0.1, 0.48, { valign: 'bottom', charSpacing: -0.5 });
  T('기존 연결 방식 / 제안 구조', x, ky + 0.76, kw - 0.1, 0.2, { fontSize: 8, color: MD });
});

// 단계별 표
const ty = ky + 1.15;
const hdr = ['비교 단계', '위반 오판정', '임의 판정', '판정 일치'];
const rows = [
  ['부품 번호·최신 개정 기준', '27.7%', '50건', '62.2%'],
  ['+ 식별자 정규화', '28.5%', '50건', '69.0%'],
  ['+ 개정 조건 연결', '10.7%', '50건', '83.2%'],
  ['+ 단위 정규화·보류', '0.0%', '0건', '100.0%'],
];
const tb = [hdr.map((h, j) => ({ text: h, options: { color: MD, fontSize: 8.5, align: j ? 'right' : 'left', border: [{ type: 'none' }, { type: 'none' }, { type: 'solid', pt: 0.75, color: BK }, { type: 'none' }] } }))]
  .concat(rows.map((row, i) => row.map((c, j) => ({ text: c, options: { align: j ? 'right' : 'left', fontFace: i === 3 ? FM : FR, color: i === 3 ? BK : DK, border: [{ type: 'none' }, { type: 'none' }, { type: 'solid', pt: 0.5, color: LL }, { type: 'none' }] } }))));
s.addTable(tb.map(row => row.map(c => ({ text: c.text, options: Object.assign({ fontFace: FR, fontSize: 9, valign: 'middle', margin: [0.03, 0.04, 0.03, 0.04] }, c.options) }))),
  { x: C3, y: ty, w: W3, colW: [W3 - 2.25, 0.8, 0.75, 0.7], rowH: 0.27, autoPage: false });

T('제안 구조의 100% 일치는 주입 오류 유형에 대응해 설계한 규칙의 결과이며 실데이터 성능이 아님. 기존 연결 방식의 오판정 규모 확인이 실험 목적', C3, ty + 1.5, W3, 0.5, { fontSize: 8.5, color: MD });

// 한계·실데이터 계획
T([r('한계  ', { fontFace: FM, color: BK }), r('정의·구현한 규칙 범위의 검증. 복합 기하공차 판정과 스캔 문서 인식 경로는 미실측', { color: DK, breakLine: true }),
   r('실데이터 평가  ', { fontFace: FM, color: BK }), r('NIST MBE PMI 시험 모델(STEP AP242), DesignQA 기반 필드 추출·관계 연결·규칙 위반 탐지 정확도', { color: DK })],
  C3, 6.05, W3, 0.62, { fontSize: 9, lineSpacingMultiple: 1.25 });

/* 하단 */
LINE(ML, 6.85, W - ML, 6.85, LT, 0.5);
T('구현: Python, OCCT(cadquery-ocp), pdfplumber, SQLite, pySHACL  |  공개 가중치 모델·폐쇄망 구동 전제', ML, 6.92, CW, 0.22, { fontSize: 8, color: MD, valign: 'middle' });

pres.writeFile({ fileName: OUT }).then(f => console.log('wrote', f));
