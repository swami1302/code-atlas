import itertools
import re
from dataclasses import dataclass, replace

import tree_sitter_javascript
import tree_sitter_php
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

# Cuts one file into chunks: ranges of whole lines that become the unit of search,
# citation and embedding. Pure logic (no disk, network or database), easy to test.

# ~400 tokens: fits any embedding model, and small enough that search can point at
# the exact code that answers a question
MAX_CHARS = 1500

# Code languages get a Tree-sitter parser; every other language is split as text
PARSERS = {
    name: Parser(Language(grammar))
    for name, grammar in {
        "python": tree_sitter_python.language(),
        "javascript": tree_sitter_javascript.language(),
        "typescript": tree_sitter_typescript.language_typescript(),
        # TSX is its own grammar: the TypeScript one can't parse <div/>
        "tsx": tree_sitter_typescript.language_tsx(),
        # language_php also accepts HTML around the <?php ... ?> blocks
        "php": tree_sitter_php.language_php(),
    }.items()
}

# Syntax-tree node types that define a symbol, across the grammars above
KINDS = {
    "function_definition": "function",  # Python, PHP
    "function_declaration": "function",  # JS/TS
    "generator_function_declaration": "function",
    "method_definition": "method",  # JS/TS class body
    "method_declaration": "method",  # PHP
    "class_definition": "class",  # Python
    "class_declaration": "class",  # JS/TS, PHP
    "abstract_class_declaration": "class",
    "interface_declaration": "interface",
    "trait_declaration": "trait",
}


@dataclass(frozen=True)
class Chunk:
    start_line: int  # 1-based, inclusive: what editors and citations show
    end_line: int
    content: str
    symbol: str | None = None  # e.g. "process" or "Service.save"; None for loose code
    kind: str | None = None  # function, method, class, interface, trait
    # Only on pieces 2+ of a split function: its def line(s), which those pieces
    # lack. None means nothing is missing from content.
    signature: str | None = None


def chunk_file(language: str, text: str) -> list[Chunk]:
    # Split on "\n" only: Tree-sitter counts rows that way. str.splitlines() also
    # splits on rarer characters (\x0c, \u2028, ...), which would shift every
    # line number after them.
    lines = text.split("\n")
    parser = PARSERS.get(language)
    if parser is None:
        return text_chunks(lines)
    # Syntax errors don't raise: Tree-sitter marks them as ERROR nodes and goes on
    root = parser.parse(text.encode()).root_node
    return code_chunks(lines, root.named_children, 0, len(lines) - 1)


def definition(node: Node) -> tuple[Node, str, str] | None:
    """(definition node, name, kind) if node defines a symbol, else None.
    Looks through the wrappers real code puts around definitions."""
    # @app.post(...) def f / export function f / export class C
    if node.type in ("decorated_definition", "export_statement"):
        inner = node.child_by_field_name("definition") or node.child_by_field_name(
            "declaration"
        )
        return definition(inner) if inner else None
    # const Button = () => ... (how React components and helpers are usually written)
    if node.type == "lexical_declaration":
        declarators = node.named_children
        if len(declarators) == 1 and declarators[0].type == "variable_declarator":
            value = declarators[0].child_by_field_name("value")
            if value and value.type in ("arrow_function", "function_expression"):
                name = declarators[0].child_by_field_name("name")
                return value, name.text.decode(), "function"
        return None
    if kind := KINDS.get(node.type):
        name = node.child_by_field_name("name")
        return node, name.text.decode() if name else "?", kind
    return None


def code_chunks(
    lines: list[str],
    children: list[Node],
    start: int,
    end: int,
    parent: tuple[str, str] | None = None,
) -> list[Chunk]:
    """Chunks for rows start..end (0-based, inclusive): one per symbol among
    children, and the code between symbols (imports, constants, routes setup)
    grouped as its own chunks so no line is lost. parent is set inside a class."""
    chunks = []
    cursor = start  # first row not in a chunk yet
    comment_row = None  # first row of the comments right before the current node
    for child in children:
        if child.type == "comment":
            if comment_row is None:
                comment_row = child.start_point.row
            continue
        found = definition(child)
        if found is None:
            comment_row = None  # comments followed by plain code stay with that code
            continue
        node, name, kind = found
        # Docstrings/JSDoc/PHPDoc directly above a symbol belong to its chunk
        first = max(
            cursor, child.start_point.row if comment_row is None else comment_row
        )
        comment_row = None
        last = child.end_point.row
        if first > last:  # two symbols on one line: already in the previous chunk
            continue
        chunks += loose_chunks(lines, cursor, first - 1, parent)
        if parent:
            name = f"{parent[0]}.{name}"
            kind = "method" if kind == "function" else kind  # Python methods
        chunks += symbol_chunks(lines, node, first, last, name, kind)
        cursor = last + 1
    chunks += loose_chunks(lines, cursor, end, parent)
    return chunks


