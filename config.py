import os
from dotenv import load_dotenv

load_dotenv(override=True)


def _parse_ollama_base_url():
    """Build Ollama base URL, handling OLLAMA_HOST with or without port/scheme."""
    raw_host = os.getenv("OLLAMA_HOST", "localhost")
    port = os.getenv("OLLAMA_PORT", "11434")

    # Strip scheme if present (e.g. "http://192.168.1.14:11434")
    if "://" in raw_host:
        raw_host = raw_host.split("://", 1)[1]

    # Strip port if already included in host (e.g. "192.168.1.14:11434")
    if ":" in raw_host:
        host = raw_host.rsplit(":", 1)[0]
    else:
        host = raw_host

    return host, int(port), f"http://{host}:{port}"


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    # Ollama
    OLLAMA_HOST, OLLAMA_PORT, OLLAMA_BASE_URL = _parse_ollama_base_url()
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "huihui_ai/qwen3-abliterated:14b-v2-q8_0")

    # ComfyUI
    COMFYUI_HOST = os.getenv("COMFYUI_HOST", "localhost")
    COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
    COMFYUI_BASE_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

    # Workflow
    WORKFLOW_PATH = os.getenv(
        "COMFYUI_WORKFLOW_PATH", "workflows/default_workflow.json"
    )

    # Profile
    PROFILE_PATH = os.getenv("PROFILE_PATH", "profiles/default.json")

    # Memory gating
    MEMORY_SHORT_CONV_THRESHOLD = int(os.getenv("MEMORY_SHORT_CONV_THRESHOLD", "6"))
    MEMORY_FORCED_RECALL_INTERVAL = int(os.getenv("MEMORY_FORCED_RECALL_INTERVAL", "8"))
    MEMORY_BATCH_SIZE = int(os.getenv("MEMORY_BATCH_SIZE", "3"))

    # Web search
    WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))

    # Image generation
    IMAGE_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "static", "images")
