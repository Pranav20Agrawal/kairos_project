# src/ner_handler.py

import spacy
from spacy.language import Language
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class NerHandler:
    """Handles Named Entity Recognition using spaCy."""
    def __init__(self):
        self.nlp: Language | None = None
        self._load_model()
        # The entity labels we are interested in
        self.target_labels = {"DATE", "TIME", "PERSON", "GPE", "ORG", "LOC"}

    def _load_model(self) -> None:
        """Loads the spaCy pre-trained model."""
        try:
            logger.info("Loading spaCy NER model 'en_core_web_sm'...")
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy NER model loaded successfully.")
        except OSError:
            logger.error("spaCy model 'en_core_web_sm' not found.")
            logger.error("Please run 'python -m spacy download en_core_web_sm' to install it.")
            self.nlp = None
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {e}", exc_info=True)
            self.nlp = None

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extracts relevant named entities from a given text.

        Args:
            text: The user's spoken command.

        Returns:
            A dictionary where keys are entity labels (e.g., "DATE") and
            values are a list of the found entities (e.g., ["tomorrow", "10 AM"]).
        """
        if not self.nlp:
            return {}

        doc = self.nlp(text)
        entities: Dict[str, List[str]] = {}
        
        for ent in doc.ents:
            if ent.label_ in self.target_labels:
                if ent.label_ not in entities:
                    entities[ent.label_] = []
                entities[ent.label_].append(ent.text)
        
        if entities:
            logger.debug(f"NER found entities: {entities}")
            
        return entities