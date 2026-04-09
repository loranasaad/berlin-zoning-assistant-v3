import logging
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import DOCS_PATH, CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

def load_and_split(docs_path: str = DOCS_PATH) -> list:
	"""
	Load all docs and split into chunks in one call.
	"""
	documents = load_documents(docs_path)
	if not documents:
		raise ValueError(f"No documents found in {docs_path}. Please add PDF or TXT files.")
	chunks = split_documents(documents)
	return chunks


def load_documents(docs_path: str = DOCS_PATH) -> list:
	"""
	Load all documents from the docs folder. Supports .pdf and .txt files.
	"""
	documents = []
	docs_dir = Path(docs_path)

	if not docs_dir.exists():
		logger.error(f"Docs directory not found: {docs_path}")
		return []
	
	for file_path in docs_dir.iterdir():
		docs = _load_single_file(file_path)
		if docs:
			documents.extend(docs)
	
	logger.info(f"Total documents loaded: {len(documents)}")
	return documents

def _load_single_file(file_path: Path) -> list:
	"""
	Load a single PDF or TXT file. Returns empty list if unsupported or failed.
	"""
	suffix = file_path.suffix.lower()

	if suffix == ".pdf":
		loader = PyPDFLoader(str(file_path))
	elif suffix == ".txt":
		loader = TextLoader(str(file_path), encoding="utf-8")
	else:
		logger.debug(f"Skipping unsupported file type: {file_path.name}")
		return []
	
	try:
		docs = loader.load()
		for doc in docs:
			doc.metadata["source"] = file_path.name
		logger.info(f"Loaded {len(docs)} page(s) from {file_path.name}")
		return docs
	except Exception as e:
		logger.error(f"Failed to load {file_path.name}: {e}")
		return []

def split_documents(documents: list) -> list:
	"""
	Split documents into chunks for embedding.
	"""
	splitter = RecursiveCharacterTextSplitter(
		chunk_size=CHUNK_SIZE,
		chunk_overlap=CHUNK_OVERLAP,
		separators=["\n\n", "\n", ".", " ", ""],
	)

	chunks = splitter.split_documents(documents)
	logger.info(f"Split into {len(chunks)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
	return chunks
