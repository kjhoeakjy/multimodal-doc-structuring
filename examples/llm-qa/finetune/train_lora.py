"""공개 가중치 8B 모델에 LoRA SFT. GPU(빌린 vast.ai 등, VRAM 16 GB 이상 권장. --4bit는 12 GB에서도 가능).
학습 자료는 make_train.py의 JSONL(messages: system/user/assistant). 손실은 assistant 부분에만 건다.
사용: python train_lora.py --data train.jsonl --model <HF 모델 id> --out adapter/ [--epochs 2] [--lr 2e-4] [--r 16] [--max-len 6144] [--4bit]"""
import os, json, argparse, random
import torch
from torch.utils.data import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments, DataCollatorForSeq2Seq
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

class Chat(Dataset):
    def __init__(self, path, tok, max_len):
        self.rows = []
        n_long = 0
        for line in open(path, encoding='utf-8'):
            ex = json.loads(line); m = ex['messages']
            prompt = tok.apply_chat_template(m[:2], tokenize=False, add_generation_prompt=True)
            full = prompt + m[2]['content'] + tok.eos_token
            p_ids = tok(prompt, add_special_tokens=False)['input_ids']; ids = tok(full, add_special_tokens=False)['input_ids']
            if len(ids) > max_len:
                n_long += 1; continue
            labels = [-100] * len(p_ids) + ids[len(p_ids):]
            self.rows.append(dict(input_ids=ids, attention_mask=[1] * len(ids), labels=labels))
        print(f'예시 {len(self.rows)}개, 길이 초과로 제외 {n_long}개')
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, i):
        return self.rows[i]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--model', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--epochs', type=float, default=2); ap.add_argument('--lr', type=float, default=2e-4); ap.add_argument('--r', type=int, default=16)
    ap.add_argument('--max-len', type=int, default=6144); ap.add_argument('--batch', type=int, default=1); ap.add_argument('--accum', type=int, default=8)
    ap.add_argument('--4bit', dest='q4', action='store_true'); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed)
    tok = AutoTokenizer.from_pretrained(a.model); tok.pad_token = tok.pad_token or tok.eos_token
    kw = dict(torch_dtype=torch.bfloat16, device_map='auto')
    if a.q4:
        from transformers import BitsAndBytesConfig
        kw['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(a.model, **kw)
    if a.q4:
        model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable(); model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=a.r, lora_alpha=2 * a.r, lora_dropout=0.05, task_type='CAUSAL_LM',
                                             target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']))
    model.print_trainable_parameters()
    ds = Chat(a.data, tok, a.max_len)
    args = TrainingArguments(output_dir=a.out, num_train_epochs=a.epochs, learning_rate=a.lr, per_device_train_batch_size=a.batch, gradient_accumulation_steps=a.accum,
                             lr_scheduler_type='cosine', warmup_ratio=0.03, logging_steps=10, save_strategy='epoch', bf16=True, report_to=[], seed=a.seed,
                             group_by_length=True, remove_unused_columns=False)
    Trainer(model=model, args=args, train_dataset=ds, data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100)).train()
    model.save_pretrained(a.out); tok.save_pretrained(a.out)
    json.dump(vars(a), open(os.path.join(a.out, 'train_args.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
