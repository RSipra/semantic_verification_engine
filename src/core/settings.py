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
    
    DOCKER BUILD COMMAND (Surgical): avoid bloat - dont download rust model as well
    RUN HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli download \
    sentence-transformers/all-MiniLM-L6-v2 \
    --exclude "*.ot" --exclude "*.h5"
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

class NLISettings(BaseSettings):
    """
    NLI model settings
    
    RATIONALE:
    1. Model Choice: 'deberta-v3-small' offers the best logic/latency ratio for CPU.
    2. Format: Standardizing on Safetensors over ONNX for Phase 2 to avoid 
       'onnxruntime' complexity and maintain library compatibility.
    3. Hardware: device='cpu' is forced to prevent OOM crashes on GCP Free Tier.
    4. Disk/RAM: Cache size is managed by excluding legacy .bin and optimized ONNX 
       formats, ensuring the runtime memory load stays at ~600MB.
       
    DOCKER BUILD COMMAND (Surgical): bloat ~1.5GB (onnx, bin)
    RUN HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli download \\
        cross-encoder/nli-deberta-v3-small \\
        --exclude "onnx/*" \\
        --exclude "*.bin"
    """
    model_name: str = 'cross-encoder/nli-deberta-v3-small'

    # standard mapping -> MUST update if model changed from deberta-v3-small
    label_mapping: dict[int, str] = {
        0: "contradiction",
        1: "entailment",
        2: "neutral"
    }
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_prefix="NLI_",
        case_sensitive=False 
    )
nli_settings = NLISettings()    