def symbol_chunks(
    lines: list[str], node: Node, start: int, end: int, name: str, kind: str
) -> list[Chunk]:
    """One chunk for a symbol that fits; otherwise a class splits into its methods,
    and anything else into pieces of whole lines that all keep the symbol's name."""
    if size(lines, start, end) <= MAX_CHARS:
        return [make(lines, start, end, name, kind)]
    body = node.child_by_field_name("body")
    if kind in ("class", "interface", "trait") and body is not None:
        return code_chunks(lines, body.named_children, start, end, (name, kind))
    first, *rest = pack(
        lines, [(row, row) for row in range(start, end + 1)], name, kind
    )
    if body is None:
        return [first, *rest]
    # Rows from the def to where the body starts. A Python block starts at its
    # first statement, so stop the row before; a { body opens on the signature's
    # last row (often the def row itself), so include it. Decorators are left out:
    # node is the def itself, not its wrapper.
    sig_end = body.start_point.row - 1 if body.type == "block" else body.start_point.row
    sig_rows = lines[node.start_point.row : max(sig_end, node.start_point.row) + 1]
    signature = "\n".join(sig_rows)
    return [first, *(replace(piece, signature=signature) for piece in rest)]


def loose_chunks(
    lines: list[str], start: int, end: int, parent: tuple[str, str] | None
) -> list[Chunk]:
    """Code outside any symbol. Inside a class (parent set) it is the class's own
    header and fields, so it carries the class name."""
    if not any(lines[row].strip() for row in range(start, end + 1)):
        return []
    name, kind = parent or (None, None)
    # ponytail: tiny loose chunks (a lone `logger = ...`) aren't merged with their
    # neighbours; merge them if retrieval evals show they hurt results
    return pack(lines, [(row, row) for row in range(start, end + 1)], name, kind)


def text_chunks(lines: list[str]) -> list[Chunk]:
    """Docs and config: paragraphs (blocks between blank lines) packed up to the cap."""
    units = []
    first = None
    for row, line in enumerate([*lines, ""]):  # the extra "" closes the last block
        if line.strip() and first is None:
            first = row
        elif not line.strip() and first is not None:
            if size(lines, first, row - 1) <= MAX_CHARS:
                units.append((first, row - 1))
            else:  # a paragraph over the cap is packed line by line instead
                units += [(r, r) for r in range(first, row)]
            first = None
    return pack(lines, units, None, None)


def pack(
    lines: list[str], units: list[tuple[int, int]], name: str | None, kind: str | None
) -> list[Chunk]:
    """Join consecutive row ranges into chunks of at most MAX_CHARS. A single unit
    over the cap (one very long line) becomes its own chunk: lines are never cut,
    so citations always point at whole lines."""
    chunks = []
    current = None  # (first row, last row) of the chunk being filled
    for first, last in units:
        if current and size(lines, current[0], last) <= MAX_CHARS:
            current = (current[0], last)
        else:
            if current:
                chunks.append(make(lines, *current, name, kind))
            current = (first, last)
    if current:
        chunks.append(make(lines, *current, name, kind))
    return chunks


def size(lines: list[str], start: int, end: int) -> int:
    return len("\n".join(lines[start : end + 1]))


def make(lines: list[str], start: int, end: int, name, kind) -> Chunk:
    # Blank lines at the edges carry nothing; callers never pass an all-blank range
    while not lines[start].strip():
        start += 1
    while not lines[end].strip():
        end -= 1
    return Chunk(start + 1, end + 1, "\n".join(lines[start : end + 1]), name, kind)


def embed_text(path: str, chunk: Chunk) -> str:
    """What gets embedded for a chunk: a header saying where it lives, the
    signature it lacks (if split), then its lines. content_hash is taken over
    this text, so it changes whenever the embedding would."""
    header = f"{path} > {chunk.symbol}" if chunk.symbol else path
    return "\n".join(filter(None, [header, chunk.signature, chunk.content]))


# One name or word: get_current_user, getCurrentUser, HTTPServer, 429
WORD = re.compile(r"\w+")
# The parts of a name: an acronym (HTTP), a word (Server, get) or a run of digits
PART = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


