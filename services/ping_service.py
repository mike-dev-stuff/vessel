"""Proactive ping service — background timer that occasionally generates
unsolicited messages from the chatbot, like a real friend texting."""

import random
import threading
from collections import deque
from datetime import datetime

from services import ollama_service

# Module-level state
_ping_queue = deque(maxlen=1)
_timer = None
_config = None
_persona_context = ""
_conversation_history = None  # reference to the global list in app.py


def start(profile_config, persona_context, conversation_history_ref):
    """Start the recurring ping timer. Call once at app startup."""
    global _config, _persona_context, _conversation_history
    _config = profile_config or {}
    _persona_context = persona_context
    _conversation_history = conversation_history_ref

    if not _config.get("enabled", False):
        return

    _schedule_next()


def stop():
    """Cancel the timer for clean shutdown."""
    global _timer
    if _timer is not None:
        _timer.cancel()
        _timer = None


def reset():
    """Clear pending pings and restart the timer."""
    _ping_queue.clear()
    stop()
    if _config and _config.get("enabled", False):
        _schedule_next()


def get_pending():
    """Pop and return the next pending ping message, or None."""
    try:
        return _ping_queue.popleft()
    except IndexError:
        return None


def _schedule_next():
    """Schedule the next check."""
    global _timer
    interval = _config.get("check_interval_seconds", 300)
    _timer = threading.Timer(interval, _check_and_ping)
    _timer.daemon = True
    _timer.start()


def _get_time_block(hour):
    """Map an hour (0-23) to a time block name."""
    if hour < 7:
        return "night"
    elif hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


def _check_and_ping():
    """Timer callback: decide whether to send a ping, then reschedule."""
    # Always reschedule first so the loop continues
    _schedule_next()

    now = datetime.now()
    hour = now.hour

    # Respect quiet hours
    quiet = _config.get("quiet_hours", [0, 7])
    if len(quiet) == 2 and quiet[0] <= hour < quiet[1]:
        return

    # Don't queue if there's already an undelivered ping
    if _ping_queue:
        return

    # Probability check weighted by time of day
    base_prob = _config.get("base_probability", 0.3)
    time_weights = _config.get("time_weights", {})
    block = _get_time_block(hour)
    weight = time_weights.get(block, 0.5)

    if random.random() >= base_prob * weight:
        return

    # Generate and queue a ping
    try:
        msg = _generate_ping()
        if msg and msg.strip():
            _ping_queue.append(msg.strip())
    except Exception:
        pass


def _generate_ping():
    """Use Ollama to generate a short unprompted message."""
    topics = _config.get("topics", ["share a thought"])
    topic = random.choice(topics)

    system = (
        f"{_persona_context}\n\n"
        f"You're reaching out to the user unprompted, like a real friend texting. "
        f"Send a short, natural message. Your angle: {topic}. "
        f"Keep it to 1-2 short sentences max. Be casual and genuine. "
        f"Do NOT ask multiple questions. Do NOT be overly enthusiastic. "
        f"Do NOT mention that you were prompted or programmed to message."
    )

    # Give the LLM recent conversation context if available
    context_messages = []
    if _conversation_history:
        recent = list(_conversation_history[-6:])
        if recent:
            context_messages = recent

    # Add a nudge as the "user" message to trigger generation
    context_messages.append({
        "role": "user",
        "content": "(The user hasn't messaged in a while. Reach out naturally.)",
    })

    return ollama_service.chat(context_messages, system_prompt=system)
