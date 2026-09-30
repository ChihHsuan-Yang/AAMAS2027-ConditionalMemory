"""Gold-blind localization: choose the source region to show the reader.

Why this module exists
----------------------
The first floor-effect pilot was VOID. It showed the reader the first 90 lines
of each file while the gold patch edited lines 278 / 152 / 106 / 1386 of files
up to 7,079 lines long, then asked for a byte-exact SEARCH block. A search for
code the model was never shown cannot succeed, so ``search_miss`` was the only
reachable outcome and the measurement could not have come out any other way.

The fix is a real localizer. The fix has one hard constraint:

    🔴 THE LOCALIZER MUST NOT CONSULT THE GOLD PATCH.

If the region were chosen using the gold patch, the pilot would be void again
for a new reason: we would have handed the model the answer's location and
measured our own oracle. Enforced structurally -- :func:`localize` accepts the
file text and the ISSUE TEXT, and there is no parameter through which a patch
could arrive -- and checked at runtime by :func:`assert_gold_blind`.

The rule
--------
BM25-style lexical scoring of candidate windows against the issue text, where
candidates are *syntactic units* (top-level ``def`` / ``class`` blocks) rather
than arbitrary line spans, so a returned region is always something a model can
edit coherently. Identifiers in the issue (``foo.bar``, ``Baz``, backticked
spans, traceback frames) are weighted above prose, because an issue naming
``_print_Min`` is pointing at the code far more reliably than its English.

Scoring is deterministic and makes no model call.

Evaluating the localizer is legitimate; USING the gold patch to localize is not
-------------------------------------------------------------------------------
:func:`recall_at_region` measures whether the chosen region contains the gold
edit. That *reads* the gold patch, but only to score the localizer after the
fact -- it is never in the path that produces a region. The separation is the
same one the leakage module draws between flagging and dropping.
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

__all__ = [
    "Region",
    "assert_gold_blind",
    "extract_query_terms",
    "candidate_regions",
    "localize",
    "gold_edit_lines",
    "recall_at_region",
]

# Identifiers that carry no localizing signal.
_STOP = frozenset("""
the a an and or but if then else for while with as is are was were be been being
to of in on at by from into over under this that these those it its i you we they
def class self return not none true false import none type value error should would
when what which who why how can could will do does did has have had get set new old
""".split())

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICK = re.compile(r"`([^`]+)`")
_DOTTED = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]+)+\b")
_TRACEBACK = re.compile(r'File "[^"]+", line \d+, in (\S+)')
_CODEFENCE = re.compile(r"```.*?```", re.S)


class GoldLeakedIntoLocalizer(AssertionError):
    """The localizer was given, or produced, something derived from the patch."""


@dataclass(frozen=True)
class Region:
    """A contiguous, syntactically coherent span of one source file.

    ``start_line`` / ``end_line`` are 1-based and inclusive.
    """

    path: str
    start_line: int
    end_line: int
    text: str
    score: float
    kind: str
    name: str = ""

    @property
    def n_lines(self) -> int:
        return self.end_line - self.start_line + 1

    def contains_line(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line

    def render(self) -> str:
        return f"# {self.path} lines {self.start_line}-{self.end_line}\n{self.text}"


# --------------------------------------------------------------------------
# query side -- issue text only
# --------------------------------------------------------------------------


def extract_query_terms(issue_text: str) -> Counter:
    """Weighted terms from an ISSUE. Never sees any patch.

    Weights are ordinal, not tuned: an identifier the reporter typed inside
    backticks or a traceback frame is a far stronger pointer at the code than
    a word in the surrounding prose.
    """
    text = issue_text or ""
    terms: Counter = Counter()

    def add(sources: Iterable[str], weight: int) -> None:
        for s in sources:
            for tok in _IDENT.findall(s):
                low = tok.lower()
                if len(tok) > 2 and low not in _STOP:
                    terms[low] += weight

    add(_TRACEBACK.findall(text), 5)
    add(_BACKTICK.findall(text), 4)
    add(_DOTTED.findall(text), 4)
    add(_CODEFENCE.findall(text), 2)
    # plain prose last, lowest weight
    add([_CODEFENCE.sub(" ", text)], 1)
    return terms


# --------------------------------------------------------------------------
# document side -- syntactic units of the file
# --------------------------------------------------------------------------


def _unit_spans(source: str) -> list[tuple[int, int, str, str]]:
    """(start, end, kind, name) for top-level defs/classes and methods.

    Falls back to fixed windows when the file does not parse -- a file at a
    historical commit may use syntax this interpreter rejects, and returning
    nothing would silently make the localizer un-runnable on that instance.
    """
    out: list[tuple[int, int, str, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.lineno, getattr(node, "end_lineno", node.lineno),
                        "function", node.name))
        elif isinstance(node, ast.ClassDef):
            out.append((node.lineno, getattr(node, "end_lineno", node.lineno),
                        "class", node.name))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((sub.lineno, getattr(sub, "end_lineno", sub.lineno),
                                "method", f"{node.name}.{sub.name}"))
    return out


def _windows(n_lines: int, size: int, stride: int) -> list[tuple[int, int, str, str]]:
    out = []
    start = 1
    while start <= n_lines:
        out.append((start, min(start + size - 1, n_lines), "window", ""))
        if start + size - 1 >= n_lines:
            break
        start += stride
    return out


def candidate_regions(
    source: str, path: str, *, max_lines: int = 120, stride: int = 60
) -> list[tuple[int, int, str, str]]:
    """Candidate spans: syntactic units, plus sliding windows as a fallback.

    Units longer than ``max_lines`` are also covered by windows so a huge class
    body cannot become one unselectable blob.
    """
    lines = source.splitlines()
    n = len(lines)
    units = [u for u in _unit_spans(source) if u[1] - u[0] + 1 <= max_lines]
    cands = list(units)
    cands.extend(_windows(n, max_lines, stride))
    seen: set[tuple[int, int]] = set()
    uniq = []
    for s, e, k, nm in cands:
        if (s, e) in seen:
            continue
        seen.add((s, e))
        uniq.append((s, e, k, nm))
    return uniq


def _score(span_text: str, query: Counter, idf: dict[str, float]) -> float:
    """Weighted lexical overlap, length-normalized (BM25-ish, k1 saturation)."""
    toks = [t.lower() for t in _IDENT.findall(span_text)]
    if not toks:
        return 0.0
    tf = Counter(toks)
    total = 0.0
    for term, qw in query.items():
        f = tf.get(term, 0)
        if not f:
            continue
        sat = (f * 2.5) / (f + 1.5)          # saturation, so repetition cannot dominate
        total += qw * idf.get(term, 1.0) * sat
    return total / math.sqrt(len(toks))       # prefer the tightest span carrying the hits


def localize(
    source: str,
    issue_text: str,
    *,
    path: str = "",
    top_k: int = 1,
    max_lines: int = 120,
    stride: int = 60,
) -> list[Region]:
    """Pick the region(s) to show the reader, from the ISSUE TEXT ALONE.

    🔴 There is deliberately NO parameter for a patch, a gold answer, or a test.
    The signature is the guarantee; :func:`assert_gold_blind` re-checks it.
    """
    lines = source.splitlines()
    if not lines:
        return []
    query = extract_query_terms(issue_text)
    cands = candidate_regions(source, path, max_lines=max_lines, stride=stride)
    if not cands:
        return []

    # idf over candidate spans, so a term appearing in every span is discounted
    df: Counter = Counter()
    span_tokens: list[set[str]] = []
    for s, e, _k, _n in cands:
        toks = {t.lower() for t in _IDENT.findall("\n".join(lines[s - 1:e]))}
        span_tokens.append(toks)
        for t in toks:
            df[t] += 1
    N = len(cands)
    idf = {t: math.log(1.0 + N / (1.0 + c)) for t, c in df.items()}

    scored: list[Region] = []
    for (s, e, kind, name) in cands:
        text = "\n".join(lines[s - 1:e])
        sc = _score(text, query, idf)
        scored.append(Region(path=path, start_line=s, end_line=e, text=text,
                             score=sc, kind=kind, name=name))
    # deterministic: score desc, then earliest, then shortest
    scored.sort(key=lambda r: (-r.score, r.start_line, r.n_lines))
    return scored[:top_k]


def assert_gold_blind(fn: Any = localize) -> None:
    """Fail if the localizer's signature could accept gold-derived input.

    A structural check, not a stylistic one: it is what stops the pilot being
    voided a second time.
    """
    import inspect
    banned = {"patch", "gold", "gold_patch", "solution", "test_patch",
              "fail_to_pass", "answer", "diff"}
    params = set(inspect.signature(fn).parameters)
    bad = params & banned
    if bad:
        raise GoldLeakedIntoLocalizer(
            f"{getattr(fn, '__name__', fn)} accepts gold-derived parameters: {sorted(bad)}"
        )


# --------------------------------------------------------------------------
# scoring the localizer -- reads gold, but never feeds it back
# --------------------------------------------------------------------------

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? ", re.M)


def gold_edit_lines(patch: str, path: str) -> list[int]:
    """Pre-image line numbers the gold patch touches in ``path``.

    Used ONLY to score a region after it has been chosen. Never an input to
    :func:`localize`.
    """
    out: list[int] = []
    for seg in (patch or "").split("diff --git ")[1:]:
        header = seg.split("\n", 1)[0]
        if path not in header:
            continue
        for m in _HUNK.finditer(seg):
            start = int(m.group(1))
            count = int(m.group(2) or 1)
            out.extend(range(start, start + max(count, 1)))
    return sorted(set(out))


def recall_at_region(regions: Sequence[Region], patch: str, path: str) -> bool:
    """Did the localizer put the gold edit inside a region we will show?

    This is the number that says whether a pilot is interpretable at all: if
    it is False, a byte-exact SEARCH is impossible and a miss measures the
    localizer, not the memory.
    """
    gold = gold_edit_lines(patch, path)
    if not gold:
        return False
    return any(r.contains_line(g) for r in regions for g in gold)
