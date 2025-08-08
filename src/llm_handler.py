# src/llm_handler.py

import ollama
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class LlmHandler:
    def __init__(self, model_name: str = "phi3") -> None:
        self.model = model_name
        self.tools_prompt = self._load_primitives_prompt()
        self._check_connection()

    def _check_connection(self) -> None:
        try:
            logger.info(f"Checking for Ollama server...")
            client = ollama.Client()
            ollama_models = client.list()
            logger.info("Ollama server is running.")
            logger.info(f"Verifying that model '{self.model}' is available...")
            available_models = [model.get('name') for model in ollama_models.get('models', [])]
            if not any(self.model in m for m in available_models if m is not None):
                logger.warning(f"Model '{self.model}' not found. Pulling from Ollama...")
                ollama.pull(self.model)
            logger.info(f"Ollama model '{self.model}' is available.")
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}. Dynamic task execution will be disabled.")
            raise

    def _load_primitives_prompt(self) -> str:
        """Reads the primitives.py file to create a dynamic prompt for the LLM."""
        try:
            with open("src/primitives.py", "r") as f:
                primitives_code = f.read()
            
            prompt = (
                "You are an expert Python programmer integrated into a desktop assistant named K.A.I.R.O.S.\n"
                "Your task is to understand a user's command and generate a SHORT, SIMPLE Python script to accomplish it.\n"
                "You MUST use the provided functions from the `primitives` module to interact with the system.\n\n"
                "### AVAILABLE PRIMITIVE TOOLS (in primitives.py) ###\n"
                f"{primitives_code}\n\n"
                "### YOUR RESPONSE FORMAT ###\n"
                "Your response MUST be in two parts, separated by '### SCRIPT ###'.\n"
                "Part 1: A brief, one-sentence plan explaining what the script will do.\n"
                "Part 2: The raw Python code block itself. The code MUST call functions using `primitives.function_name()`. DO NOT wrap the code in markdown backticks."
            )
            return prompt
        except FileNotFoundError:
            logger.error("src/primitives.py not found! LLM will not have tool context.")
            return "You are an expert Python programmer. Please generate a simple python script to solve the user's request."

    def generate_script(self, query: str) -> Tuple[str, str | None]:
        """Asks the LLM to generate a plan and a Python script using the available tools."""
        try:
            logger.info(f"Generating script for query: '{query}'")
            response = ollama.generate(
                model=self.model,
                system=self.tools_prompt,
                prompt=query
            )
            full_response = response['response']
            
            if "### SCRIPT ###" in full_response:
                parts = full_response.split("### SCRIPT ###", 1)
                plan = parts[0].strip().replace("\n", " ")
                script = parts[1].strip()
                logger.info(f"LLM generated plan: {plan}")
                return plan, script
            else:
                logger.warning("LLM did not follow the expected format.")
                return "I will attempt to run the raw output from the model.", full_response
        except Exception as e:
            logger.error(f"Failed to generate script from LLM: {e}")
            return "An error occurred.", f"Error: {e}"