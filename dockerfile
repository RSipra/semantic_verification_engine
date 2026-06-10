# 1. BASE IMAGE: Use a slim Python 3.11 image to minimize RAM usage
FROM python:3.11-slim

# 2. LOGGING: Prevent Python from buffering stdout/stderr
#  ensures real-time feedback in Google Cloud Operations Suite logs
ENV PYTHONUNBUFFERED=1
# Master Pointer for SVE intelligence (local model storage)
ENV HF_HOME=/app/models
# Point Python to 'src' to find core, engine, and game_app
ENV PYTHONPATH="/app/src"

# manage torch download during docker build
ENV PIP_NO_CACHE_DIR=1
ENV TMPDIR=/var/tmp


# 3. SYSTEM DEPS: Install curl/tar for GoTTY and clean up to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tar \
    && rm -rf /var/lib/apt/lists/*

# 4. WORKSPACE: Establish the /app directory (Docker creates this automatically)
WORKDIR /app

# 5. PYTHON DEPS: Install verified libraries from requirements.txt
# This ignores requirements-dev.txt to save space
# --------------------------------------------------------------------------------
# Dependency installation strategy (iteratively refined during constrained VM builds)
#
# Initial builds were executed on a ~10GB VM where pip installs of ML packages
# (torch, transformers, scipy, sklearn) caused transient disk exhaustion during
# wheel unpacking and Docker layer writes.
#
# To ensure build stability, dependencies were split into staged installs:
# 1. torch (CPU-only, isolated early to control large binary resolution)
# 2. application dependencies
#
# The VM has since been upgraded to ~30GB disk, a single-pass requirements install 
# is now technically viable. However, staged installation is retained as a 
# robustness pattern for:
# - reproducible builds across constrained environments
# - easier isolation of heavy ML dependencies (torch / transformers)
# - reduced risk of transient build spikes in CI or future deployments-----------------
#    
COPY requirements.txt .
# 5.1. torch (locked CPU)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# 5.2. remaining lightweight deps, ensure torch not overwritten by sentence transformers
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# 6. MODEL BAKE: Copy core logic and download weights during BUILD phase
# Done BEFORE copying the rest of the app to leverage Docker layer caching
# remove cache to not retain the heavy .tar files
COPY src/core/ /app/src/core/
RUN python -m core.download_models && rm -rf /root/.cache/huggingface

# 7. NETWORK ISOLATION: Disable Hugging Face API requests (safety net)
# Ensures the container only uses the baked-in models and prevents runtime timeouts.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# 8. GOTTY WRAPPER: Install the web-terminal binary (v1.6.0)
# Note: This is the linux_amd64 version for your target GCP VM
ENV GOTTY_VERSION=v1.6.0
RUN curl -L https://github.com/sorenisanerd/gotty/releases/download/${GOTTY_VERSION}/gotty_${GOTTY_VERSION}_linux_amd64.tar.gz \
    | tar -xzC /usr/local/bin/

# 9. Runtime engine, application layer, and validated dataset
COPY src/engine/ /app/src/engine/
COPY src/game_app/ /app/src/game_app/
# Create the data directory in the container first
RUN mkdir -p /app/data
COPY data/05_final/tracer_production_green_v1.parquet /app/data/tracer_production_green_v1.parquet
# create dir to store game session_reports
RUN mkdir -p /app/runtime

# 10. NETWORKING: Expose the port used by GoTTY
EXPOSE 8080

# 11. ENTRYPOINT: Launch GoTTY to serve the trivia game over a web terminal
CMD ["gotty", "-w", "--address", "0.0.0.0", "--port", "8080", "python", "src/game_app/main.py"]