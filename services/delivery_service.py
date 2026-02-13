"""Message splitting and realistic delivery timing.

Splits a single LLM response into multiple short messages and
calculates per-message typing delays to simulate natural texting.
"""

import random
import re


# Milliseconds per character for simulated typing speed
MIN_MS_PER_CHAR = 30
MAX_MS_PER_CHAR = 60
# Minimum/maximum delay between messages in milliseconds
MIN_INTER_MSG_DELAY = 400
MAX_INTER_MSG_DELAY = 1500
# Minimum delay for any message
MIN_DELAY = 300


def split_response(text, target_count=None):
    """Split a response into multiple short messages.

    If target_count is provided (from inner monologue), tries to split
    into approximately that many parts. Otherwise splits on natural
    boundaries (double newlines, sentence endings).
    """
    text = text.strip()
    if not text:
        return [""]

    # If the text is already short, don't split
    if len(text) < 60 or target_count == 1:
        return [text]

    # Split on double newlines first (paragraph breaks)
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    if len(paragraphs) >= 2:
        messages = paragraphs
    else:
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= 1:
            return [text]

        # Group sentences into messages of roughly equal length
        count = target_count or _estimate_message_count(text)
        count = min(count, len(sentences), 4)
        messages = _group_sentences(sentences, count)

    # Cap at 4 messages
    if len(messages) > 4:
        messages = _group_sentences(messages, 4)

    return [m.strip() for m in messages if m.strip()]


def calculate_delay(message_text):
    """Calculate a realistic typing delay in milliseconds for a message."""
    length = len(message_text)
    ms_per_char = random.uniform(MIN_MS_PER_CHAR, MAX_MS_PER_CHAR)
    delay = int(length * ms_per_char)
    # Add some random variation
    delay += random.randint(-100, 200)
    return max(delay, MIN_DELAY)


def inter_message_delay():
    """Calculate delay between consecutive messages in milliseconds."""
    return random.randint(MIN_INTER_MSG_DELAY, MAX_INTER_MSG_DELAY)


def _estimate_message_count(text):
    """Heuristic for how many messages to split into."""
    length = len(text)
    if length < 100:
        return 1
    elif length < 200:
        return 2
    elif length < 400:
        return 3
    else:
        return 4


def _group_sentences(sentences, target_count):
    """Group a list of sentences into target_count roughly equal groups."""
    if target_count >= len(sentences):
        return sentences

    total_len = sum(len(s) for s in sentences)
    target_len = total_len / target_count

    groups = []
    current = []
    current_len = 0

    for sentence in sentences:
        current.append(sentence)
        current_len += len(sentence)

        if current_len >= target_len and len(groups) < target_count - 1:
            groups.append(" ".join(current))
            current = []
            current_len = 0

    if current:
        groups.append(" ".join(current))

    return groups
