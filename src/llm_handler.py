# src/llm_handler.py

import ollama
import logging
import json  # <-- ADDED THIS IMPORT
from typing import Tuple, List, Dict, Any, TYPE_CHECKING  # <-- ADDED LIST, DICT, ANY

# --- ADD THIS IMPORT ---
if TYPE_CHECKING:
    from src.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

class LlmHandler:
    def __init__(self, model_name: str = "phi3", settings_manager: "SettingsManager" = None) -> None:  # <-- ADD settings_manager
        self.model = model_name
        self.settings_manager = settings_manager  # <-- ADD THIS LINE
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

    def _get_personality_prompt_suffix(self) -> str:
        """Creates a prompt suffix based on the current personality settings."""
        if not self.settings_manager:
            return ""
        
        p = self.settings_manager.settings.personality
        
        # Translate float values into instructions for the LLM
        verbosity_desc = "be extremely concise" if p.verbosity < 0.33 else "be moderately detailed" if p.verbosity < 0.66 else "be very detailed"
        formality_desc = "use a casual, informal tone" if p.formality < 0.5 else "use a professional, formal tone"
        
        return f"\n\nIMPORTANT INSTRUCTION: Your response style must {verbosity_desc} and {formality_desc}."

    def analyze_workflow(self, session_log: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        """
        Takes a log of user actions and asks the LLM to infer the goal
        and suggest a name for an automation macro.
        """
        logger.info("Asking LLM to analyze user workflow...")
        
        # Format the session log for the prompt
        formatted_actions = "\n".join(
            f"- ({item['process_name']}, \"{item['window_title']}\")" for item in session_log
        )
        prompt = (
            "You are an expert workflow analyst. Based on the following sequence of user actions "
            "(process_name, window_title), infer the user's high-level goal and suggest a concise, "
            "human-readable name for a macro to automate this workflow.\n\n"
            "Actions:\n"
            f"{formatted_actions}\n\n"
            "Your response MUST be in a single, raw JSON object format with two keys: 'goal' and 'macro_name'.\n"
            "Example: {\"goal\": \"Starting a development session for the KAIROS project.\", \"macro_name\": \"Start KAIROS Dev Session\"}"
        )
        prompt += self._get_personality_prompt_suffix()  # <-- ADD THIS LINE
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                format="json", # Use Ollama's built-in JSON mode
            )
            
            response_text = response['response']
            suggestion = json.loads(response_text)
            return suggestion
        except Exception as e:
            logger.error(f"Failed to analyze workflow with LLM: {e}")
            return None

    def generate_ui_layout(self, task_context: str, available_widgets: List[str], goal_info: Dict | None = None) -> Dict[str, Any] | None:  # <-- ADD goal_info
        """
        Asks the LLM to generate a dynamic UI layout based on the user's current task and goals.
        """
        logger.info(f"Generating UI layout for context: {task_context}")
        
        # Clean up the context name for the prompt
        friendly_context = task_context.replace("TASK_", "").replace("_", " ").title()
        
        # --- Create a more detailed prompt if a goal is active ---
        goal_prompt_part = ""
        if goal_info:
            goal_prompt_part = (
                f"\n**IMPORTANT**: The user is actively working on the following high-priority goal: '{goal_info['name']}'. "
                f"Your layout MUST prioritize widgets that help with this goal. The 'GOAL_MEMORY' widget is highly relevant."
            )
        
        prompt = (
            "You are an expert Human-Computer Interaction (HCI) designer. Your task is to design a "
            "dynamic 2x2 grid layout for a desktop assistant's dashboard to perfectly match the user's "
            f"current task: '{friendly_context}'.{goal_prompt_part}\n\n"
            "Here are the available widgets you can use:\n"
            f"- {', '.join(available_widgets)}\n\n"
            "RULES:\n"
            "1. The grid is 2 rows by 2 columns (row/col indices are 0-1).\n"
            "2. Choose the 2 to 4 most relevant widgets for the task.\n"
            "3. You MUST respond with only a raw JSON object. Do not include any other text or markdown.\n"
            "4. The JSON keys must be the widget names from the available list.\n"
            "5. Each widget object must contain: enabled (always true), row, col, row_span, col_span.\n\n"
            "Example for a 'Video Call' task:\n"
            "{\n"
            '  "VIDEO_FEED": {"enabled": true, "row": 0, "col": 0, "row_span": 2, "col_span": 1},\n'
            '  "NOTIFICATIONS": {"enabled": true, "row": 0, "col": 1, "row_span": 1, "col_span": 1},\n'
            '  "SYSTEM_STATS": {"enabled": true, "row": 1, "col": 1, "row_span": 1, "col_span": 1}\n'
            "}"
        )
        prompt += self._get_personality_prompt_suffix()  # <-- ADD THIS LINE
        
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                format="json",
            )
            layout_str = response['response']
            layout_config = json.loads(layout_str)
            logger.info(f"LLM generated new layout config.")
            return layout_config
        except Exception as e:
            logger.error(f"Failed to generate UI layout with LLM: {e}")
            return None

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