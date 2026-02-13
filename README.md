# Vessel

An AI companion chatbot that feels like texting a friend. Built with Flask, Ollama, and a multi-step reasoning pipeline that thinks before it speaks.

## Features

- **Inner monologue** — Before responding, the AI reasons about your emotion, picks a tone, decides whether to search the web or generate an image, and plans its reply strategy.
- **Emotion tracking** — Maintains a rolling history of emotional states across the conversation to inform future responses.
- **Long-term memory** — Remembers meaningful details across sessions using Cognee (vector embeddings + knowledge graph). Short conversations are kept lightweight; storage is batched and gated by relevance.
- **Image generation** — Creates images on demand via ComfyUI workflows. The inner monologue can trigger generation autonomously, or users can call `/imagine` directly.
- **Web search** — Searches DuckDuckGo when the conversation needs current events or recent facts.
- **Realistic delivery** — Splits responses into multiple short messages with simulated typing delays, like a real person texting.
- **Proactive messaging** — Background pings that send unprompted messages based on time-of-day probability weights and configurable topics.
- **Persona profiles** — Fully customizable personality, speaking style, tone, interests, and behavior via a single JSON file.

## Prerequisites

- **Python 3.8+**
- **[Ollama](https://ollama.ai)** — Local LLM inference
- **[ComfyUI](https://github.com/comfyorg/ComfyUI)** — Local image generation (optional, only needed for image features)

Pull the models you need:

```bash
ollama pull gemma3:4b          # or any chat model
ollama pull nomic-embed-text   # for long-term memory embeddings
```

## Setup

```bash
git clone https://github.com/mike-dev-stuff/vessel.git
cd vessel

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Ollama host, model, and other settings
```

## Configuration

### Environment variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `localhost` | Ollama server host |
| `OLLAMA_PORT` | `11434` | Ollama server port |
| `OLLAMA_MODEL` | `gemma3:4b` | Chat model for responses and inner monologue |
| `COMFYUI_HOST` | `localhost` | ComfyUI server host |
| `COMFYUI_PORT` | `8188` | ComfyUI server port |
| `COMFYUI_WORKFLOW_PATH` | `workflows/default_workflow.json` | Path to ComfyUI workflow |
| `PROFILE_PATH` | `profiles/default.json` | Path to persona profile |
| `FLASK_HOST` | `0.0.0.0` | Flask bind address |
| `FLASK_PORT` | `5000` | Flask port |
| `MEMORY_SHORT_CONV_THRESHOLD` | `6` | Messages before long-term memory kicks in |
| `MEMORY_FORCED_RECALL_INTERVAL` | `8` | Force memory recall every N messages |
| `MEMORY_BATCH_SIZE` | `3` | Batch this many exchanges before storing |
| `WEB_SEARCH_MAX_RESULTS` | `5` | Max DuckDuckGo results |

Cognee (long-term memory) is configured via `LLM_*` and `EMBEDDING_*` variables — see `.env.example` for the full list.

### Persona profile (`profiles/default.json`)

The profile defines your companion's personality and behavior:

```json
{
  "name": "AIsha",
  "backstory": "A creative AI companion who loves art and technology.",
  "personality_traits": ["warm", "curious", "witty", "encouraging"],
  "speaking_style": "Casual and friendly, uses contractions, occasionally playful",
  "tone": "Upbeat but not over-the-top. Thoughtful when topics are serious.",
  "interests": ["digital art", "science", "music", "philosophy"],
  "image_prompt_prefix": "",
  "image_prompt_suffix": "",
  "image_negative_prompt": "low quality, blurry, deformed, ugly, watermark, text, signature",
  "proactive_messaging": {
    "enabled": true,
    "check_interval_seconds": 600,
    "base_probability": 0.3,
    "quiet_hours": [0, 7]
  }
}
```

See the full default profile for all available fields.

## Running

```bash
python app.py
```

Open `http://localhost:1337` (or whatever port you configured).

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `POST` | `/api/chat` | Send a message (returns SSE stream) |
| `POST` | `/api/imagine` | Generate an image from a prompt |
| `GET` | `/api/pings` | Poll for proactive messages |
| `POST` | `/api/forget` | Clear conversation history and long-term memory |

### SSE event types (`/api/chat`)

| Type | Description |
|---|---|
| `typing` | Pause for `delay` ms (typing simulation) |
| `message` | Display message `content` |
| `image_generating` | Image generation started |
| `image` | Image ready at `url` |
| `error` | Error occurred |
| `done` | Stream complete |

## How it works

Each message goes through a multi-step pipeline:

1. **Inner monologue** (Ollama call #1) — Analyzes the conversation, detects emotion, plans response strategy, decides on memory/search/image actions.
2. **Web search** (conditional) — If the monologue flags `needs_web_search`, queries DuckDuckGo.
3. **Memory recall** (conditional) — Retrieves relevant context from long-term memory via Cognee.
4. **Response generation** (Ollama call #2, streamed) — Generates the reply using all gathered context.
5. **Delivery** — Splits into multiple messages with realistic typing delays.
6. **Image generation** (conditional) — If triggered, runs the ComfyUI pipeline.
7. **Memory storage** (conditional, batched) — Stores meaningful exchanges for future recall.

## Project structure

```
vessel/
├── app.py                  # Flask app, orchestrates the pipeline
├── config.py               # Environment-based configuration
├── profiles/
│   └── default.json        # Persona definition
├── services/
│   ├── ollama_service.py   # LLM inference (streaming + sync)
│   ├── inner_monologue.py  # Decision-making layer
│   ├── emotion_state.py    # Emotion tracking
│   ├── memory_service.py   # Long-term memory (Cognee)
│   ├── comfyui_service.py  # Image generation
│   ├── web_search_service.py
│   ├── delivery_service.py # Message splitting + typing delays
│   ├── image_trigger.py    # Extract image tags from responses
│   └── ping_service.py     # Proactive messaging
├── static/
│   ├── css/chat.css
│   ├── js/chat.js
│   └── images/             # Generated images (gitignored)
├── templates/
│   └── index.html
└── workflows/              # ComfyUI workflow JSONs
```

## Notes

- **Single-user** — Conversation history is in-memory. Designed for one user per instance.
- **Long-term memory** persists to `.cognee_system/` and survives restarts.
- **ComfyUI is optional** — The chatbot works without it; image generation just won't be available.
