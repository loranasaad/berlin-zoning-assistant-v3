import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Makes the same config.py work locally and on share.streamlit.io
def _get_secret(key: str) -> str | None:
	try:
		return st.secrets[key]
	except Exception:
		return os.getenv(key)

# API Keys
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = _get_secret("OPENAI_API_KEY")

# Language options
LANGUAGES = {
	"Deutsch": "de",
	"English": "en",
}

DEFAULT_LANGUAGE = "de"

# Models
ANTHROPIC_MODEL_ID = "claude-sonnet-4-6"
OPENAI_MODEL_ID    = "gpt-5.2"
MODEL_ID           = ANTHROPIC_MODEL_ID   # backward-compat alias for rag/retriever.py

EMBEDDING_MODEL = "text-embedding-3-small"

# Multi-LLM
LLM_PROVIDERS = {
	"OpenAI (GPT-5.2)":   "openai",
	"Anthropic (Claude)": "anthropic",
}
DEFAULT_LLM_PROVIDER = "openai"

# SQLite memory
SQLITE_MEMORY_PATH = "./memory.db"

# ChromaDB
CHROMA_DB_PATH         = "./chroma_db"
CHROMA_COLLECTION_NAME = "berlin_zoning"

# RAG settings
CHUNK_SIZE    = 2000
CHUNK_OVERLAP = 200
TOP_K_RESULTS = 6

# Pricing (USD per 1K tokens) for cost tracker
TOKEN_COSTS = {
	"input":  0.003,
	"output": 0.015,
}

# Data paths
DOCS_PATH = "./data/docs"

# Input validation
MIN_INPUT_LENGTH = 3
MAX_INPUT_LENGTH = 2000

# Rate limiting
RATE_LIMITING_ENABLED     = True
RATE_LIMIT_REQUESTS       = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# LangSmith — auto-configured at import if env vars are set
_LANGSMITH_TRACING = _get_secret("LANGSMITH_TRACING")
_LANGSMITH_API_KEY = _get_secret("LANGSMITH_API_KEY")
if _LANGSMITH_TRACING == "true" and _LANGSMITH_API_KEY:
	os.environ["LANGCHAIN_TRACING_V2"] = "true"
	os.environ["LANGCHAIN_API_KEY"]    = _LANGSMITH_API_KEY
	os.environ["LANGCHAIN_PROJECT"]    = _get_secret("LANGSMITH_PROJECT") or "berlin-zoning-assistant"
