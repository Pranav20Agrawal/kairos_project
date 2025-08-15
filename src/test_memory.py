# test_memory.py

import pprint
from src.memory_manager import MemoryManager
from src.nlu_engine import NluEngine
from src.settings_manager import SettingsManager

# Pretty printer for clean output
pp = pprint.PrettyPrinter(indent=2)

def main():
    print("--- KAIROS Memory Test ---")

    # We need the NLU engine to get the sentence transformer model
    print("Loading AI models...")
    settings = SettingsManager()
    nlu_engine = NluEngine(settings)
    
    if not nlu_engine.model:
        print("Error: Could not load the sentence transformer model. Aborting.")
        return

    # Initialize the memory manager
    print("Connecting to memory database...")
    memory = MemoryManager(nlu_engine.model)

    if not memory.collection:
        print("Error: Could not connect to the memory collection. Aborting.")
        return

    # --- ASK A QUESTION ---
    query = "What have I been reading about Python programming?"
    print(f"\nSearching for memories related to: '{query}'\n")

    results = memory.query_memory(query, n_results=3)

    if results:
        print("Found relevant memories:")
        pp.pprint(results)
    elif results == []:
        print("No relevant memories found. Try browsing some websites and running the main app first.")
    else:
        print("An error occurred during the query.")

if __name__ == "__main__":
    main()