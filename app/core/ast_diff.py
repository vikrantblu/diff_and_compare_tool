"""
Tree-sitter and AST Semantic Code Differ
Provides structural understanding of source code:
- Detects reordered functions, methods, and classes.
- Detects reformatted docstrings, comments, and whitespace without false-positive diffs.
- Extracts symbol trees and semantic blocks across Python, JavaScript, and other languages.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Set

# Attempt tree-sitter bindings
try:
    import tree_sitter
    import tree_sitter_python
    PY_LANGUAGE = tree_sitter.Language(tree_sitter_python.language())
    PY_PARSER = tree_sitter.Parser(PY_LANGUAGE)
except Exception:
    PY_LANGUAGE = None
    PY_PARSER = None

try:
    import tree_sitter_javascript
    JS_LANGUAGE = tree_sitter.Language(tree_sitter_javascript.language())
    JS_PARSER = tree_sitter.Parser(JS_LANGUAGE)
except Exception:
    JS_LANGUAGE = None
    JS_PARSER = None


@dataclass
class SemanticSymbol:
    """Represents a structural code symbol (function, class, method, or statement)."""
    kind: str           # 'function', 'class', 'method', 'docstring', 'comment', 'statement'
    name: str           # Symbol name e.g. 'calculate_tax'
    start_line: int     # 0-indexed start line
    end_line: int       # 0-indexed end line (exclusive)
    raw_text: str
    normalized_body: str
    docstring: Optional[str] = None
    signature: str = ""


@dataclass
class SemanticDiffMatch:
    """Represents a matched semantic symbol across left and right."""
    left_symbol: Optional[SemanticSymbol]
    right_symbol: Optional[SemanticSymbol]
    status: str  # 'identical', 'reordered', 'modified', 'docstring_only', 'left_only', 'right_only'
    explanation: str


class ASTSemanticDiffer:
    """Extracts structural AST symbols and compares them semantically."""

    @classmethod
    def extract_symbols(cls, code: str, language: str = "python") -> List[SemanticSymbol]:
        """Extracts top-level and method symbols using Tree-sitter or fallback AST."""
        lang = language.lower()
        if lang in ("python", "py"):
            if PY_PARSER:
                symbols = cls._extract_python_treesitter(code)
                if symbols:
                    return symbols
            return cls._extract_python_ast(code)
        elif lang in ("javascript", "js", "typescript", "ts") and JS_PARSER:
            return cls._extract_js_treesitter(code)

        # Generic line-based symbol heuristic fallback
        return cls._extract_generic_symbols(code)

    @classmethod
    def _extract_python_treesitter(cls, code: str) -> List[SemanticSymbol]:
        try:
            byte_code = code.encode("utf-8")
            tree = PY_PARSER.parse(byte_code)
            symbols: List[SemanticSymbol] = []

            for node in tree.root_node.children:
                if node.type in ("function_definition", "class_definition"):
                    kind = "class" if node.type == "class_definition" else "function"
                    name_node = node.child_by_field_name("name")
                    name = name_node.text.decode("utf-8") if name_node else "<anonymous>"

                    # Parameters / signature
                    params_node = node.child_by_field_name("parameters")
                    sig = params_node.text.decode("utf-8") if params_node else ""

                    # Body
                    body_node = node.child_by_field_name("body")
                    body_text = body_node.text.decode("utf-8") if body_node else ""

                    # Normalize body: strip comments, normalize whitespace
                    norm_body = cls._normalize_code_text(body_text)

                    start_line = node.start_point.row
                    end_line = node.end_point.row + 1
                    raw_text = byte_code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

                    symbols.append(SemanticSymbol(
                        kind=kind,
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        raw_text=raw_text,
                        normalized_body=norm_body,
                        signature=sig
                    ))
            return symbols
        except Exception:
            return []

    @classmethod
    def _extract_python_ast(cls, code: str) -> List[SemanticSymbol]:
        symbols: List[SemanticSymbol] = []
        try:
            lines = code.splitlines()
            tree = ast.parse(code)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "class" if isinstance(node, ast.ClassDef) else "function"
                    name = node.name
                    start_line = node.lineno - 1
                    end_line = getattr(node, "end_lineno", node.lineno)
                    raw_lines = lines[start_line:end_line]
                    raw_text = "\n".join(raw_lines)

                    # Extract docstring if present
                    docstring = ast.get_docstring(node)

                    # Normalized body without docstring
                    try:
                        norm_body = ast.unparse(node)
                    except Exception:
                        norm_body = cls._normalize_code_text(raw_text)

                    symbols.append(SemanticSymbol(
                        kind=kind,
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        raw_text=raw_text,
                        normalized_body=norm_body,
                        docstring=docstring
                    ))
        except Exception:
            pass
        return symbols

    @classmethod
    def _extract_js_treesitter(cls, code: str) -> List[SemanticSymbol]:
        try:
            byte_code = code.encode("utf-8")
            tree = JS_PARSER.parse(byte_code)
            symbols: List[SemanticSymbol] = []

            for node in tree.root_node.children:
                if node.type in ("function_declaration", "class_declaration", "lexical_declaration"):
                    name = "<anonymous>"
                    kind = "function"
                    if node.type == "class_declaration":
                        kind = "class"
                        name_node = node.child_by_field_name("name")
                        if name_node:
                            name = name_node.text.decode("utf-8")
                    elif node.type == "function_declaration":
                        name_node = node.child_by_field_name("name")
                        if name_node:
                            name = name_node.text.decode("utf-8")
                    elif node.type == "lexical_declaration":
                        # const fn = () => {}
                        text = node.text.decode("utf-8")
                        m = re.match(r"(?:const|let|var)\s+([a-zA-Z0-9_$]+)", text)
                        if m:
                            name = m.group(1)

                    start_line = node.start_point.row
                    end_line = node.end_point.row + 1
                    raw_text = byte_code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

                    symbols.append(SemanticSymbol(
                        kind=kind,
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        raw_text=raw_text,
                        normalized_body=cls._normalize_code_text(raw_text)
                    ))
            return symbols
        except Exception:
            return []

    @classmethod
    def _extract_generic_symbols(cls, code: str) -> List[SemanticSymbol]:
        symbols: List[SemanticSymbol] = []
        lines = code.splitlines()
        func_pattern = re.compile(r"^\s*(?:def|function|class|public\s+\w+|private\s+\w+)\s+([a-zA-Z_]\w*)")
        current_name = None
        current_start = 0

        for idx, line in enumerate(lines):
            m = func_pattern.match(line)
            if m:
                if current_name is not None:
                    raw = "\n".join(lines[current_start:idx])
                    symbols.append(SemanticSymbol(
                        kind="symbol",
                        name=current_name,
                        start_line=current_start,
                        end_line=idx,
                        raw_text=raw,
                        normalized_body=cls._normalize_code_text(raw)
                    ))
                current_name = m.group(1)
                current_start = idx

        if current_name is not None:
            raw = "\n".join(lines[current_start:])
            symbols.append(SemanticSymbol(
                kind="symbol",
                name=current_name,
                start_line=current_start,
                end_line=len(lines),
                raw_text=raw,
                normalized_body=cls._normalize_code_text(raw)
            ))
        return symbols

    @staticmethod
    def _normalize_code_text(text: str) -> str:
        # Strip comments
        no_comm = re.sub(r"#.*?$|//.*?$|/\*[\s\S]*?\*/", "", text, flags=re.MULTILINE)
        # Normalize whitespace
        tokens = no_comm.split()
        return " ".join(tokens)

    @classmethod
    def compare_semantics(cls, left_code: str, right_code: str, language: str = "python") -> List[SemanticDiffMatch]:
        """
        Compares two source documents semantically, detecting reordered functions,
        docstring changes, and true modifications.
        """
        left_syms = cls.extract_symbols(left_code, language)
        right_syms = cls.extract_symbols(right_code, language)

        left_by_name: Dict[str, SemanticSymbol] = {s.name: s for s in left_syms if s.name != "<anonymous>"}
        right_by_name: Dict[str, SemanticSymbol] = {s.name: s for s in right_syms if s.name != "<anonymous>"}

        matches: List[SemanticDiffMatch] = []
        matched_right_names: Set[str] = set()

        for l_idx, l_sym in enumerate(left_syms):
            if l_sym.name in right_by_name:
                r_sym = right_by_name[l_sym.name]
                r_idx = right_syms.index(r_sym)
                matched_right_names.add(l_sym.name)

                # Check body equality
                if l_sym.normalized_body == r_sym.normalized_body:
                    if l_idx != r_idx:
                        matches.append(SemanticDiffMatch(
                            left_symbol=l_sym,
                            right_symbol=r_sym,
                            status="reordered",
                            explanation=f"'{l_sym.name}' was reordered (position {l_idx+1} -> {r_idx+1}) with identical logic."
                        ))
                    else:
                        matches.append(SemanticDiffMatch(
                            left_symbol=l_sym,
                            right_symbol=r_sym,
                            status="identical",
                            explanation=f"'{l_sym.name}' is structurally identical."
                        ))
                else:
                    # Check if only docstring or formatting changed
                    if l_sym.docstring != r_sym.docstring and cls._strip_docstrings(l_sym.raw_text) == cls._strip_docstrings(r_sym.raw_text):
                        matches.append(SemanticDiffMatch(
                            left_symbol=l_sym,
                            right_symbol=r_sym,
                            status="docstring_only",
                            explanation=f"'{l_sym.name}' has reformatted/updated docstring only; code logic unchanged."
                        ))
                    else:
                        matches.append(SemanticDiffMatch(
                            left_symbol=l_sym,
                            right_symbol=r_sym,
                            status="modified",
                            explanation=f"'{l_sym.name}' was modified."
                        ))
            else:
                matches.append(SemanticDiffMatch(
                    left_symbol=l_sym,
                    right_symbol=None,
                    status="left_only",
                    explanation=f"'{l_sym.name}' was deleted in right."
                ))

        for r_sym in right_syms:
            if r_sym.name not in left_by_name and r_sym.name not in matched_right_names:
                matches.append(SemanticDiffMatch(
                    left_symbol=None,
                    right_symbol=r_sym,
                    status="right_only",
                    explanation=f"'{r_sym.name}' is newly added in right."
                ))

        return matches

    @staticmethod
    def _strip_docstrings(code: str) -> str:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                    if (node.body and isinstance(node.body[0], ast.Expr) and
                            isinstance(node.body[0].value, (ast.Str, ast.Constant))):
                        node.body.pop(0)
            return " ".join(ast.unparse(tree).split())
        except Exception:
            return re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', '', code).strip()
