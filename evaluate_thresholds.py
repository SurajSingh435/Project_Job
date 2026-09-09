import json
import numpy as np
import httpx
import asyncio

# Configure with your test JSON file
TEST_DATA_PATH = "labeled_complaints.json"
# Add your token here when running the script directly
OPENAI_API_KEY = "sk-..." 

async def fetch_embedding(text: str, client: httpx.AsyncClient) -> list[float]:
    response = await client.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "text-embedding-3-small",
            "input": text
        }
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    a = np.array(v1)
    b = np.array(v2)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

async def main():
    try:
        with open(TEST_DATA_PATH, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {TEST_DATA_PATH}. Creating a dummy file for demonstration...")
        # Create a sample JSON file structure
        data = [
            {
                "text1": "Huge pothole on 5th avenue",
                "text2": "Massive crater on 5th ave destroying tires",
                "is_duplicate": True
            },
            {
                "text1": "Street light out on elm street",
                "text2": "Trash not collected on elm street",
                "is_duplicate": False
            }
        ]
        with open(TEST_DATA_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print("Please fill labeled_complaints.json with real data and set your OPENAI_API_KEY.")
        return

    # 1. Fetch embeddings if not present
    print("Fetching missing embeddings...")
    async with httpx.AsyncClient() as client:
        for pair in data:
            if "emb1" not in pair:
                pair["emb1"] = await fetch_embedding(pair["text1"], client)
            if "emb2" not in pair:
                pair["emb2"] = await fetch_embedding(pair["text2"], client)

    # Save embeddings back so we don't have to fetch them again
    with open(TEST_DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

    # 2. Evaluate thresholds
    thresholds = np.arange(0.70, 0.95, 0.05)
    print("\n--- Evaluation Results ---")
    print(f"{'Threshold':<12} | {'Precision':<10} | {'Recall':<10} | {'F1 Score':<10}")
    print("-" * 55)

    for t in thresholds:
        tp = fp = fn = tn = 0
        for pair in data:
            sim = cosine_similarity(pair["emb1"], pair["emb2"])
            pred_duplicate = sim >= t
            actual_duplicate = pair["is_duplicate"]
            
            if pred_duplicate and actual_duplicate:
                tp += 1
            elif pred_duplicate and not actual_duplicate:
                fp += 1
            elif not pred_duplicate and actual_duplicate:
                fn += 1
            else:
                tn += 1
                
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        print(f"{t:<12.2f} | {precision:<10.3f} | {recall:<10.3f} | {f1:<10.3f}")

if __name__ == "__main__":
    asyncio.run(main())
