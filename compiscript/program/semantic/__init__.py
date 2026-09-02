"""Semantic analysis package for Compiscript.

Layout:
    ``types``        type model and compatibility rules
    ``symbols``      symbols stored in the table
    ``scopes``       scope tree and walking environment
    ``symbol_table`` facade exposed to the CLI and the tests
    ``diagnostics``  diagnostic records and codes
    ``annotations``  parse-tree helpers for positions and type annotations
    ``collector``    first pass: classes and function signatures
    ``checker``      second pass: scopes, resolution and typing
    ``analyzer``     runs both passes
"""

from .analyzer import SemanticResult, analyze
from .diagnostics import Diagnostic, DiagnosticBag
from .symbol_table import SymbolTable

__all__ = [
    "Diagnostic",
    "DiagnosticBag",
    "SemanticResult",
    "SymbolTable",
    "analyze",
]
