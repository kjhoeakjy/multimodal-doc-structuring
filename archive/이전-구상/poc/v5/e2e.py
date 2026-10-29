"""종단형 방식: 페이지 이미지와 질문을 소형 멀티모달 모델에 직접 입력."""
import time, torch
from PIL import Image

MODEL = "ibm-granite/granite-vision-3.3-2b"
_m = _p = None


def load():
    global _m, _p
    if _m is None:
        from transformers import AutoProcessor, AutoModelForImageTextToText
        _p = AutoProcessor.from_pretrained(MODEL)
        _m = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.bfloat16).eval()
    return _m, _p


def ask(img_path, sys_prompt, q, max_new_tokens=48):
    m, p = load()
    img = Image.open(img_path).convert("RGB")
    conv = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": f"{sys_prompt}\n\nQuestion: {q}"}]}]
    text = p.apply_chat_template(conv, add_generation_prompt=True)
    inp = p(images=img, text=text, return_tensors="pt")
    t = time.time()
    with torch.no_grad():
        out = m.generate(**inp, max_new_tokens=max_new_tokens, do_sample=False)
    ans = p.decode(out[0, inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return ans, int(inp["input_ids"].shape[1]), time.time() - t
