import logging
from pathlib import Path
from collections import OrderedDict
from typing import List, Dict, Any

from config import Config

logger = logging.getLogger("llm_service")


class MultiModelEngine:
    def __init__(self):
        # OrderedDict acts as an LRU cache: most recently used models moved to end
        self.loaded_models = OrderedDict()

    def discover_models(self) -> Dict[str, str]:
        """Returns all configured models plus any .gguf files found in models directory."""
        available = dict(Config.MODELS)

        if Config.MODELS_DIR.exists():
            for f in Config.MODELS_DIR.glob("*.gguf"):
                # Clean identifier from filename, e.g. 'mistral-7b-instruct-v0.2.Q4_K_M'
                model_id = f.stem.lower()
                if model_id not in available:
                    available[model_id] = str(f)

        return available

    def list_available_models(self) -> List[str]:
        """Lists IDs of all models available on disk."""
        discovered = self.discover_models()
        valid = []
        for model_id, path_str in discovered.items():
            if Path(path_str).exists():
                valid.append(model_id)
        # If no models found on disk yet, list registered names for configuration awareness
        return valid if valid else list(discovered.keys())

    def _resolve_model_path(self, model_name: str) -> str:
        """Finds path for a model name or falls back to default model."""
        discovered = self.discover_models()

        # Direct match or case-insensitive match
        for key, path_str in discovered.items():
            if key.lower() == model_name.lower():
                if Path(path_str).exists():
                    return path_str
                raise FileNotFoundError(
                    f"Model '{model_name}' is registered but file '{path_str}' is missing on disk."
                )

        # Fallback to default model if specific name not found
        default_path = discovered.get(Config.DEFAULT_MODEL)
        if default_path and Path(default_path).exists():
            logger.warning("Requested model '%s' not found. Falling back to default '%s'", model_name, Config.DEFAULT_MODEL)
            return default_path

        # If even default doesn't exist, check if ANY .gguf exists in models dir
        if Config.MODELS_DIR.exists():
            found = list(Config.MODELS_DIR.glob("*.gguf"))
            if found:
                logger.warning("Falling back to first available model file: %s", found[0])
                return str(found[0])

        raise FileNotFoundError(f"Model '{model_name}' not found and no .gguf models found in {Config.MODELS_DIR}")

    def load_model(self, model_name: str):
        """Loads model into memory, evicting the oldest model if MAX_LOADED_MODELS is exceeded."""
        if model_name in self.loaded_models:
            # Move to end to mark as recently used
            self.loaded_models.move_to_end(model_name)
            return self.loaded_models[model_name]

        model_path = self._resolve_model_path(model_name)

        # Check if we need to evict an old model to save RAM/VRAM
        if len(self.loaded_models) >= Config.MAX_LOADED_MODELS:
            oldest_model_name, oldest_instance = self.loaded_models.popitem(last=False)
            logger.info("Evicting model '%s' from memory to make room for '%s'", oldest_model_name, model_name)
            del oldest_instance

        from llama_cpp import Llama

        target_gpu = Config.MODEL_GPUS.get(model_name.lower(), 0)
        logger.info("Loading model '%s' from %s (GPU=%d, threads=%d, ctx=%d, gpu_layers=%d)...",
                    model_name, model_path, target_gpu, Config.N_THREADS, Config.N_CTX, Config.N_GPU_LAYERS)

        llama_kwargs = {
            "model_path": model_path,
            "n_ctx": Config.N_CTX,
            "n_threads": Config.N_THREADS,
            "n_gpu_layers": Config.N_GPU_LAYERS,
            "n_batch": Config.N_BATCH,
            "verbose": False,
        }
        if target_gpu > 0:
            llama_kwargs["main_gpu"] = target_gpu

        instance = Llama(**llama_kwargs)

        self.loaded_models[model_name] = instance
        logger.info("Model '%s' loaded successfully.", model_name)
        return instance

    @staticmethod
    def format_prompt(messages: List[Dict[str, str]]) -> str:
        chunks = []
        for msg in messages:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            if role == "system":
                chunks.append(f"<<SYSTEM>>\n{content}\n")
            elif role == "assistant":
                chunks.append(f"<<ASSISTANT>>\n{content}\n")
            else:
                chunks.append(f"<<USER>>\n{content}\n")

        chunks.append("<<ASSISTANT>>\n")
        return "".join(chunks)

    def generate(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Runs chat completion against the specified model."""
        llm = self.load_model(model_name)

        try:
            # Use native GGUF chat template completion
            output = llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=max(temperature, 0.01),
            )
            choice = output["choices"][0]
            text = choice.get("message", {}).get("content", "").strip()
            usage = output.get("usage", {})
            return {
                "text": text,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "model_used": model_name
            }
        except Exception as e:
            logger.warning("Native chat completion failed (%s). Falling back to raw prompt format.", e)
            prompt = self.format_prompt(messages)
            output = llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<<USER>>", "<<SYSTEM>>"],
                echo=False,
            )
            text = output["choices"][0]["text"].strip()
            usage = output.get("usage", {})
            return {
                "text": text,
                "prompt_tokens": usage.get("prompt_tokens", max(1, len(prompt) // 4)),
                "completion_tokens": usage.get("completion_tokens", max(1, len(text) // 4)),
                "model_used": model_name
            }


engine = MultiModelEngine()


# ==============================================================================
# OPTIONAL SAFETENSORS ENGINE (Hugging Face / PyTorch)
# To use unquantized .safetensors models directly without converting to GGUF:
# 1. Install dependencies:
#    pip install torch transformers accelerate safetensors
# 2. Point your model path to a directory containing 'model.safetensors' & 'config.json'
# 3. Swap the active engine instance:
#    # engine = MultiModelEngine()
#    engine = HuggingFaceSafetensorsEngine()
# ==============================================================================
# import torch
# from transformers import AutoModelForCausalLM, AutoTokenizer
#
# class HuggingFaceSafetensorsEngine:
#     """Direct PyTorch Safetensors LLM loader for unquantized models."""
#     def __init__(self):
#         self.loaded_models = {}
#
#     def load_model(self, model_dir_or_id: str):
#         if model_dir_or_id in self.loaded_models:
#             return self.loaded_models[model_dir_or_id]
#
#         logger.info("Loading Safetensors model from %s with PyTorch...", model_dir_or_id)
#         tokenizer = AutoTokenizer.from_pretrained(model_dir_or_id)
#         model = AutoModelForCausalLM.from_pretrained(
#             model_dir_or_id,
#             torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
#             device_map="auto" if torch.cuda.is_available() else None,
#             low_cpu_mem_usage=True
#         )
#         self.loaded_models[model_dir_or_id] = (model, tokenizer)
#         return model, tokenizer
#
#     def generate(self, model_name: str, messages: List[Dict[str, str]], max_tokens: int = 512, temperature: float = 0.7) -> Dict[str, Any]:
#         model, tokenizer = self.load_model(model_name)
#
#         # Apply standard chat template if supported by tokenizer, or fallback to formatted text
#         if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
#             prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
#         else:
#             prompt = MultiModelEngine.format_prompt(messages)
#
#         device = "cuda" if torch.cuda.is_available() else "cpu"
#         inputs = tokenizer(prompt, return_tensors="pt").to(device)
#
#         with torch.no_grad():
#             outputs = model.generate(
#                 **inputs,
#                 max_new_tokens=max_tokens,
#                 temperature=max(temperature, 0.01),
#                 do_sample=(temperature > 0.0)
#             )
#
#         # Extract newly generated tokens (excluding prompt)
#         new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
#         text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
#
#         return {
#             "text": text,
#             "prompt_tokens": int(inputs["input_ids"].shape[1]),
#             "completion_tokens": int(len(new_tokens)),
#             "model_used": model_name
#         }
