"""
Utility script to pre-download ONLY SBERT weights for the demo.
Ensures 'local_files_only=True' works for the Semantic Intelligence layer.
"""
import os
from sentence_transformers import SentenceTransformer
from core.settings import sbert_settings

def bake_demo_models():
    """
    Downloads model weights to the location specified by HF_HOME.
    This is called during the 'docker build' phase to 'shift intelligence left'.
    """
    # Use the same HF_HOME logic as embeddings.py
    # Defaulting to /app/models to match your Docker structure
    cache_path = os.getenv('HF_HOME', '/app/models')
    
    print(f"--- Starting Demo Model Bake into {cache_path} ---")
    
    # Download ONLY SBERT (approx 80MB-100MB for MiniLM)
    # This prevents the container from needing internet at runtime
    print(f"Downloading SBERT: {sbert_settings.model_name}...")
    SentenceTransformer(sbert_settings.model_name, cache_folder=cache_path)
    
    print("--- Demo Model Bake Complete ---")

if __name__ == "__main__":
    bake_demo_models()