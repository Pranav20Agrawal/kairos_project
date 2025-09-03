# src/nlu_engine.py

from sentence_transformers import SentenceTransformer, util
import torch
from src.settings_manager import SettingsManager
from src.ner_handler import NerHandler
import logging
from typing import Any, Dict, List, Tuple
import time
import os
import re
import json

logger = logging.getLogger(__name__)

BASE_MODEL = 'all-MiniLM-L6-v2'
FINE_TUNED_MODEL_PATH = 'models/fine_tuned_nlu'

class NluEngine:
    def __init__(self, settings_manager: SettingsManager) -> None:
        self.settings_manager = settings_manager
        self.model: SentenceTransformer | None = None
        self.ner_handler = NerHandler()
        self._load_model()
        
        self.canonical_phrases: list[str] = []
        self.canonical_embeddings: Any = None
        self.intent_keys: list[str] = []
        
        # Load system index for local item detection
        self.system_index = self._load_system_index()
        
        self.reload_intents()
        self.settings_manager.settings_updated.connect(self.reload_intents)

    def _load_system_index(self) -> dict:
        """Load the system index for local applications and folders."""
        try:
            with open("system_index.json", 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load system index: {e}")
            return {"applications": {}, "folders": {}}

    def _load_model(self) -> None:
        model_to_load = BASE_MODEL
        if os.path.exists(FINE_TUNED_MODEL_PATH):
            logger.info(f"Found fine-tuned model at '{FINE_TUNED_MODEL_PATH}'. Loading...")
            model_to_load = FINE_TUNED_MODEL_PATH
        else:
            logger.info(f"No fine-tuned model found. Loading base model '{BASE_MODEL}'...")

        try:
            self.model = SentenceTransformer(model_to_load)
            logger.info(f"Semantic model '{model_to_load}' loaded successfully.")
        except Exception as e:
            logger.critical(f"Failed to load model from path '{model_to_load}': {e}", exc_info=True)
            self.model = None

    def reload_intents(self) -> None:
        if not self.model: return
        logger.info("Reloading intents and re-computing embeddings...")
        intents_dict = self.settings_manager.settings.intents
        macros_dict = self.settings_manager.settings.macros

        all_intents = {**intents_dict, **macros_dict}

        self.canonical_phrases = [
            intent.canonical 
            for intent in all_intents.values() 
            if hasattr(intent, 'canonical') and intent.canonical
        ]
        if self.canonical_phrases:
            self.canonical_embeddings = self.model.encode(self.canonical_phrases, convert_to_tensor=True)
        else:
            self.canonical_embeddings = None
        self.intent_keys = [
            key 
            for key, intent in all_intents.items() 
            if hasattr(intent, 'canonical') and intent.canonical
        ]
        logger.info(f"Reloaded {len(all_intents)} intents/macros, with {len(self.canonical_phrases)} canonicals.")

    def _is_local_item_query(self, text: str) -> bool:
        """
        Determines if the query is asking for a local application or folder.
        This is the core logic that prevents local commands from being treated as web searches.
        """
        text_lower = text.lower().strip()
        
        # Strong local indicators (folder-specific terms)
        local_folder_indicators = [
            "folder", "directory", "file", "project folder", 
            "downloads", "documents", "desktop", "pictures", "music", "videos"
        ]
        
        # Check for explicit folder requests
        for indicator in local_folder_indicators:
            if indicator in text_lower:
                return True
        
        # Check if any word in the query matches known local applications
        words = text_lower.replace("open ", "").replace("launch ", "").replace("run ", "").split()
        for word in words:
            if word in self.system_index.get("applications", {}):
                logger.debug(f"Found local application match: '{word}'")
                return True
            if word in self.system_index.get("folders", {}):
                logger.debug(f"Found local folder match: '{word}'")
                return True
        
        return False

    def _is_web_navigation_query(self, text: str) -> bool:
        """
        Determines if the query is asking for web navigation or search.
        """
        text_lower = text.lower().strip()
        
        # Web navigation triggers
        web_triggers = ["open", "go to", "search for", "find", "look up", "show me"]
        
        # Check if it starts with web triggers
        starts_with_web_trigger = any(text_lower.startswith(trigger) for trigger in web_triggers)
        
        # URL patterns (e.g., "open github.com")
        url_pattern = re.compile(r'([a-zA-Z0-9-]+\.)+(com|org|in|net|dev|io|ai|gg|tech)\b')
        has_url = bool(url_pattern.search(text_lower))
        
        # Site aliases (e.g., "open yt" -> YouTube)
        aliases = {"lc": "leetcode", "gfg": "geeksforgeeks", "yt": "youtube", "wiki": "wikipedia"}
        words = text_lower.split()
        has_alias = len(words) > 0 and words[0] in aliases
        
        # Known sites from the site map
        sites = set(self.settings_manager.settings.sites.keys())
        has_known_site = any(site in text_lower for site in sites)
        
        # Contextual search patterns (e.g., "find two sum on leetcode")
        has_contextual_search = bool(re.search(r"(.+)\s+on\s+(youtube|leetcode|gfg|geeksforgeeks|github)", text_lower))
        
        return (starts_with_web_trigger and not self._is_local_item_query(text)) or has_url or has_alias or has_known_site or has_contextual_search

    def _get_exact_keyword_match(self, text: str) -> str | None:
        """
        Finds the first intent that has an exact keyword match.
        This is for high-priority, non-ambiguous commands.
        """
        text_lower = text.lower()
        all_items = {**self.settings_manager.settings.intents, **self.settings_manager.settings.macros}

        # Sort by priority - more specific intents first
        priority_intents = ["OPEN_PROJECT_FOLDER", "ANALYZE_SCREEN", "GET_SYSTEM_STATS", "STOP_ACTION"]
        
        for intent_name in priority_intents:
            if intent_name in all_items:
                intent_data = all_items[intent_name]
                if hasattr(intent_data, 'keywords'):
                    for keyword in intent_data.keywords:
                        if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text_lower):
                            logger.info(f"Priority keyword match found for intent: {intent_name}")
                            return intent_name

        # Check remaining intents
        for name, data in all_items.items():
            if name in priority_intents:
                continue
            if not hasattr(data, 'keywords'): 
                continue
            for keyword in data.keywords:
                if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text_lower):
                    logger.info(f"Keyword match found for intent: {name}")
                    return name
        return None

    def _extract_entity(self, text: str, triggers: list[str]) -> str | None:
        text_lower = text.lower()
        best_trigger = ""
        for trigger in triggers:
            trigger_lower = trigger.lower()
            if text_lower.startswith(trigger_lower):
                if len(trigger_lower) > len(best_trigger):
                    best_trigger = trigger
        
        if best_trigger:
            entity = text[len(best_trigger):].strip()
            return entity if entity else None
        return text.strip()

    def process(self, text: str, context: str | None = None) -> tuple[str | None, Dict[str, Any] | None, str | None]:
        text_lower = text.lower().strip()
        logger.info(f"Processing NLU for: '{text}'")
        
        # ---- START DEBUG BLOCK ----
        start_time = time.time()
        query_embedding = self.model.encode(text, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, self.canonical_embeddings)[0]
        top_result = torch.topk(cos_scores, k=1)

        top_intent_index = top_result.indices[0].item()
        top_intent_score = top_result.values[0].item()
        top_intent_name = self.intent_keys[top_intent_index]

        logger.debug(f"NLU SEMANTIC SEARCH: Best match is '{top_intent_name}' with score {top_intent_score:.4f}")
        logger.debug(f"NLU Latency: {(time.time() - start_time) * 1000:.2f} ms")
        # ---- END DEBUG BLOCK ----

        # --- NEW CODE BLOCK START ---
        # PRIORITY 0: Exact keyword matching for unambiguous commands
        exact_match_intent = self._get_exact_keyword_match(text)
        if exact_match_intent:
            intent_data = self.settings_manager.settings.intents.get(exact_match_intent.strip("[]"))
            entities = None
            if intent_data and intent_data.triggers:
                entity_text = self._extract_entity(text, intent_data.triggers)
                if entity_text:
                    entities = {"entity": entity_text}
            return f"[{exact_match_intent}]", entities, None
        # --- NEW CODE BLOCK END ---
        
        # --- NEW LOGIC CASCADE ---

        # PRIORITY 1: Check for exact keyword match for specific, non-web intents
        all_intents = self.settings_manager.settings.intents
        for intent_name, intent_data in all_intents.items():
            # These intents take precedence over general web searches
            if intent_name in ["OPEN_PROJECT_FOLDER", "OPEN_LOCAL_ITEM"]:
                for keyword in intent_data.keywords:
                    if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text_lower):
                        logger.info(f"High-priority local keyword match: [{intent_name}]")
                        entity = self._extract_entity(text, intent_data.triggers)
                        return f"[{intent_name}]", {"entity": entity} if entity else None, None

        # PRIORITY 2: Check if it's a request to open a known local application or folder
        entity_to_check = self._extract_entity(text, ["open", "launch", "run"])
        if entity_to_check:
            entity_lower = entity_to_check.lower()
            if entity_lower in self.system_index["applications"] or entity_lower in self.system_index["folders"]:
                 logger.info(f"Query identified as LOCAL item request: '{entity_lower}'")
                 return "[OPEN_LOCAL_ITEM]", {"entity": entity_lower}, None
            # Fuzzy check
            for app in self.system_index["applications"]:
                if entity_lower in app:
                    logger.info(f"Query identified as fuzzy LOCAL item request: '{app}'")
                    return "[OPEN_LOCAL_ITEM]", {"entity": app}, None


        # PRIORITY 3: If not a specific local command, check if it's a web command
        web_nav_triggers = ["open", "go to", "search for", "find", "look up", "show me"]
        if any(text_lower.startswith(trigger) for trigger in web_nav_triggers):
            entity = self._extract_entity(text, web_nav_triggers)
            if entity:
                logger.info(f"Routing to SEARCH_AND_NAVIGATE with entity: '{entity}'")
                return "[SEARCH_AND_NAVIGATE]", {"entity": entity}, None

        # PRIORITY 4: Fallback to LLM for anything else that is ambiguous
        logger.info(f"No specific rule matched. Passing to LLM for dynamic task.")
        return "[EXECUTE_DYNAMIC_TASK]", {"query": text}, None