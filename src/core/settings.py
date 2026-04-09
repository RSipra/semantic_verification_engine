"""
Project: SVE (ref implementation: Harry Potter Trivia)
Project Settings (Phase 2+)
"""
import torch
from pydantic_settings import BaseSettings, SettingsConfigDict
import numpy as np

# --- Subsystem 1: Global/Core Invariants ---
class SBERTSettings(BaseSettings):
    """
    Core Invariants for the SBERT Semantic Engine.
    These define the 'Physics' of our vector space.
    """
    
    # 1. The Model SOT (Source of Truth)
    model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    
    # 2. The Global Tensor Standard
    # This ensures the Generator, Ingestor, and Checker all use the same math
    tensor_dtype: torch.dtype = torch.float32
    numpy_dtype: type = np.float32

    # --- Threshold Placeholders ---
    # To be defined in the Verification Routing logic later 
    # based on (MCQ vs FR vs EX) performance testing.

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_prefix="SBERT_",
        case_sensitive=False # Good for cross-platform (Windows/Mac) safety
    )

sbert_settings = SBERTSettings()    
