from transformers import AutoModelForCausalLM, AutoTokenizer
import os

hf_token = os.getenv('HUGGING_FACE_TOKEN')
gpt_model = os.getenv('GPT_MODEL')
bert_model = os.getenv('BERT_MODEL')


tokenizer = AutoTokenizer.from_pretrained(
    gpt_model,
    use_auth_token=hf_token
)