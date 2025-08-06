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
        
        self.memory: Dict[str, Any] = {}
        self.MEMORY_TIMEOUT_S: int = 30
        self.FOLLOW_UP_KEYWORDS: List[str] = [
            "it", "that", "this", "on the same topic", "again", "for that", "do that",
            "the first one", "the second one", "first", "second"
        ]
        self.WRITE_KEYWORDS: List[str] = [
            "write", "generate", "create a function", "code me", "draft"
        ]
        
        self.conversation_state: str | None = None
        self.conversation_data: Dict[str, Any] = {}
        self.CONVERSATION_TIMEOUT_S: int = 60
        self.last_interaction_time: float = 0.0

        self.reload_intents()
        self.settings_manager.settings_updated.connect(self.reload_intents)

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
        self.canonical_phrases = [
            intent.canonical 
            for intent in intents_dict.values() 
            if hasattr(intent, 'canonical') and intent.canonical
        ]
        if self.canonical_phrases:
            self.canonical_embeddings = self.model.encode(self.canonical_phrases, convert_to_tensor=True)
        else:
            self.canonical_embeddings = None
        self.intent_keys = [
            key 
            for key, intent in intents_dict.items() 
            if hasattr(intent, 'canonical') and intent.canonical
        ]
        logger.info(f"Reloaded {len(intents_dict)} intents, with {len(self.canonical_phrases)} canonicals.")


    def _clear_expired_memory(self) -> None:
        if "timestamp" in self.memory and (time.time() - self.memory["timestamp"]) > self.MEMORY_TIMEOUT_S:
            logger.info("NLU short-term memory expired and has been cleared.")
            self.memory.clear()

    def _clear_expired_conversation(self) -> None:
        if self.conversation_state and (time.time() - self.last_interaction_time) > self.CONVERSATION_TIMEOUT_S:
            logger.info("Conversation timed out and has been reset.")
            self.conversation_state = None
            self.conversation_data = {}

    def _handle_active_conversation(self, text: str) -> tuple[str | None, Dict[str, Any] | None, str | None]:
        self.last_interaction_time = time.time()
        text_lower = text.lower()
        
        if self.conversation_state == "AWAITING_REMINDER_CONTENT":
            self.conversation_data['content'] = text
            self.conversation_state = "AWAITING_REMINDER_TIME"
            prompt = "Got it. When should I remind you?"
            return None, None, prompt

        elif self.conversation_state == "AWAITING_REMINDER_TIME":
            entities = self.ner_handler.extract_entities(text)
            date_entity = " ".join(entities.get("DATE", []))
            time_entity = " ".join(entities.get("TIME", []))
            full_time_entity = f"{date_entity} {time_entity}".strip() or text
            self.conversation_data['time'] = full_time_entity
            final_intent = "[CREATE_SCHEDULED_REMINDER]"
            final_entities = {"content": self.conversation_data['content'], "time": self.conversation_data['time']}
            prompt = f"Okay, reminder set for {final_entities['content']} at {final_entities['time']}."
            self.conversation_state = None
            self.conversation_data = {}
            return final_intent, final_entities, prompt

        elif self.conversation_state == "AWAITING_AMBIGUITY_RESOLUTION":
            candidates = self.conversation_data.get("candidates", [])
            chosen_intent = None
            if "first" in text_lower or (len(candidates) > 0 and candidates[0][0].lower().replace("_", " ") in text_lower):
                chosen_intent = candidates[0][0]
            elif "second" in text_lower or (len(candidates) > 1 and candidates[1][0].lower().replace("_", " ") in text_lower):
                chosen_intent = candidates[1][0]
            
            if chosen_intent:
                logger.info(f"Ambiguity resolved by user. Choosing intent: {chosen_intent}")
                original_text = self.conversation_data.get("original_text", "")
                self.conversation_state = None 
                self.conversation_data = {}
                return self.process_intent(chosen_intent, original_text)
            else:
                prompt = "Sorry, I didn't understand. Please say 'the first one' or 'the second one'."
                return None, None, prompt

        return None, None, None

    def _classify_intent(self, text: str, context: str | None = None) -> List[Tuple[str, float]]:
        text_lower = text.lower()
        all_intents = self.settings_manager.settings.intents
        applicable_intents: Dict[str, Any] = {}
        
        # --- START: Paranoid Mode Enforcement ---
        paranoid_mode = self.settings_manager.settings.core.paranoid_mode_enabled
        
        safe_intents = all_intents
        if paranoid_mode:
            logger.warning("PARANOID MODE ACTIVE: Filtering high-risk intents.")
            safe_intents = {
                name: intent_data for name, intent_data in all_intents.items()
                if not intent_data.is_high_risk
            }
        # --- END: Paranoid Mode Enforcement ---

        if context:
            for name, intent_data in safe_intents.items():
                if hasattr(intent_data, 'contexts') and context in intent_data.contexts:
                    applicable_intents[name] = intent_data
        
        for name, intent_data in safe_intents.items():
            if not (hasattr(intent_data, 'contexts') and intent_data.contexts):
                if name not in applicable_intents:
                    applicable_intents[name] = intent_data
        
        for intent_name, intent_data in applicable_intents.items():
            if hasattr(intent_data, 'keywords'):
                for keyword in intent_data.keywords:
                    if keyword.lower() in text_lower:
                        return [(intent_name, 1.0)]

        if not self.model or not self.intent_keys: return []
        
        text_embedding = self.model.encode(text, convert_to_tensor=True)
        cosine_scores = util.cos_sim(text_embedding, self.canonical_embeddings)[0]
        
        top_results = torch.topk(cosine_scores, k=min(3, len(self.intent_keys)))
        
        results = []
        for score, idx in zip(top_results.values, top_results.indices):
            intent_name = self.intent_keys[idx]
            if intent_name in applicable_intents:
                results.append((intent_name, score.item()))
        
        return results

    def _extract_entities_whatsapp(self, text: str) -> Dict[str, str] | None:
        pattern = re.compile(r'(?:tell|send a message to|send a whatsapp to)\s+(.+?)\s+(?:that|saying|to say)\s+(.+)', re.IGNORECASE)
        match = pattern.search(text)
        if match:
            recipient = match.group(1).strip()
            message = match.group(2).strip()
            return {"recipient": recipient, "message": message}
        return None

    def _extract_entity(self, text: str, triggers: list[str]) -> str | None:
        text_lower = text.lower()
        best_trigger = ""
        for trigger in triggers:
            if trigger.lower() in text_lower and len(trigger) > len(best_trigger):
                best_trigger = trigger
        
        if best_trigger:
            trigger_lower = best_trigger.lower()
            start_index = text_lower.find(trigger_lower) + len(trigger_lower)
            entity = text[start_index:].lstrip(" ,:").strip()
            if entity: return entity
        return None

    def process_intent(self, intent: str, text: str) -> tuple[str | None, Dict[str, Any] | None, str | None]:
        entities: Dict[str, Any] | None = None
        prompt = None
        
        if intent in ["EXECUTE_DYNAMIC_TASK", "WRITE_CODE"]:
            entities = {"query": text}
        elif intent == "SEND_WHATSAPP_MESSAGE":
            entities = self._extract_entities_whatsapp(text)
        elif intent and intent != "UNKNOWN_INTENT":
            intent_data = self.settings_manager.settings.intents.get(intent)
            if intent_data:
                if hasattr(intent_data, 'starts_conversation') and intent_data.starts_conversation:
                    self.conversation_state = intent_data.conversation_state
                    self.conversation_data = {"original_intent": intent}
                    self.last_interaction_time = time.time()
                    prompt = intent_data.initial_prompt
                
                if hasattr(intent_data, 'triggers') and intent_data.triggers:
                    single_entity = self._extract_entity(text, intent_data.triggers)
                    if single_entity:
                        entities = {"entity": single_entity}
        
        is_follow_up = any(keyword in text.lower() for keyword in self.FOLLOW_UP_KEYWORDS)
        if not entities and is_follow_up and "entities" in self.memory:
            entities = self.memory.get("entities")
            if intent == "UNKNOWN_INTENT" and "intent" in self.memory:
                intent = self.memory.get("intent")

        if entities and intent not in ["EXECUTE_DYNAMIC_TASK", "WRITE_CODE"]:
            self.memory = {"intent": intent, "entities": entities, "timestamp": time.time()}
        
        return (f"[{intent}]", entities, prompt)

    def process(self, text: str, context: str | None = None) -> tuple[str | None, Dict[str, Any] | None, str | None]:
        self.last_interaction_time = time.time()
        self._clear_expired_memory()
        self._clear_expired_conversation()

        if self.conversation_state:
            return self._handle_active_conversation(text)

        intent_candidates = self._classify_intent(text, context)
        
        if not intent_candidates:
            if any(keyword in text.lower() for keyword in self.WRITE_KEYWORDS):
                return self.process_intent("WRITE_CODE", text)
            if len(text.split()) > 4:
                return self.process_intent("EXECUTE_DYNAMIC_TASK", text)
            return "[UNKNOWN_INTENT]", None, None

        top_intent, top_score = intent_candidates[0]
        
        HIGH_CONFIDENCE_THRESHOLD = 0.85
        AMBIGUITY_THRESHOLD = 0.15

        if top_score >= HIGH_CONFIDENCE_THRESHOLD:
            logger.debug(f"High confidence match: {top_intent} ({top_score:.2f})")
            return self.process_intent(top_intent, text)
        
        if len(intent_candidates) > 1:
            second_intent, second_score = intent_candidates[1]
            if (top_score - second_score) < AMBIGUITY_THRESHOLD:
                logger.info(f"Ambiguous command detected. Candidates: {top_intent}, {second_intent}")
                self.conversation_state = "AWAITING_AMBIGUITY_RESOLUTION"
                self.conversation_data = {
                    "original_text": text,
                    "candidates": [(top_intent, top_score), (second_intent, second_score)]
                }
                prompt = f"Did you mean {top_intent.replace('_', ' ').lower()}, or {second_intent.replace('_', ' ').lower()}?"
                return None, None, prompt

        MIN_CONFIDENCE_THRESHOLD = 0.5
        if top_score >= MIN_CONFIDENCE_THRESHOLD:
            logger.debug(f"Low confidence match: {top_intent} ({top_score:.2f})")
            return self.process_intent(top_intent, text)

        if any(keyword in text.lower() for keyword in self.WRITE_KEYWORDS):
            return self.process_intent("WRITE_CODE", text)
        if len(text.split()) > 4:
            return self.process_intent("EXECUTE_DYNAMIC_TASK", text)
        
        return "[UNKNOWN_INTENT]", None, None