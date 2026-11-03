"""폴더 안의 조각 이미지를 PaddleOCR로 읽어 json({파일 이름: 문자})으로 쓴다. annotate_tags.py가 별도 가상환경에서 부른다.

사용: <PaddleOCR 가상환경 python> paddle_crops.py <조각 폴더> <결과 json>
CPU에서 Paddle 3.x는 oneDNN 경로 오류가 있어 enable_mkldnn=False와 FLAGS_use_mkldnn=0으로 끈다.
"""
import os, sys, json, glob
os.environ.setdefault('FLAGS_use_mkldnn', '0')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

def main(crop_dir, out_json):
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, lang='en', enable_mkldnn=False)
    out = {}
    for f in sorted(glob.glob(os.path.join(crop_dir, '*.png'))):
        res = ocr.predict(f)
        out[os.path.splitext(os.path.basename(f))[0]] = ' '.join(res[0]['rec_texts']) if res else ''
    json.dump(out, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(out)}개 읽음 → {out_json}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
