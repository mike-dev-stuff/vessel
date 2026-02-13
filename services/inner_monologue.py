"""Inner monologue agent: a single 'thinking' LLM call that combines
emotion analysis, response planning, and persona reasoning before
the visible response is generated.

Returns structured JSON that guides the response generator.
"""

import json
from services import ollama_service

MONOLOGUE_SYSTEM_PROMPT = """\
You are the inner thought process of a chatbot character. You do NOT produce the \
visible reply — you only think and plan. Analyze the conversation and output a \
JSON object with these fields:

{
  "user_emotion": "the user's current emotional state (e.g. happy, frustrated, curious, sad, playful, neutral)",
  "emotional_shift": "how the user's emotion changed from the previous message (e.g. stable, escalating, calming, shifted)",
  "response_strategy": "how to respond (e.g. match energy, be supportive, be playful, ask follow-up, go deep, keep brief)",
  "message_style": "how to structure the reply (e.g. single short message, two casual messages, one longer thoughtful message)",
  "message_count": 1,
  "tone": "the specific tone to use (e.g. warm and casual, gently encouraging, excited, deadpan humor)",
  "key_points": ["what to mention or address in the response"],
  "should_generate_image": false,
  "image_prompt": null,
  "needs_memory_lookup": false,
  "should_store_memory": false,
  "needs_web_search": false,
  "search_query": null,
  "inner_thoughts": "free-form reasoning about the character's feelings, memories, and what they would naturally think before replying"
}

Rules:
- message_count should be 1-3, driven by emotional energy:
  * 1 message: neutral, calm, or brief acknowledgments
  * 2 messages: engaged, conversational, or making a point with a follow-up
  * 3 messages: excited, enthusiastic, surprised, or emotionally charged moments
- Keep inner_thoughts authentic to the character's personality.
- should_generate_image: {image_frequency}
- If generating an image, set image_prompt to a detailed visual description. {image_prompt_instructions}
- Set needs_memory_lookup to true ONLY when the user references something from a \
previous session, asks about a past conversation topic, or asks something you \
cannot answer from the visible conversation history alone. If the answer is \
already visible in the conversation, set it to false.
- Set should_store_memory to true when the user shares meaningful personal \
information (preferences, facts about themselves, important events), makes a \
decision worth remembering, or discusses something valuable to recall in future \
sessions. Set it to false for casual chit-chat, greetings, or transient information.
- Set needs_web_search to true ONLY when the user explicitly asks about current \
events, recent news, or specific real-time facts that are impossible to answer from \
training data alone. Do NOT search for general knowledge, opinions, or anything you \
can answer on your own. When true, set search_query to a concise web search query.
- Do NOT end every message with a question. Real people make statements, react, \
share thoughts, and let silences happen. Only ask a question when genuinely curious \
or when the conversation naturally calls for it — not as a default filler.
- Output ONLY valid JSON, no other text.\
"""


def think(conversation_history, persona_context, emotion_history="",
          image_frequency="only when a visual would genuinely add value",
          image_prompt_instructions=""):
    """Run the inner monologue. Returns a dict with thinking results."""
    # Build a focused prompt with just enough context
    prompt = MONOLOGUE_SYSTEM_PROMPT.format(
        image_frequency=image_frequency,
        image_prompt_instructions=image_prompt_instructions,
    )
    system = f"{prompt}\n\nCharacter context:\n{persona_context}"
    if emotion_history:
        system += f"\n\nRecent emotional trajectory:\n{emotion_history}"

    response = ollama_service.chat(conversation_history, system_prompt=system)

    # Parse JSON from response, handling potential markdown wrapping
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback if model doesn't produce valid JSON
        return {
            "user_emotion": "neutral",
            "emotional_shift": "stable",
            "response_strategy": "be natural and conversational",
            "message_style": "single short message",
            "message_count": 1,
            "tone": "warm and casual",
            "key_points": [],
            "should_generate_image": False,
            "image_prompt": None,
            "needs_memory_lookup": False,
            "should_store_memory": False,
            "needs_web_search": False,
            "search_query": None,
            "inner_thoughts": "",
        }
