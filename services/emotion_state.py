"""Lightweight emotional state tracker. No LLM calls — just stores
the state produced by the inner monologue agent and provides
a rolling history string for context."""


class EmotionTracker:
    def __init__(self, max_history=10):
        self._history = []
        self._max = max_history
        self.current = "neutral"

    def update(self, emotion, shift="stable"):
        """Record a new emotional state from the inner monologue."""
        self.current = emotion
        self._history.append({"emotion": emotion, "shift": shift})
        if len(self._history) > self._max:
            self._history = self._history[-self._max :]

    def get_history_string(self):
        """Return a concise summary for the inner monologue's context."""
        if not self._history:
            return ""
        recent = self._history[-5:]
        parts = [f"{e['emotion']} ({e['shift']})" for e in recent]
        return "User emotional trajectory (oldest→newest): " + " → ".join(parts)


# Module-level singleton (single-user app)
tracker = EmotionTracker()
