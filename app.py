import atexit
import json
import os
import time

from flask import Flask, Response, jsonify, render_template, request
from config import Config
from services import (
    ollama_service,
    comfyui_service,
    image_trigger,
    memory_service,
    inner_monologue,
    delivery_service,
    web_search_service,
    ping_service,
)
from services.emotion_state import tracker as emotion_tracker

app = Flask(__name__)
app.config.from_object(Config)

# In-memory conversation history (short-term, single-user)
conversation_history = []
_pending_memory_exchanges = []  # Buffer for batched memory storage
_message_counter = 0            # Counts messages for periodic forced-recall


def load_profile():
    """Load the persona profile JSON. Returns (system_prompt, raw_profile)."""
    path = Config.PROFILE_PATH
    if not os.path.exists(path):
        return "You are a helpful assistant.", {}
    with open(path, "r") as f:
        profile = json.load(f)

    parts = [f"You are {profile.get('name', 'an AI assistant')}."]

    if profile.get("backstory"):
        parts.append(profile["backstory"])
    if profile.get("personality_traits"):
        parts.append(
            f"Personality traits: {', '.join(profile['personality_traits'])}."
        )
    if profile.get("speaking_style"):
        parts.append(f"Speaking style: {profile['speaking_style']}.")
    if profile.get("tone"):
        parts.append(f"Tone: {profile['tone']}.")
    if profile.get("interests"):
        parts.append(f"Interests: {', '.join(profile['interests'])}.")
    if profile.get("expertise"):
        parts.append(f"Areas of expertise: {', '.join(profile['expertise'])}.")
    if profile.get("quirks"):
        parts.append(f"Quirks: {', '.join(profile['quirks'])}.")
    if profile.get("emoji_usage"):
        parts.append(f"Emoji usage: {profile['emoji_usage']}.")
    if profile.get("response_length"):
        parts.append(f"Response length: {profile['response_length']}.")
    if profile.get("relationship_to_user"):
        parts.append(f"Relationship to user: {profile['relationship_to_user']}.")
    if profile.get("boundaries"):
        parts.append(f"Boundaries: {profile['boundaries']}.")
    if profile.get("texting_style"):
        parts.append(f"Texting style: {profile['texting_style']}.")
    if profile.get("emotional_range"):
        parts.append(f"Emotional range: {profile['emotional_range']}.")
    if profile.get("custom_instructions"):
        parts.append(profile["custom_instructions"])

    return " ".join(parts), profile


PERSONA_CONTEXT, _PROFILE = load_profile()
_IMAGE_SETTINGS = {
    "negative_prompt": _PROFILE.get("image_negative_prompt", ""),
    "prompt_prefix": _PROFILE.get("image_prompt_prefix", ""),
    "prompt_suffix": _PROFILE.get("image_prompt_suffix", ""),
}


def build_response_system_prompt(thinking, memory_context="", search_context=""):
    """Build the system prompt for the response generator using
    the inner monologue's output."""
    parts = [PERSONA_CONTEXT]

    if search_context:
        parts.append(
            f"\nWeb search results (use to inform your response, cite naturally):\n{search_context}"
        )

    if memory_context:
        parts.append(f"\nRelevant context from past conversations:\n{memory_context}")

    # Inject the inner monologue's guidance
    parts.append(f"\nYour inner thoughts about this moment:\n{thinking.get('inner_thoughts', '')}")
    parts.append(f"\nResponse strategy: {thinking.get('response_strategy', 'be natural')}")
    parts.append(f"Tone to use: {thinking.get('tone', 'warm and casual')}")
    parts.append(f"Message style: {thinking.get('message_style', 'single short message')}")

    target_count = thinking.get("message_count", 1)
    if target_count > 1:
        parts.append(
            f"\nIMPORTANT: Structure your reply as {target_count} separate short messages, "
            f"separated by double newlines. Write like you're texting — short, natural, "
            f"conversational. Do NOT write a single long block of text."
        )
    else:
        parts.append(
            "\nKeep your reply concise and natural, like a single text message."
        )

    key_points = thinking.get("key_points", [])
    if key_points:
        parts.append(f"\nKey points to address: {', '.join(key_points)}")

    # Image generation (decided by inner monologue)
    if thinking.get("should_generate_image") and thinking.get("image_prompt"):
        parts.append(
            "\nInclude this image generation tag at the end of your reply:\n"
            f"[GENERATE_IMAGE: {thinking['image_prompt']}]"
        )

    return "\n".join(parts)


def _should_recall(thinking):
    """Determine whether to run a long-term memory recall."""
    history_len = len(conversation_history)

    # Always recall on the very first message of a session
    if history_len <= 1:
        return True

    # Periodic forced recall as a safety net
    if _message_counter % Config.MEMORY_FORCED_RECALL_INTERVAL == 0:
        return True

    # Short conversation: skip unless monologue explicitly requests it
    if history_len < Config.MEMORY_SHORT_CONV_THRESHOLD:
        return False

    # Defer to the inner monologue's judgment
    return thinking.get("needs_memory_lookup", False)


