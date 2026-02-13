import os
import asyncio
import cognee
from config import Config


def init_memory():
    """Configure Cognee for local Ollama usage. Call once at startup."""
    # Point Cognee's LLM + embeddings at the same Ollama instance used for chat
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("LLM_MODEL", Config.OLLAMA_MODEL)
    os.environ.setdefault("LLM_ENDPOINT", f"{Config.OLLAMA_BASE_URL}/v1")
    os.environ.setdefault("LLM_API_KEY", "ollama")
    os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
    os.environ.setdefault("EMBEDDING_MODEL", "nomic-embed-text")
    os.environ.setdefault(
        "EMBEDDING_ENDPOINT", f"{Config.OLLAMA_BASE_URL}/api/embeddings"
    )
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")
    os.environ.setdefault(
        "HUGGINGFACE_TOKENIZER", "Salesforce/SFR-Embedding-Mistral"
    )


async def _recall(user_message):
    """Search Cognee for relevant past context."""
    try:
        results = await cognee.search(query_text=user_message)
        if not results:
            return ""
        fragments = []
        for r in results:
            text = str(r) if not isinstance(r, str) else r
            if text.strip():
                fragments.append(text.strip())
        return "\n".join(fragments) if fragments else ""
    except Exception:
        return ""


async def _remember(user_message, bot_response):
    """Store a conversation exchange and rebuild the knowledge graph."""
    exchange = f"User: {user_message}\nAssistant: {bot_response}"
    try:
        await cognee.add(exchange)
        await cognee.cognify()
    except Exception:
        pass


async def _batch_remember(combined_text):
    """Store a pre-formatted block of exchanges and rebuild the knowledge graph.
    Used for batched memory storage (multiple exchanges at once)."""
    try:
        await cognee.add(combined_text)
        await cognee.cognify()
    except Exception:
        pass


async def _forget():
    """Reset all stored memory."""
    await cognee.prune.prune_data()


def recall(user_message):
    """Sync wrapper for recall."""
    return asyncio.run(_recall(user_message))


def remember(user_message, bot_response):
    """Sync wrapper for remember."""
    asyncio.run(_remember(user_message, bot_response))


def batch_remember(combined_text):
    """Sync wrapper for batch_remember."""
    asyncio.run(_batch_remember(combined_text))


def forget():
    """Sync wrapper for forget."""
    asyncio.run(_forget())
