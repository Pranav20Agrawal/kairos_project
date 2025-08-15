import time
from sentence_transformers import SentenceTransformer, util
import torch

# Use the same model as your NLU engine
MODEL_NAME = 'all-MiniLM-L6-v2'
NUM_INTENTS = 50 # A realistic number of commands
NUM_RUNS = 100 # Run the test multiple times for a stable average

def test_nlu_performance():
    print(f"--- Testing NLU Performance with '{MODEL_NAME}' ---")

    # 1. Load the model (time this once, as it's a one-time cost at startup)
    start_time = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME)
    end_time = time.perf_counter()
    print(f"Model load time: {end_time - start_time:.2f} seconds")

    # 2. Create a dummy set of canonical phrases and embeddings
    # This simulates the state of your NLU engine after loading intents
    print(f"\nGenerating {NUM_INTENTS} dummy intent embeddings...")
    canonical_phrases = [f"This is a sample command number {i}" for i in range(NUM_INTENTS)]
    canonical_embeddings = model.encode(canonical_phrases, convert_to_tensor=True)
    print("Embeddings created.")

    # 3. Time the core logic: encoding a query and finding the best match
    test_query = "search the web for information about python"
    timings = []

    print(f"\nRunning semantic search test ({NUM_RUNS} runs)...")
    for _ in range(NUM_RUNS):
        start_time = time.perf_counter()

        # This is the exact logic your NLU engine uses
        query_embedding = model.encode(test_query, convert_to_tensor=True)
        _ = util.cos_sim(query_embedding, canonical_embeddings) # The underscore discards the result

        end_time = time.perf_counter()
        timings.append((end_time - start_time) * 1000) # Convert to milliseconds

    average_time = sum(timings) / len(timings)
    
    print("\n--- Results ---")
    print(f"Average intent recognition time: {average_time:.2f} ms")

if __name__ == "__main__":
    test_nlu_performance()