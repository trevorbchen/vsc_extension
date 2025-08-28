"""
Formal Verifier Backend Package

This package provides the backend logic for the VS Code Formal Verifier extension.
It contains the pipeline for:
1. Reading source files and resolving dependencies.
2. Annotating the code via API #1.
3. Verifying the annotated code via API #2.
4. Formatting results for the extension frontend.
"""

__version__ = "0.1.0"

# Expose main pipeline function for convenience
from .pipeline import run_pipeline
