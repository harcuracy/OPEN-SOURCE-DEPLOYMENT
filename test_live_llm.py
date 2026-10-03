import requests
import json
import sys

# ==============================================================================
# Live RunPod LLM Test Script
# ==============================================================================
RUNPOD_LLM_URL = "https://4ocns6ys5nvj56-8002.proxy.runpod.net"

def check_health():
    """Checks if the RunPod LLM service is online."""
    print(f"Connecting to: {RUNPOD_LLM_URL}/health ...")
    try:
        resp = requests.get(
            f"{RUNPOD_LLM_URL}/health",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if resp.status_code == 200:
            print("Status: ONLINE! Active models on GPU:")
            print(json.dumps(resp.json(), indent=2))
            return True
        else:
            print(f"Server returned status code: {resp.status_code}")
            return False
    except Exception as e:
        print(f"Failed to connect to RunPod: {e}")
        return False


def chat_with_model(prompt: str, model: str = "mistral-7b", max_tokens: int = 150):
    """Sends a chat message to your live model on RunPod."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful, witty AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    print(f"\nUser: {prompt}")
    print("Waiting for GPU response...", end="", flush=True)

    try:
        resp = requests.post(
            f"{RUNPOD_LLM_URL}/generate",
            json=payload,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("text", "")
            tokens = data.get("completion_tokens", 0)
            print("\r" + " " * 35 + "\r", end="")  # Clear waiting message
            print(f"Assistant ({data.get('model_used')}, {tokens} tokens):\n{answer}\n")
            return answer
        else:
            print(f"\nError {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"\nRequest failed: {e}")


if __name__ == "__main__":
    print("=== Testing Live RunPod LLM Instance ===")
    if not check_health():
        sys.exit(1)

    print("\nStarting live chat test...")
    # 1. Automated test prompt
    chat_with_model("Explain what makes open-source AI models special in 2 sentences.")

    # 2. Interactive chat loop
    print("--- You can now chat live with your RunPod model (Type 'exit' to quit) ---")
    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            chat_with_model(user_input)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
            break
