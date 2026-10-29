"""Granite-Docling-258M 영역 재해석. 생성 길이 상한을 두어 CPU에서 반복 생성으로 인한 지연을 방지함."""
import re, time
import numpy as np, torch
from PIL import Image

MODEL = "ibm-granite/granite-docling-258M"
_m = _p = None


def load():
    global _m, _p
    if _m is None:
        from transformers import AutoProcessor, AutoModelForImageTextToText
        _p = AutoProcessor.from_pretrained(MODEL)
        _m = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.float32).eval()
        _p.image_processor.size = {"longest_edge": 512}  # 작은 영역을 2048로 확대해 타일이 늘어나는 것을 방지
    return _m, _p


def read_region(gray: np.ndarray, max_new_tokens=160, prompt="Convert this page to docling."):
    """잘라낸 영역 이미지를 DocTags로 변환해 태그를 제거한 텍스트 줄 목록과 소요 시간을 반환함."""
    m, p = load()
    img = Image.fromarray(gray).convert("RGB")
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    text = p.apply_chat_template(msgs, add_generation_prompt=True)
    inp = p(text=text, images=[img], return_tensors="pt")
    t = time.time()
    with torch.no_grad():
        out = m.generate(**inp, max_new_tokens=max_new_tokens, do_sample=False)
    dt = time.time() - t
    gen = p.batch_decode(out[:, inp["input_ids"].shape[1]:], skip_special_tokens=False)[0]
    n_tok = int(out.shape[1] - inp["input_ids"].shape[1])
    lines = []
    for seg in re.split(r"</(?:text|section_header_level_1|footnote|caption|list_item|page_header|page_footer)>", gen):
        s = re.sub(r"<[^>]+>", "", seg).strip()
        if s:
            lines.append(s)
    return lines, dt, n_tok, gen
