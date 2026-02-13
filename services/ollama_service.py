import json
import requests
from config import Config


def stream_chat(messages, system_prompt=None):
    """Generator that yields text chunks from Ollama's streaming response."""
    all_messages = list(messages)
    if system_prompt:
        all_messages = [{"role": "system", "content": system_prompt}] + all_messages

    payload = {
        "model": Config.OLLAMA_MODEL,
        "messages": all_messages,
        "stream": True,
    }

    response = requests.post(
        f"{Config.OLLAMA_BASE_URL}/api/chat",
        json=payload,
        stream=True,
        timeout=120,
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            content = data.get("message", {}).get("content", "")
            if content:
                yield content
            if data.get("done", False):
                break


def chat(messages, system_prompt=None):
    """Non-streaming variant. Returns the complete response string."""
    return "".join(stream_chat(messages, system_prompt))
