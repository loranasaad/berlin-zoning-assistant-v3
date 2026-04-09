"""
chain/llm.py — LLM factory.

Pattern: consistent with all LangChain Academy notebooks.
Nodes import get_llm() instead of instantiating LLMs directly so the
provider can be switched at runtime without touching node code.
"""

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENAI_MODEL_ID, ANTHROPIC_MODEL_ID


def get_llm(provider: str = "openai"):
    if provider == "openai":
        return ChatOpenAI(
            model=OPENAI_MODEL_ID,
            openai_api_key=OPENAI_API_KEY,
            temperature=0,
        )
    if provider == "anthropic":
        return ChatAnthropic(
            model=ANTHROPIC_MODEL_ID,
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0,
        )
    raise ValueError(f"Unknown LLM provider: {provider!r}. Expected 'openai' or 'anthropic'.")
