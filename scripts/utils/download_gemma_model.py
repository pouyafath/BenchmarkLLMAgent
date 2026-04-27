"""
Pre-download Gemma 3 12B from HuggingFace.

Run once to cache the model before benchmarks.
Usage: python scripts/utils/download_gemma_model.py
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))


def main():
    print("Downloading google/gemma-3-12b-it...")
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_id = "google/gemma-3-12b-it"
    AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    print("  Tokenizer OK")
    AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True)
    print("  Model OK. Cached in ~/.cache/huggingface/")


if __name__ == "__main__":
    main()