def _maybe_remember(user_message, bot_response, thinking):
    """Conditionally store the exchange in long-term memory."""
    # Never store if conversation is very short
    if len(conversation_history) < Config.MEMORY_SHORT_CONV_THRESHOLD:
        return

    # Check if the monologue thinks this is worth storing
    if not thinking.get("should_store_memory", False):
        return

    # Add to pending buffer
    _pending_memory_exchanges.append((user_message, bot_response))

    # Flush the buffer when it reaches batch size
    if len(_pending_memory_exchanges) >= Config.MEMORY_BATCH_SIZE:
        _flush_memory_buffer()


def _flush_memory_buffer():
    """Store all pending exchanges in long-term memory at once."""
    if not _pending_memory_exchanges:
        return
    try:
        combined = "\n\n".join(
            f"User: {um}\nAssistant: {br}"
            for um, br in _pending_memory_exchanges
        )
        memory_service.batch_remember(combined)
    except Exception:
        pass
    finally:
        _pending_memory_exchanges.clear()


atexit.register(_flush_memory_buffer)


@app.route("/")
def index():
    return render_template("index.html", chatbot_name=_PROFILE.get("name", "Vessel"))


@app.route("/api/chat", methods=["POST"])
def chat():
    global _message_counter

    user_message = request.json.get("message", "")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    conversation_history.append({"role": "user", "content": user_message})
    _message_counter += 1

    # Step 1: Inner monologue FIRST — emotion + planning + memory gating (1 Ollama call)
    emotion_history = emotion_tracker.get_history_string()
    thinking = inner_monologue.think(
        conversation_history, PERSONA_CONTEXT, emotion_history
    )

    # Update emotion tracker with results
    emotion_tracker.update(
        thinking.get("user_emotion", "neutral"),
        thinking.get("emotional_shift", "stable"),
    )

    # Step 2: Conditionally run web search
    search_context = ""
    if thinking.get("needs_web_search") and thinking.get("search_query"):
        search_context = web_search_service.search(thinking["search_query"])

    # Step 3: Conditionally retrieve memory context
    memory_context = ""
    if _should_recall(thinking):
        memory_context = memory_service.recall(user_message)

    # Step 4: Build the guided system prompt
    system_prompt = build_response_system_prompt(thinking, memory_context, search_context)
    target_message_count = thinking.get("message_count", 1)

    def generate():
        # Step 4: Generate response (streamed from Ollama — 2nd Ollama call)
        full_response = ""
        try:
            for chunk in ollama_service.stream_chat(
                conversation_history, system_prompt=system_prompt
            ):
                full_response += chunk
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield 'data: {"type": "done"}\n\n'
            return

        # Step 5: Clean up and check for image tags
        image_prompt = image_trigger.check_response(full_response)
        cleaned = image_trigger.clean_response(full_response)

        # Step 6: Split into messages and deliver with realistic timing
        messages = delivery_service.split_response(cleaned, target_message_count)

        for i, msg in enumerate(messages):
            if i > 0:
                delay = delivery_service.inter_message_delay()
                yield f"data: {json.dumps({'type': 'typing', 'delay': delay})}\n\n"
                time.sleep(delay / 1000.0)

            typing_delay = delivery_service.calculate_delay(msg)
            yield f"data: {json.dumps({'type': 'typing', 'delay': typing_delay})}\n\n"
            time.sleep(typing_delay / 1000.0)

            yield f"data: {json.dumps({'type': 'message', 'content': msg})}\n\n"

        # Store cleaned full response in conversation history
        conversation_history.append({"role": "assistant", "content": cleaned})

        # Step 7: Handle image generation if triggered
        if image_prompt:
            yield f"data: {json.dumps({'type': 'image_generating', 'prompt': image_prompt})}\n\n"
            try:
                image_url = comfyui_service.generate_image(image_prompt, **_IMAGE_SETTINGS)
                yield f"data: {json.dumps({'type': 'image', 'url': image_url})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Image generation failed: {e}'})}\n\n"

        yield 'data: {"type": "done"}\n\n'

        # Step 8: Conditionally store in long-term memory
        _maybe_remember(user_message, cleaned, thinking)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/imagine", methods=["POST"])
def imagine():
    prompt = request.json.get("prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    try:
        image_url = comfyui_service.generate_image(prompt, **_IMAGE_SETTINGS)
        conversation_history.append(
            {"role": "user", "content": f"/imagine {prompt}"}
        )
        conversation_history.append(
            {"role": "assistant", "content": f"[Generated image: {prompt}]"}
        )
        return jsonify({"url": image_url, "prompt": prompt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pings")
def pings():
    msg = ping_service.get_pending()
    if msg:
        conversation_history.append({"role": "assistant", "content": msg})
        return jsonify({"message": msg})
    return jsonify({"message": None})


@app.route("/api/forget", methods=["POST"])
def forget():
    global _message_counter
    conversation_history.clear()
    _pending_memory_exchanges.clear()
    _message_counter = 0
    ping_service.reset()
    try:
        memory_service.forget()
    except Exception:
        pass
    return jsonify({"status": "memory cleared"})


atexit.register(ping_service.stop)


if __name__ == "__main__":
    memory_service.init_memory()
    ping_service.start(
        _PROFILE.get("proactive_messaging", {}),
        PERSONA_CONTEXT,
        conversation_history,
    )
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True,
    )
