"""Print a Pydantic model's fields, types and descriptions.

Usage: python -m scripts.dev.show_fields google.genai.types GenerateContentConfig
"""
import importlib
import sys

module_name, class_name = sys.argv[1], sys.argv[2]
cls = getattr(importlib.import_module(module_name), class_name)
for name, f in cls.model_fields.items():
    print(f"{name}: {f.annotation}\n    {f.description}\n")