def split_identifiers(text: str) -> str:
    """Text as plain lowercase words for the keyword index. A name gives its parts,
    then the parts joined: getCurrentUser and get_current_user both become
    "get current user getcurrentuser", so a search for either spelling, or for
    "current user", finds both. Punctuation is dropped, so Postgres only sees plain
    words (its parser would read os.path.join as one host name)."""
    words = []
    for word in WORD.findall(text):
        parts = PART.findall(word)
        if len(parts) > 1:
            words += [part.lower() for part in parts]
        # Underscores dropped: __init__ is init, get_user joins to getuser
        if joined := word.replace("_", "").lower():
            words.append(joined)
    return " ".join(words)


if __name__ == "__main__":
    # Self-check: python chunking.py

    def spans(language: str, text: str) -> list[tuple[int, int, str | None]]:
        return [
            (c.start_line, c.end_line, c.symbol) for c in chunk_file(language, text)
        ]

    # Decorated route keeps its decorator and the comment above it; the non-ASCII
    # comment proves line numbers don't drift (Tree-sitter positions are bytes)
    route = """import logging

# Café ☕ health check
@app.get("/health")
async def health():
    return {"ok": True}

logger = logging.getLogger(__name__)
"""
    assert spans("python", route) == [(1, 1, None), (3, 6, "health"), (8, 8, None)]

    # Exported function with JSDoc, exported arrow component, plain constant
    page = """/** The home page */
export default function Page() {
  return <div>é</div>
}
export const Button = () => <b />
const x = 1
"""
    assert spans("tsx", page) == [(1, 4, "Page"), (5, 5, "Button"), (6, 6, None)]

    php = """<?php
/** Adds two numbers */
function add($a, $b) { return $a + $b; }
class A { public function m() {} }
"""
    assert spans("php", php) == [(1, 1, None), (2, 3, "add"), (4, 4, "A")]

    # Oversized function: whole-line pieces under the cap, all named, no gaps.
    # Pieces 2+ carry the signature (multi-line params, no decorator).
    body = "".join(f"    x{i} = '{'a' * 40}'\n" for i in range(100))
    big = "@cache\ndef big(\n    a,\n):\n" + body
    pieces = chunk_file("python", big)
    assert len(pieces) > 1 and {c.symbol for c in pieces} == {"big"}
    assert all(len(c.content) <= MAX_CHARS for c in pieces)
    assert all(a.end_line + 1 == b.start_line for a, b in itertools.pairwise(pieces))
    assert (pieces[0].start_line, pieces[-1].end_line) == (1, 104)
    assert pieces[0].signature is None
    assert {c.signature for c in pieces[1:]} == {"def big(\n    a,\n):"}
    # Brace languages: the signature ends on the row that opens the body
    big_js = "function big(a) {\n" + body.replace("'\n", "';\n") + "}\n"
    assert {c.signature for c in chunk_file("javascript", big_js)[1:]} == {
        "function big(a) {"
    }

    # Oversized class: split at its methods, which get Class.method names
    method = "    def {}(self):\n" + "        y = 1  # padding\n" * 25
    service = 'class Service:\n    """Saves things."""\n\n' + "\n".join(
        method.format(n) for n in "abc"
    )
    assert [(c.symbol, c.kind) for c in chunk_file("python", service)] == [
        ("Service", "class"),
        ("Service.a", "method"),
        ("Service.b", "method"),
        ("Service.c", "method"),
    ]

    # Text: small paragraphs pack into one chunk; long docs split at paragraphs
    assert spans("markdown", "# Title\n\nPara one.\n\nPara two.\n") == [(1, 5, None)]
    doc = "\n\n".join("word " * 80 for _ in range(10))
    assert all(len(c.content) <= MAX_CHARS for c in chunk_file("markdown", doc))
    assert chunk_file("python", "") == []

    # Embed text: header, then the signature only when the chunk lacks it
    assert embed_text("a.py", pieces[1]).startswith(
        "a.py > big\ndef big(\n    a,\n):\n"
    )
    assert embed_text("README.md", Chunk(1, 1, "# Hi")) == "README.md\n# Hi"

    # Keyword text: both spellings of a name give the same words
    assert split_identifiers("getCurrentUser") == "get current user getcurrentuser"
    assert split_identifiers("get_current_user") == "get current user getcurrentuser"
    assert split_identifiers("HTTPServer utf8") == "http server httpserver utf 8 utf8"
    assert (
        split_identifiers("backend/indexing.py > save_chunks")
        == "backend indexing py save chunks savechunks"
    )
    assert split_identifiers("def __init__(self): return 429") == (
        "def init self return 429"
    )
    assert split_identifiers("# Café") == "café"
    print("chunking: ok")
