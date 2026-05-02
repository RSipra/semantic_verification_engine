"""
Project: SVE (ref implementation: Harry Potter Trivia)
Central embeddings generating and processing logic (Phase 2+)
    
TODO (Full Dev): Move methods here for SOT for all downstream embedding uses.
- embeddings methods (generation in qa_validation and processing from NLP lab) 
- upfront tensor conversions at runtime NLP lab
"""
from functools import lru_cache
from sentence_transformers import SentenceTransformer, CrossEncoder
from core.settings import sbert_settings, nli_settings

# singleton cache internal pointers to loaded model; starts empty.
_sbert_model_instance = None
_nli_model_instance = None

# ↓lru decorator intercepts the call. returns the saved object instantly in memory, 
# preventing function body running a second time (so dont need is None check loop)
@lru_cache(maxsize=1)  #ensure model is loaded into cache only once
def get_sbert_model() -> SentenceTransformer:
    """
    SBERT LOADER: Ensures a single SBERT instance is shared across the 
    Pipeline and Lab.
    ---------------------------------------
    DESIGN PURPOSE (SVE Core Architecture):
    ---------------------------------------
    1. TRACER PHASE (Offline Standardization): 
       'Convenience Singleton' to avoid code repetition across 
       Notebooks and Scripts. Ensures the 'Lab' and 'Pipeline' always 
       use the same SOT (Source of Truth) model without manual redeclaration.
    
    2. RUNTIME EFFICIENCY:
       - Fast Access: Once loaded, subsequent calls return the cached model
       - Lazy Loading: The model only loads into RAM on the first call,
         preserving resources for other system processes.
       - RAM Efficiency: SBERT models are heavy (~420MB). Loading explicitly on 
         CPU (`device='cpu'`) prevents OOM kills in 1GB Docker containers 
         (GCP Free Tier) by ensuring only ONE instance exists in memory 
         and avoiding unnecessary GPU memory allocation.
    
    3. FUTURE OFFLINE SYSTEMS COMPLIANCE: (Content Factory, Context Refinery)
       By centralizing the loader, can force 'local_files_only' logic 
       during full system development to ensure the system never hangs trying to download 
       weights from Hugging Face in a restricted production environment.
    """
    global _sbert_model_instance  # system wide global variable to hold the model instance     
    _sbert_model_instance = SentenceTransformer(sbert_settings.model_name,
                                              device='cpu',   # force CPU for compatibility with GCP Free Tier
                                              local_files_only=True)
        
    return _sbert_model_instance
 
@lru_cache(maxsize=1) 
def get_nli_model() -> CrossEncoder:
    """
    Singleton cache for the NLI Cross-Encoder.
    Guarantees the model is only loaded into memory once per session.
    """
    global _nli_model_instance  # system wide global variable to hold the model instance
      # Add device='cuda' or device='mps' here if you are using GPU/Mac Silicon
    _nli_model_instance = CrossEncoder(nli_settings.model_name,    
                                       device='cpu',   # force CPU for compatibility with GCP Free Tier
                                       local_files_only=True) 
    return _nli_model_instance