# src/llm_handler.py
import logging
import requests
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LlmHandler:
    """Handles the loading and execution of the local Large Language Model via Ollama."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model_name = "phi3" # We are using the phi3 model from Ollama
        self.is_ready = self._check_ollama_availability()

    def _check_ollama_availability(self) -> bool:
        """Checks if the Ollama server is running and the specified model is available."""
        try:
            logger.info(f"Checking for Ollama server at {self.ollama_url}...")
            response = requests.get(self.ollama_url, timeout=5)
            response.raise_for_status()
            logger.info("Ollama server is running.")

            # Now, check if the model is available
            logger.info(f"Verifying that model '{self.model_name}' is available in Ollama...")
            tags_response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            tags_response.raise_for_status()
            models = tags_response.json().get("models", [])
            
            model_found = any(self.model_name in m.get("name", "") for m in models)

            if model_found:
                logger.info(f"Ollama model '{self.model_name}' is available.")
                return True
            else:
                logger.critical(f"Ollama server is running, but the model '{self.model_name}' was not found.")
                logger.critical(f"Please run 'ollama pull {self.model_name}' in your terminal.")
                return False
        except requests.exceptions.RequestException as e:
            logger.critical(f"Failed to connect to Ollama server at {self.ollama_url}. Please ensure Ollama is running. Error: {e}")
            return False
        except Exception as e:
            logger.critical(f"An unexpected error occurred while checking Ollama: {e}", exc_info=True)
            return False
    
    def get_proactive_suggestion(self, screen_text: str) -> Optional[str]:
        """Analyzes screen text and returns a proactive suggestion using Ollama."""
        if not self.is_ready:
            logger.error("Ollama is not available, cannot generate suggestion.")
            return None

        system_prompt = (
            "You are a proactive assistant named K.A.I.R.O.S. "
            "The user is showing you text from their screen. Your task is to analyze the text and suggest a single, helpful next action in 15 words or less. "
            "If you see an error, suggest a potential fix. If you see a topic, suggest a web search. "
            "If there is nothing interesting or actionable, you MUST respond with only the word 'NONE'. "
            "Do not explain your reasoning. Only provide the suggestion or 'NONE'."
        )
        
        # <--- MODIFICATION: Simplified prompt to better align with Ollama API --->
        prompt = f"Here is the screen text:\n---\n{screen_text}\n---\nWhat is a concise, helpful suggestion based on this text?"
        
        logger.info("Generating proactive suggestion based on screen text...")
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "num_predict": 50,
                    "stop": ["<|end|>", "<|user|>", "user:", "system:"],
                },
            }
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            suggestion = result['response'].strip()
            
            if "none" in suggestion.lower() or not suggestion:
                logger.info("LLM found no actionable suggestion.")
                return None

            logger.info(f"LLM generated suggestion: '{suggestion}'")
            return suggestion
        except Exception as e:
            logger.error(f"Error during LLM suggestion generation: {e}", exc_info=True)
            return None

    def generate_script(self, query: str) -> Optional[str]:
        """Generates a Python script from a user query using Ollama."""
        if not self.is_ready:
            logger.error("Ollama is not available, cannot generate script.")
            return None

        system_prompt = (
            "You are an expert Python programmer integrated into an OS assistant named K.A.I.R.O.S. "
            "Your task is to write a single, safe, standalone Python script to accomplish the user's goal. "
            "Guidelines:\n"
            "- Only use standard Python libraries like 'os', 'shutil', 'glob', 'datetime'.\n"
            "- Do NOT use libraries like 'tkinter' or 'pyautogui' as the OS assistant handles UI.\n"
            "- Do NOT use any user input functions like `input()`.\n"
            "- The script must not contain any function or class definitions, just a straight script.\n"
            "- Assume the script will be run from the user's home directory.\n"
            "- Enclose the final Python script within ```python ... ``` markdown block."
        )

        prompt = query
        logger.info(f"Generating script for query: '{query}'")
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "num_predict": 500,
                    "stop": ["<|end|>", "<|user|>"],
                },
            }
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=180)
            response.raise_for_status()

            result = response.json()
            full_response_text = result['response']
            
            if "```python" in full_response_text:
                code_block = full_response_text.split("```python")[1]
                if "```" in code_block:
                    code_block = code_block.split("```")[0]
                script = code_block.strip()
                logger.info(f"LLM generated script:\n{script}")
                return script
            else:
                logger.warning("Ollama response did not contain a valid Python code block.")
                return None
        except Exception as e:
            logger.error(f"Error during Ollama script generation: {e}", exc_info=True)
            return None