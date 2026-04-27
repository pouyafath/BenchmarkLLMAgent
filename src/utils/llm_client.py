"""
Unified LLM client for benchmark experiments.

Supports:
- Ollama (gpt-oss:120b) — default, uses localhost:11434
- OpenAI-compatible endpoint (e.g., local vLLM) via OPENAI_COMPAT_BASE_URL
- HuggingFace (google/gemma-2-9b-it) — fallback when Ollama is unavailable

Set USE_OLLAMA=0 to force HuggingFace.
"""

import os
import time
from typing import Optional, Tuple, Dict

# Default: Ollama with gpt-oss:120b; override with USE_OLLAMA=0 to force HuggingFace
USE_OLLAMA = os.environ.get("USE_OLLAMA", "1").lower() not in ("0", "false", "no")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
HF_MODEL_ID = "google/gemma-2-9b-it"  # fallback only
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:120b")
OPENAI_COMPAT_BASE_URL = os.environ.get("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
OPENAI_COMPAT_API_KEY = os.environ.get("OPENAI_COMPAT_API_KEY", "")
OPENAI_COMPAT_MODEL = os.environ.get("OPENAI_COMPAT_MODEL", "Devstral-Small-2-24B-Instruct-2512")


def _check_ollama_available() -> bool:
    """Check if Ollama server is reachable."""
    try:
        import requests
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def get_llm_backend() -> str:
    """Return 'ollama' or 'huggingface' based on config and availability."""
    if OPENAI_COMPAT_BASE_URL:
        return "openai_compat"
    if USE_OLLAMA and _check_ollama_available():
        return "ollama"
    return "huggingface"


class LLMClient:
    """Unified chat completion interface. Use generate() for inference."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        backend: Optional[str] = None,
        max_new_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self._model = None
        self._tokenizer = None

        backend = backend or get_llm_backend()
        if backend == "openai_compat":
            self.backend = "openai_compat"
            self.model_id = model_id or OPENAI_COMPAT_MODEL
        elif backend == "ollama":
            self.backend = "ollama"
            self.model_id = model_id or OLLAMA_MODEL
        else:
            self.backend = "huggingface"
            self.model_id = model_id or HF_MODEL_ID

    def generate(self, system_prompt: str, user_message: str) -> Tuple[str, Dict]:
        """
        Generate a response. Returns (response_text, metadata).
        metadata includes: elapsed_s, backend, model_id
        """
        if self.backend == "openai_compat":
            return self._generate_openai_compat(system_prompt, user_message)
        if self.backend == "ollama":
            return self._generate_ollama(system_prompt, user_message)
        return self._generate_huggingface(system_prompt, user_message)

    def _generate_openai_compat(self, system_prompt: str, user_message: str) -> Tuple[str, Dict]:
        import requests

        if not OPENAI_COMPAT_BASE_URL:
            raise RuntimeError("OPENAI_COMPAT_BASE_URL is not set")

        url = f"{OPENAI_COMPAT_BASE_URL}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if OPENAI_COMPAT_API_KEY:
            headers["Authorization"] = f"Bearer {OPENAI_COMPAT_API_KEY}"
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_new_tokens,
            "response_format": {"type": "json_object"},
        }
        start = time.time()
        r = requests.post(url, json=payload, headers=headers, timeout=600)
        elapsed = time.time() - start
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI-compatible endpoint error {r.status_code}: {r.text[:500]}")
        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI-compatible endpoint returned no choices")
        text = choices[0].get("message", {}).get("content", "")
        return text, {"elapsed_s": elapsed, "backend": "openai_compat", "model_id": self.model_id}

    def _generate_ollama(self, system_prompt: str, user_message: str) -> Tuple[str, Dict]:
        import requests

        url = f"{OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_new_tokens,
            },
        }
        start = time.time()
        r = requests.post(url, json=payload, timeout=600)
        elapsed = time.time() - start
        if r.status_code != 200:
            raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:500]}")
        data = r.json()
        text = data.get("message", {}).get("content", "")
        return text, {"elapsed_s": elapsed, "backend": "ollama", "model_id": self.model_id}

    def _generate_huggingface(self, system_prompt: str, user_message: str) -> Tuple[str, Dict]:
        if self._model is None:
            self._load_huggingface_model()

        # Gemma chat format
        full_prompt = (
            f"<start_of_turn>user\n{system_prompt}\n\n{user_message}<end_of_turn>\n"
            "<start_of_turn>model\n"
        )
        start = time.time()
        import torch

        inputs = self._tokenizer(full_prompt, return_tensors="pt").to(self._model.device)
        input_len = inputs["input_ids"].shape[-1]

        with torch.inference_mode():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=max(self.temperature, 0.01),
                do_sample=self.temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        response = self._tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)
        elapsed = time.time() - start
        return response.strip(), {"elapsed_s": elapsed, "backend": "huggingface", "model_id": self.model_id}

    def _load_huggingface_model(self):
        """Load model and tokenizer. Downloads on first run."""
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        print(f"[LLM] Loading {self.model_id} from HuggingFace (first run may download)...")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        try:
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",
                trust_remote_code=True,
            ).eval()
        except Exception as e:
            if "out of memory" in str(e).lower() or "CUDA" in str(e):
                print("[LLM] OOM, trying 8-bit quantization...")
                from transformers import BitsAndBytesConfig
                quant = BitsAndBytesConfig(load_in_8bit=True)
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    quantization_config=quant,
                    device_map="auto",
                    trust_remote_code=True,
                ).eval()
            else:
                raise
        print(f"[LLM] Loaded {self.model_id}")


_client_cache: Dict[Tuple, LLMClient] = {}


def _client_cache_key(**kwargs) -> Tuple:
    backend = kwargs.get("backend") or get_llm_backend()
    model_id = kwargs.get("model_id")
    max_new_tokens = int(kwargs.get("max_new_tokens", 4096))
    temperature = float(kwargs.get("temperature", 0.0))

    if backend == "openai_compat":
        endpoint = OPENAI_COMPAT_BASE_URL
        resolved_model = model_id or OPENAI_COMPAT_MODEL
    elif backend == "ollama":
        endpoint = OLLAMA_BASE_URL
        resolved_model = model_id or OLLAMA_MODEL
    else:
        endpoint = "huggingface"
        resolved_model = model_id or HF_MODEL_ID

    return (backend, endpoint, resolved_model, max_new_tokens, temperature)


def reset_client_cache() -> None:
    """Clear cached client instances."""
    _client_cache.clear()


def get_client(**kwargs) -> LLMClient:
    key = _client_cache_key(**kwargs)
    client = _client_cache.get(key)
    if client is None:
        client = LLMClient(**kwargs)
        _client_cache[key] = client
    return client
