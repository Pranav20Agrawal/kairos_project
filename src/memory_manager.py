# src/memory_manager.py

import logging
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import hashlib
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = "nexus_db"
COLLECTION_NAME = "kairos_nexus"

class MemoryManager:
    """Manages the long-term vector memory (Nexus) for K.A.I.R.O.S."""

    def __init__(self, sentence_transformer_model) -> None:
        """
        Initializes the MemoryManager and connects to the ChromaDB collection.

        Args:
            sentence_transformer_model: The loaded SentenceTransformer model instance.
        """
        self.client = None
        self.collection = None
        self.embedding_function = None

        if sentence_transformer_model is None:
            logger.error("SentenceTransformer model is None. MemoryManager will be disabled.")
            return

        try:
            # FIX: Get the model name properly from SentenceTransformer
            model_name = self._get_model_name(sentence_transformer_model)
            
            # Create an embedding function using the model name
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model_name
            )
            
            # Ensure the database directory exists
            db_dir = Path(DB_PATH)
            db_dir.mkdir(exist_ok=True)

            self.client = chromadb.PersistentClient(path=str(db_dir))
            
            # Get or create the collection with the embedding function
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_function
            )
            logger.info(f"Successfully connected to ChromaDB collection '{COLLECTION_NAME}' with model '{model_name}'.")

        except Exception as e:
            logger.critical(f"Failed to initialize ChromaDB client or collection: {e}", exc_info=True)
            self.client = None
            self.collection = None

    def _get_model_name(self, sentence_transformer_model) -> str:
        """
        Safely extract the model name from a SentenceTransformer instance.
        Handles different versions and attributes.
        """
        # In newer versions of sentence-transformers, the path is stored differently.
        # The primary model is usually the first module.
        if hasattr(sentence_transformer_model, 'get_submodule'):
             # Accessing the internal structure to find the model path
            if '0_transformer' in sentence_transformer_model._modules:
                model_path = sentence_transformer_model._modules['0_transformer'].auto_model.config.name_or_path
                if model_path:
                    logger.info(f"Found model name via internal module: {model_path}")
                    return model_path

        # Fallback for other versions
        default_model = 'all-MiniLM-L6-v2'
        logger.warning(f"Could not determine model name reliably, using default: {default_model}")
        return default_model


    def add_memory(self, text_content: str, metadata: Dict[str, Any]) -> None:
        """Adds a new document (memory) to the collection."""
        if not self.collection:
            logger.warning("Cannot add memory, collection is not available.")
            return

        # Create a unique but deterministic ID for the content
        doc_id = hashlib.sha256(text_content.encode()).hexdigest()

        try:
            # Using 'upsert' prevents duplicates of the exact same text
            self.collection.upsert(
                documents=[text_content],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.info(f"Memory added/updated with ID: {doc_id[:10]}...")
        except Exception as e:
            logger.error(f"Failed to add memory to ChromaDB: {e}", exc_info=True)

    def query_memory(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]] | None:
        """
        Performs a semantic search on the memory collection.
        """
        if not self.collection:
            logger.error("Cannot query memory, collection is not available.")
            return None

        try:
            logger.info(f"Querying memory with: '{query_text}'")
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            if not results or not results.get('ids') or not results['ids'][0]:
                return []

            combined_results = []
            for i, result_id in enumerate(results['ids'][0]):
                combined_results.append({
                    "id": result_id,
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
            
            return combined_results
        except Exception as e:
            logger.error(f"Failed to query memory from ChromaDB: {e}", exc_info=True)
            return None