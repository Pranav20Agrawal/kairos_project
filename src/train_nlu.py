# train_nlu.py

import json
from src.database_manager import DatabaseManager
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

BASE_MODEL = 'all-MiniLM-L6-v2'
FINE_TUNED_MODEL_PATH = 'models/fine_tuned_nlu'
MIN_TRAINING_SAMPLES = 5 # Minimum number of corrections needed to start training

def main():
    """
    Main function to run the fine-tuning process.
    """
    print("--- K.A.I.R.O.S. NLU Fine-Tuning ---")
    
    # 1. Load data
    print("Step 1: Loading training data from database...")
    db = DatabaseManager()
    training_data = db.get_training_data()

    if len(training_data) < MIN_TRAINING_SAMPLES:
        print(f"Insufficient training data. Need at least {MIN_TRAINING_SAMPLES} corrected samples, but found {len(training_data)}. Please use the app and correct more mistakes first.")
        return

    # 2. Load canonical phrases from config to pair with training data
    print("Step 2: Loading canonical phrases from config.json...")
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        intents_config = config.get("intents", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: Could not load or parse config.json. {e}")
        return

    # 3. Create training examples
    print("Step 3: Creating training examples...")
    train_examples = []
    for text, corrected_intent in training_data:
        # We clean the intent name (e.g., '[GET_WEATHER]' -> 'GET_WEATHER')
        clean_intent = corrected_intent.strip("[]")
        
        # Find the canonical phrase for this intent
        canonical_phrase = intents_config.get(clean_intent, {}).get("canonical")
        
        if canonical_phrase:
            # We create a positive pair: the user's text and the ideal phrase
            # The model will learn to make their embeddings similar.
            train_examples.append(InputExample(texts=[text, canonical_phrase], label=1.0))
        else:
            print(f"Warning: No canonical phrase found for intent '{clean_intent}'. Skipping this training example.")

    if not train_examples:
        print("No valid training examples could be created. Aborting.")
        return
        
    print(f"Successfully created {len(train_examples)} training examples.")

    # 4. Load the base model
    print(f"Step 4: Loading base model '{BASE_MODEL}'...")
    model = SentenceTransformer(BASE_MODEL)

    # 5. Fine-tune the model
    print("Step 5: Starting the fine-tuning process...")
    # CosineSimilarityLoss is good for making sentence pairs have similar embeddings
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
    train_loss = losses.CosineSimilarityLoss(model)

    # Train for one epoch
    model.fit(train_objectives=[(train_dataloader, train_loss)], epochs=1, warmup_steps=10)
    print("Fine-tuning complete.")
    
    # 6. Save the improved model
    print(f"Step 6: Saving fine-tuned model to '{FINE_TUNED_MODEL_PATH}'...")
    model.save(FINE_TUNED_MODEL_PATH)
    
    print("\n--- Success! ---")
    print("The NLU model has been improved with your feedback. Please restart K.A.I.R.O.S. to use the updated model.")


if __name__ == "__main__":
    main()