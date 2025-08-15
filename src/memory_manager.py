# src/memory_manager.py

import logging
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import hashlib
from typing import List, Dict, Any # <-- Add List, Dict, Any to the import

logger = logging.getLogger(__name__)

# ... (DB_PATH and the rest of the file header are unchanged)

class MemoryManager:
    # ... (__init__ and add_memory methods are unchanged) ...

    # --- ADD THIS ENTIRE NEW METHOD ---
    def query_memory(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]] | None:
        """
        Performs a semantic search on the memory collection.

        Args:
            query_text: The natural language question to ask.
            n_results: The maximum number of results to return.

        Returns:
            A list of results, or None if an error occurs.
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
            
            # The results dictionary is a bit complex, let's simplify it
            if not results or not results.get('ids') or not results['ids'][0]:
                return []

            # Combine the different parts of the result into a list of dictionaries
            combined_results = []
            for i, result_id in enumerate(results['ids'][0]):
                combined_results.append({
                    "id": result_id,
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] # How similar it is (lower is better)
                })
            
            return combined_results

        except Exception as e:
            logger.error(f"Failed to query memory from ChromaDB: {e}", exc_info=True)
            return None
    # --- END OF NEW METHOD ---