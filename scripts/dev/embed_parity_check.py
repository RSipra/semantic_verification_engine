"""
Embedding parity check: verify SBERT embeddings stay the same across a dependency bump.

Purpose
-------
SVE computes embeddings in two places: offline (the dev environment, building
assets) and online (the runtime container, scoring answers). Both must produce
the same vectors for the same text, or SBERT similarity scores, and the
thresholds tuned on them, drift silently.

A bump to torch, transformers or sentence-transformers can change the numbers
slightly. This script checks whether it has, by encoding a fixed set of
sentences in two environments and comparing the results.

Model loading (singleton)
-------------------------
The model is loaded through the singleton in src/core/embeddings.py, not built
directly in this script. Two things follow from that:

- Production parity: the singleton reads the model name from src/core/settings
  and owns how the model is loaded and how text is encoded (e.g. normalisation).
  Going through it means this check exercises the same path production uses,
  with no duplicated loading logic to drift out of sync.

- One model per process: a singleton loads once and is reused for the life of
  the Python process. It cannot reload under a different package version
  mid-run, so the old-pin and new-pin encodings must run as separate processes
  (separate venvs or interpreters), as in the usage steps below.

If importing the singleton ever gains side effects (loading datasets, running
validation, calling the LLM), switch this script to reading the model name
from settings and constructing the model directly, mirroring the encode
options in embeddings.py.

When to run
-----------
- After bumping torch, transformers or sentence-transformers in either
  requirements-dev.txt or the Dockerfile.
- Before rebuilding the runtime image with a new torch pin.

This is a manual check, not a pytest test: it needs two environments
(e.g. the dev venv and the running container).

sage: old pin vs new pin (main workflow)
-----------------------------------------
Your dev venv holds the NEW pin. A throwaway venv holds the OLD pin, so only
the bumped package differs between the two runs. Run all commands from the
repo root so `src` is importable.

1. Encode with the new pin (your normal dev venv):
       python scripts/dev/embed_parity_check.py emb_new.npy

2. Build a throwaway venv with the old pin and encode:
       python3.12 -m venv /tmp/parity-old
       /tmp/parity-old/bin/pip install -r requirements-dev.txt
       /tmp/parity-old/bin/pip install -e . --no-deps
       /tmp/parity-old/bin/pip install <package>==<old version>    # e.g. torch==2.9.1
       /tmp/parity-old/bin/python scripts/dev/embed_parity_check.py emb_old.npy

3. Compare:
       python -c "import numpy as np; a, b = np.load('emb_old.npy'), np.load('emb_new.npy'); \
       print('max abs diff:', np.abs(a - b).max()); print('min cosine:', (a * b).sum(axis=1).min())"

4. Clean up:
       rm -rf /tmp/parity-old

Optional: runtime container vs dev
----------------------------------
Before a runtime rebuild, the same script can compare the live container with
the dev venv. Note that the container may run different code and Python
versions, so not every difference comes from the bump.
       docker cp scripts/dev/embed_parity_check.py <container>:/tmp/
       docker exec -w /app <container> python /tmp/embed_parity_check.py /tmp/emb_old.npy
       docker cp <container>:/tmp/emb_old.npy .

Reading the result
------------------
- max abs diff around 1e-6 or smaller, min cosine about 1.0: equivalent. The
  bump is safe for embeddings.
- Larger differences: not automatically a failure. Check whether any
  similarity score would cross an SBERT threshold in the evaluation cascade.
  Note that other differences between the environments (Python version,
  transformers version) can also contribute.

Outputs
-------
emb_*.npy files are throwaway artifacts and are gitignored.

Example record
--------------
torch 2.10.0+cpu (runtime container) vs 2.13.0 (dev), Nov 2026:  
max abs diff 1.35e-07, min cosine 0.99999994 (equivalent; float32 rounding)
"""

import sys
import numpy as np
import torch

from core.embeddings import get_sbert_model

SENTENCES = [
    "Harry Potter", "the boy who lived", "Voldemort",
    "Hermione Granger", "a wand made of holly and phoenix feather",
]
model = get_sbert_model()
emb = model.encode(SENTENCES, normalize_embeddings=True)
np.save(sys.argv[1], emb)
print(torch.__version__, emb.shape)
