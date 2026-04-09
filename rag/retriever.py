import logging
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from rag.embeddings import get_or_create_vector_store
from config import ANTHROPIC_API_KEY, MODEL_ID, TOP_K_RESULTS
from ui.strings import RETRIEVER_STRINGS
from chain.prompts import CLASSIFIER_SYSTEM

logger = logging.getLogger(__name__)

def retrieve_and_format(
		query: str,
		vector_store: Chroma = None,
		language: str = "de",
) -> tuple[str, list[Document], dict]:
	total_input  = 0
	total_output = 0

	# Classify before retrieving — skip RAG entirely for tool queries
	category, classifier_usage = _classify_query(query)
	total_input  += classifier_usage["input_tokens"]
	total_output += classifier_usage["output_tokens"]

	if category == "tool":
		logger.info("RAG skipped — tool query, no regulation context needed")
		return "", [], {"input_tokens": total_input, "output_tokens": total_output}

	# Translation only runs for English regulation queries
	if language == "en":
		retrieval_query, translation_usage = _translate_to_german(query)
		total_input  += translation_usage["input_tokens"]
		total_output += translation_usage["output_tokens"]
	else:
		retrieval_query = query

	chunks  = _retrieve_relevant_chunks(retrieval_query, vector_store)
	context = _format_retrieved_context(chunks, language)

	retriever_usage = {"input_tokens": total_input, "output_tokens": total_output}
	return context, chunks, retriever_usage

# Classifies query as "regulation" or "tool" before deciding whether to run RAG.
# "tool" queries skip retrieval entirely — saves ~3,000 input tokens + one embedding call.
# Falls back to "regulation" on any error so retrieval always runs as safe default.
def _classify_query(query: str) -> tuple[str, dict]:
	try:
		llm = ChatAnthropic(
			model=MODEL_ID,
			anthropic_api_key=ANTHROPIC_API_KEY,
			temperature=0,
			max_tokens=5,
		)
		response = llm.invoke([
			{"role": "system", "content": CLASSIFIER_SYSTEM},
			{"role": "user",   "content": query},
		])
		result   = response.content.strip().lower()
		category = "tool" if "tool" in result else "regulation"
		usage    = _extract_usage(response)
		logger.info(f"Query classified as '{category}': '{query[:60]}' "
					f"({usage['input_tokens']}in / {usage['output_tokens']}out tokens)")
		return category, usage
	except Exception as e:
		logger.warning(f"Query classification failed, defaulting to 'regulation': {e}")
		return "regulation", {"input_tokens": 0, "output_tokens": 0}

# Translate English queries to German before embedding
def _translate_to_german(query: str) -> tuple[str, dict]:
	"""
	Translate an English query to German before embedding.
	The knowledge base documents are in German, so translating the query
	improves retrieval quality for English-language users — German-to-German
	matching produces significantly lower L2 distances than English-to-German.
	Falls back to the original query if translation fails so it never breaks the app.
	"""
	try:
		llm = ChatAnthropic(
			model=MODEL_ID,
			anthropic_api_key=ANTHROPIC_API_KEY,
			temperature=0,
			max_tokens=500,
		)
		response = llm.invoke(
			"Translate the following query into German legal and regulatory language, "
			"as it would appear in a German building code or zoning ordinance. "
			"Use formal legal phrasing (e.g. 'gelten', 'sind einzuhalten', 'vorgeschrieben'). "
			"Return only the translated text, nothing else.\n\n"
			+ query
		)
		translated = response.content.strip()
		usage      = _extract_usage(response)
		logger.info(f"Query translated: '{query[:60]}' -> '{translated[:60]}' "
					f"({usage['input_tokens']}in / {usage['output_tokens']}out tokens)")
		return translated, usage
	except Exception as e:
		logger.warning(f"Query translation failed, using original: {e}")
		return query, {"input_tokens": 0, "output_tokens": 0}

def _retrieve_relevant_chunks(query: str, vector_store: Chroma = None) -> list[Document]:
	"""Retrieve the top-k most relevant chunks for a query."""
	if vector_store is None:
		vector_store = get_or_create_vector_store()
	
	logger.info(f"Retrieving chunks for query: '{query[:80]}'")
	results = vector_store.similarity_search_with_score(query, k=TOP_K_RESULTS)
	chunks = []
	for doc, score in results:
		doc.metadata["retrieval_score"] = round(float(score), 4)
		chunks.append(doc)
	logger.info(f"Retrieved {len(chunks)} chunks")
	return chunks

def _format_retrieved_context(chunks: list[Document], language: str = "de") -> str:
	"""Format retrieved chunks into a single context string for the LLM prompt."""
	s = RETRIEVER_STRINGS.get(language, RETRIEVER_STRINGS["de"])
	
	if not chunks:
		return s["no_results"]

	context_parts = []
	for i, chunk in enumerate(chunks, 1):
		source = chunk.metadata.get("source", s["unknown_src"])
		page = chunk.metadata.get("page", "")
		page_info = f", {s['page_label']} {page + 1}" if page != "" else ""
		context_parts.append(
			f"[{s['source_label']} {i}: {source}{page_info}]\n{chunk.page_content}"
		)
	
	return "\n\n---\n\n".join(context_parts)

# Extracts actual token counts from a ChatAnthropic response object
def _extract_usage(response) -> dict:
	usage = getattr(response, "usage_metadata", None)
	if usage:
		return {
			"input_tokens":  usage.get("input_tokens",  0),
			"output_tokens": usage.get("output_tokens", 0),
		}
	return {"input_tokens": 0, "output_tokens": 0}
