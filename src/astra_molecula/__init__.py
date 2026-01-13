"""
AstraMolecula - Molecular Design and Docking API Service

A FastAPI-based service for molecular docking, peptide optimization,
and molecular generation tasks.
"""

__version__ = "2.1.0"
__author__ = "AstraMolecula Team"

from pathlib import Path

# 项目根目录 (src/astra_molecula 的上两级)
ROOT = Path(__file__).resolve().parent.parent.parent

__all__ = ["ROOT", "__version__", "__author__"]
