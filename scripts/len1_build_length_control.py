#!/usr/bin/env python3
"""LEN1: the length-controlled representation test. Executes docs/LENGTH_CONTROL_PRECOMMITMENT.md.

The question: Raw memories are ~30x longer than the model-written ones. Is the
measured Raw advantage a REPRESENTATION effect, or a MORE-TOKENS effect?

Eight arms, ALL IN ONE SESSION (defect #25: gpt-oss-120b is deterministic
within a session and NOT across one, so the published Raw-vs-Summary
comparison -- measured on two different days -- is confounded and is NOT used
as a comparator here).

THE TRUNCATION RULE IS CONTENT-BLIND, and that is the whole point
------------------------------------------------------------------
A rule that picked "the most informative span" would smuggle in the value
judgement under test (MEMORY_PROTOCOL section 1A; the same reason
RawExtractiveWriter takes the WHOLE segment). These rules take a FIXED
POSITIONAL SLICE to a FIXED TOKEN BUDGET and read no task, no question, no
gold answer, no reward and no embedding.

Budget is matched in the OFFICIAL TOKENIZER, by binary search on characters --
never assumed from character counts -- and the reader tokenizer's count is
recorded per cell so the match is auditable in the tokenizer that consumes it.

Everything else is held fixed from the screened run: the same 277 cells, the
same K=4 filler and pool, the same system prompt, the same reader config, and
-- load-bearing -- THE SAME TARGET POSITION, seeded by (task_id, manifest
memory_id). Varying position changed the answer in 8 of 12 cells
(docs/POSITION_EFFECT.md), so position equality across arms is asserted, not
hoped for.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from p1mem import schema as S  # noqa: E402
from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.cells import SYSTEM, MemoryUnit, build_context  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.embed import EMBED_DIM, EMBED_MODEL, EmbeddingClient  # noqa: E402
from p1mem.memory.tokens import count_tokens, tokenizer_provenance  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402
from p1mem.writer import CellWriter  # noqa: E402

PROMPT_VERSION = "p1_deltau_raw_v1"   # unchanged: a bump would break comparability
STRATA = ("BEARING", "MATCHED_CONTROL")
EMBED_TOKEN_BUDGET = 2000             # identical to r2_run_representations.py
EMBED_MIN_BUDGET = 500

TRUNC_LAST_RULE = "trunc_last_n_tokens@1.0.0"
TRUNC_FIRST_RULE = "trunc_first_n_tokens@1.0.0"
RAW_RULE = "raw_whole_segment@1.0.0"

#: arm -> (condition_id, kind, budget). budget None = "that cell's own summary
#: token count". kind 'raw'/'summary'/'structured' reuse the frozen memory text.
ARMS: dict[str, tuple[str, str, int | None]] = {
    "raw":                 ("lmev2_raw_lenctl_v1",               "raw",         None),
    "summary":             ("lmev2_summary_lenctl_v1",           "summary",     None),
    "structured":          ("lmev2_structured_lenctl_v1",        "structured",  None),
    "trunc_last_matched":  ("lmev2_trunclast_matched_lenctl_v1", "trunc_last",  None),
    "trunc_first_matched": ("lmev2_truncfirst_matched_lenctl_v1","trunc_first", None),
    "trunc_last_1024":     ("lmev2_trunclast_1024_lenctl_v1",    "trunc_last",  1024),
    "trunc_last_4096":     ("lmev2_trunclast_4096_lenctl_v1",    "trunc_last",  4096),
    "trunc_last_20000":    ("lmev2_trunclast_20000_lenctl_v1",   "trunc_last",  20000),
}

#: ``memory_representation`` is a CLOSED enum describing HOW the memory is
#: written down, not which arm it belongs to. A truncated segment is extractive
#: verbatim text with zero writer calls, so it is written down ``raw``; the arm
#: identity travels in ``condition_id`` and ``provenance.arm``. Passing the arm
#: name here is a ``bad_enum`` rejection of every row -- see the comment at the
#: write site.
REPR_OF_ARM: dict[str, str] = {
    "raw": "raw", "summary": "summary", "structured": "structured",
    "trunc_last_matched": "raw", "trunc_first_matched": "raw",
    "trunc_last_1024": "raw", "trunc_last_4096": "raw",
    "trunc_last_20000": "raw",
}


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def _fit_prefix_tokens(text: str, budget: int) -> str:
    """Longest PREFIX within ``budget`` official tokens (embedding input only)."""
    if count_tokens(text) <= budget:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_tokens(text[:mid]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


def embed_with_backoff(emb, labelled, budget):
    """Verbatim from r2_run_representations.py: semantic_similarity is
    NON-NULLABLE on this benchmark, so a failed embedding must raise rather
    than write a null into a field the validator refuses to accept as null."""
    from p1mem.client import EndpointError  # noqa: PLC0415
    vecs, used = {}, {}
    for key, text in labelled:
        b = budget
        while True:
            t = _fit_prefix_tokens(text, b)
            try:
                vecs[key] = emb.embed([t])[0]
                used[key] = b
                break
            except EndpointError:
                b //= 2
                if b < EMBED_MIN_BUDGET:
                    raise RuntimeError(
                        f"embedding {key!r} failed even at {EMBED_MIN_BUDGET} tokens; "
                        f"refusing to write a null into non-nullable "
                        f"semantic_similarity")
                log(f"  embed retry {key[:32]}: budget -> {b}")
    return vecs, used


# ---------------------------------------------------------------- the rule
def _fit_tokens(text: str, budget: int, *, from_end: bool) -> str:
    """Longest prefix (or suffix) of ``text`` whose OFFICIAL token count <= budget.

    Binary search on characters against the official tokenizer -- the same
    routine r2_run_representations.py already uses for embedding budgets. A
    character-count approximation would put a wrong x-axis under the whole
    experiment, which is precisely the defect the precommitment forbids.
    """
    if count_tokens(text) <= budget:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        piece = text[-mid:] if from_end else text[:mid]
        if count_tokens(piece) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return text[-lo:] if from_end else text[:lo]


def truncate(text: str, budget: int, kind: str) -> str:
    if kind == "trunc_last":
        return _fit_tokens(text, budget, from_end=True)
    if kind == "trunc_first":
        return _fit_tokens(text, budget, from_end=False)
    raise ValueError(kind)


# ------------------------------------------------------- C-PLANT: the guards
def assert_budget_exact(text: str, budget: int, *, where: str) -> None:
    n = count_tokens(text)
    if n > budget:
        raise AssertionError(f"{where}: {n} tokens EXCEEDS budget {budget}")


def assert_budget_tight(text: str, full: str, budget: int, *, from_end: bool,
                        where: str) -> None:
    """The slice must be MAXIMAL: one more character must break the budget.

    🔴 The earlier form of this guard required ``n == budget`` exactly, and it
    was WRONG -- not conservative, wrong. It fired on
    ``trunc_first_matched|3331c568:2-2``, where the budget is 196 and the
    official tokenizer admits NO prefix of exactly 196 tokens: measured, the
    maximal prefix is 510 chars = 195 tokens and 511 chars = 197 tokens. A
    token boundary simply does not land on 196 there. Requiring exact equality
    demands a slice that does not exist, so the guard was unsatisfiable on that
    cell for a reason that has nothing to do with length matching.

    Maximality is the property the design actually needs: it is what makes the
    slice the longest content-blind window that fits the budget, so the arm
    cannot be accused of being handicapped by an under-filled budget. It is
    also strictly stronger than ``n == budget`` in the cases where an exact hit
    exists, and it remains well-defined in the cases where it does not. The
    achieved-vs-target delta is recorded per cell either way, so the residual
    (measured: 0 on 56/57 cells, -1 on one) is auditable rather than asserted
    away.
    """
    n, nf = count_tokens(text), count_tokens(full)
    if n > budget:
        raise AssertionError(f"{where}: {n} tokens EXCEEDS budget {budget}")
    if nf <= budget:
        return  # the whole text fits; there is nothing to saturate
    if len(text) >= len(full):
        raise AssertionError(
            f"{where}: full text is {nf} tokens > budget {budget} but the slice "
            f"was not shortened at all")
    one_more = full[-(len(text) + 1):] if from_end else full[:len(text) + 1]
    if count_tokens(one_more) <= budget:
        raise AssertionError(
            f"{where}: slice is {n} tokens against budget {budget} and is NOT "
            f"maximal -- one more character still fits "
            f"({count_tokens(one_more)} tokens). The budget is under-filled and "
            f"the arms would not be length-matched")


def run_plant_controls() -> list[dict[str, Any]]:
    """Plant each defect and require the guard to FAIL. A guard verified only
    on its home case is not known to discriminate.

    Every plant is paired with its negative control: a control that cannot
    fail is not a control, and a control that cannot PASS is a broken test
    rather than a strict one.
    """
    out: list[dict[str, Any]] = []

    def check(name: str, fn, expect_raise: bool) -> None:
        try:
            fn()
            fired = False
        except AssertionError:
            fired = True
        out.append({"control": name, "defect_planted": expect_raise,
                    "guard_fired": fired, "passed": fired == expect_raise})

    body = "alpha bravo charlie delta echo foxtrot golf hotel india juliet " * 400
    good = truncate(body, 64, "trunc_last")
    good_first = truncate(body, 64, "trunc_first")

    # P1 -- truncation that returns the full text
    check("P1_untruncated_text_is_caught",
          lambda: assert_budget_exact(body, 64, where="P1"), True)
    check("P1_negative_control_clean_slice_passes",
          lambda: assert_budget_exact(good, 64, where="P1n"), False)
    # P1b -- the full text also has to be caught by the MAXIMALITY guard, which
    # is the one that actually runs on every cell.
    check("P1b_untruncated_text_caught_by_maximality",
          lambda: assert_budget_tight(body, body, 64, from_end=True, where="P1b"), True)
    # P2 -- a slice short of the budget (off-by-N the under-filling direction)
    short = truncate(body, 39, "trunc_last")
    check("P2_undersaturated_budget_is_caught",
          lambda: assert_budget_tight(short, body, 64, from_end=True, where="P2"), True)
    check("P2_negative_control_saturated_slice_passes",
          lambda: assert_budget_tight(good, body, 64, from_end=True, where="P2n"), False)
    check("P2_negative_control_saturated_prefix_passes",
          lambda: assert_budget_tight(good_first, body, 64, from_end=False,
                                      where="P2n_first"), False)
    # P2b -- off by +25 tokens the OVER direction, which is the shape the
    # precommitment names. Over-budget must be caught by BOTH guards.
    over = truncate(body, 89, "trunc_last")
    check("P2b_over_budget_by_25_caught_by_exact",
          lambda: assert_budget_exact(over, 64, where="P2b"), True)
    check("P2b_over_budget_by_25_caught_by_maximality",
          lambda: assert_budget_tight(over, body, 64, from_end=True, where="P2b2"), True)
    # P2c -- POSITIVE CONTROL FOR THE RELAXATION ITSELF, and the reason this
    # control needs its own corpus.
    #
    # The maximality guard must still PASS on a slice that is maximal but NOT
    # equal to the budget, because such slices really occur: measured on
    # trunc_first_matched|3331c568:2-2, budget 196, the maximal prefix is 510
    # chars = 195 tokens and 511 chars = 197 tokens, so no prefix of exactly
    # 196 tokens exists. That is the case the old exact-equality guard wrongly
    # rejected, and this control is what stops the relaxation being silently
    # reverted.
    #
    # ``body`` above CANNOT exercise it: measured, a whitespace-delimited
    # ASCII corpus admits an exact hit at every budget from 20 to 400 in both
    # directions (0 inexact cases), as do runs of one letter, CJK, mixed
    # CJK/ASCII and long URLs. Only text whose tokens span several characters
    # unevenly skips a count. A control run only on a corpus that cannot
    # produce the condition is a control aimed at nothing, so this one uses a
    # corpus that provably does -- and asserts that it does before using it.
    inexact_body = "🙂🧪🔬" * 1500
    inex: tuple[str, int, bool] | None = None
    for bud in range(30, 260):
        for fe in (True, False):
            s = truncate(inexact_body, bud, "trunc_last" if fe else "trunc_first")
            if count_tokens(s) != bud:
                inex = (s, bud, fe)
                break
        if inex:
            break
    if inex is None:
        # The corpus stopped producing the condition: this control would pass
        # vacuously, which is worse than failing. Refuse.
        out.append({"control": "P2c_maximal_but_inexact_slice_passes",
                    "defect_planted": False, "guard_fired": None, "passed": False,
                    "_why": "the inexact-boundary corpus produced no inexact "
                            "case, so this control could not discriminate"})
    else:
        s, bud, fe = inex
        check("P2c_maximal_but_inexact_slice_passes",
              lambda: assert_budget_tight(s, inexact_body, bud, from_end=fe,
                                          where="P2c"), False)
        out[-1]["_case"] = {"budget": bud, "achieved": count_tokens(s),
                            "from_end": fe,
                            "_what": "maximal slice whose token count != budget; "
                                     "the guard must accept it"}
        # and the NEGATIVE half: on that same inexact boundary, a slice one
        # character shorter is no longer maximal and MUST be caught.
        shorter = s[1:] if fe else s[:-1]
        check("P2c_negative_one_char_shorter_at_inexact_boundary_is_caught",
              lambda: assert_budget_tight(shorter, inexact_body, bud,
                                          from_end=fe, where="P2c_neg"), True)
    # P5 -- a None reward coerced to 0.0
    def coerce_none():
        rewards = [1.0, None, 0.0]
        if any(r is None for r in rewards):
            raise AssertionError("None reward present: must not be coerced")
    check("P5_none_reward_is_caught", coerce_none, True)
    check("P5_negative_control_all_scored_passes",
          lambda: (_ for _ in ()).throw(AssertionError("x"))
          if any(r is None for r in [1.0, 0.0]) else None, False)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--design-meta", type=Path,
                    default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--memories", type=Path,
                    default=REPO / "results/repr_scaleup/memories.jsonl")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--k-filler", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=9200)
    ap.add_argument("--out", type=Path, default=REPO / "results/length_control")
    ap.add_argument("--dry-run", action="store_true")
    #: SMOKE ONLY. Subsets the cell set to prove the write path end-to-end on
    #: real content before 8,864 calls are spent. The precommitment fixes the
    #: cell set at 277 and forbids adding or dropping a cell on any outcome, so
    #: a smoke run is NOT a result: it refuses to write into the real output
    #: directory and stamps the ledger as void. The 277-cell assertion still
    #: runs first, before any subsetting.
    ap.add_argument("--smoke-cells", type=int, default=0)
    #: Allow serving from a PRE-EXISTING cache file. Off by default because a
    #: cache written in an earlier session silently violates C-SESSION (§5.1).
    ap.add_argument("--resume-cache", action="store_true")
    args = ap.parse_args()
    if args.smoke_cells and args.out == REPO / "results/length_control":
        raise SystemExit(
            "--smoke-cells refuses to write to the real output directory; "
            "pass --out results/length_control_smoke")
    args.out.mkdir(parents=True, exist_ok=True)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for a in arms:
        if a not in ARMS:
            raise SystemExit(f"unknown arm {a!r}")

    log(f"vendored scorer: {lmev2.verify_vendored_scorer()[:16]}...")
    lmev2.assert_writer_blind()
    ok_ctrl, ctrl = LK.controls_summary()
    if not ok_ctrl:
        raise SystemExit("leakage detector controls FAILED")
    log(f"leakage detector controls: {sum(c.passed for c in ctrl)}/{len(ctrl)} PASS")

    plants = run_plant_controls()
    for p in plants:
        log(f"  [C-PLANT] {p['control']}: guard_fired={p['guard_fired']} "
            f"{'PASS' if p['passed'] else 'FAIL'}")
    if not all(p["passed"] for p in plants):
        raise SystemExit("C-PLANT: a guard did not behave as required; refusing to run")

    # ---- design + the 277 matched cells -------------------------------
    design = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    cells_all = [c for c in design if c["stratum"] in STRATA]
    meta = json.loads(args.design_meta.read_text())
    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}

    mem_rows = [json.loads(l) for l in args.memories.read_text().splitlines() if l.strip()]
    written = {(m["representation"], m["memory_unit_locator"]): m for m in mem_rows}

    # THE CELL SET IS THE 277 PRESENT IN ALL THREE PUBLISHED REPRESENTATIONS.
    # Fixed by the precommitment; no cell is added or dropped on any outcome.
    cells = [c for c in cells_all
             if all(written.get((r, c["memory_unit_locator"]), {}).get("ok")
                    for r in ("raw", "summary", "structured"))]
    log(f"cell set: {len(cells)} of {len(cells_all)} design cells have all three "
        f"representations written OK "
        f"{dict(collections.Counter(c['stratum'] for c in cells))}")
    if len(cells) != 277:
        raise SystemExit(f"expected the 277-cell matched set, got {len(cells)}")
    # The 277 assertion above is unconditional and runs BEFORE any subsetting,
    # so a smoke run still proves the real cell set is intact.
    if args.smoke_cells:
        by_st: dict[str, list] = collections.defaultdict(list)
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            by_st[c["stratum"]].append(c)
        cells = [c for st in sorted(by_st)
                 for c in by_st[st][:max(1, args.smoke_cells // 2)]]
        log(f"🔴 SMOKE RUN: subset to {len(cells)} cells "
            f"{dict(collections.Counter(c['stratum'] for c in cells))}. "
            f"NOT A RESULT -- the precommitment fixes the cell set at 277.")

    # C-JOIN: the documented trap, proven both directions -----------------
    pub_new = [json.loads(l) for l in
               (REPO / "results/repr_scaleup/cells.jsonl").read_text().splitlines() if l.strip()]
    pub_raw = [json.loads(l) for l in
               (REPO / "results/deltau_screened/cells.jsonl").read_text().splitlines() if l.strip()]

    def pub_pair(r):
        p = r.get("provenance") or {}
        loc = p.get("memory_unit_locator") or (
            r.get("source_episode_metadata") or {}).get("memory_unit_locator")
        return f"{loc}|{r['future_task_id']}"
    raw_keys = {pub_pair(r) for r in pub_raw
                if (r.get("provenance") or {}).get("stratum") in STRATA}
    sum_keys = {pub_pair(r) for r in pub_new
                if r["memory_representation"] == "summary"
                and (r.get("provenance") or {}).get("stratum") in STRATA}
    raw_mid = {r["memory_id"] for r in pub_raw
               if (r.get("provenance") or {}).get("stratum") in STRATA}
    sum_mid = {r["memory_id"] for r in pub_new if r["memory_representation"] == "summary"}
    c_join = {"n_join_on_memory_unit_locator": len(raw_keys & sum_keys),
              "n_join_on_memory_id": len(raw_mid & sum_mid),
              "_why": "memory_id is a per-representation content hash; joining on "
                      "it returns ZERO rows and would print a table of nothing."}
    log(f"  [C-JOIN] locator join {c_join['n_join_on_memory_unit_locator']} rows, "
        f"memory_id join {c_join['n_join_on_memory_id']} rows")
    if c_join["n_join_on_memory_id"] != 0:
        raise SystemExit("C-JOIN: memory_id join was expected to return 0")
    if c_join["n_join_on_memory_unit_locator"] < 277:
        raise SystemExit("C-JOIN: locator join did not recover the matched set")

    # ---- filler pool, identical to the screened run ---------------------
    fb = meta["filler"]["band"]
    max_hits = int(meta["config"]["max_pool_hits"])
    hits: dict[str, int] = collections.Counter()
    fired_by_task: dict[str, set[str]] = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if not line.strip():
            continue
        d = json.loads(line)
        hits[d["task_id"]] += 1
        fired_by_task[d["task_id"]].add(d["memory_id"])
    bearing_locs = {m for tid, ms in fired_by_task.items()
                    if tasks[tid].deterministic and 1 <= hits[tid] <= max_hits
                    for m in ms}
    fire_trajs = {uloc[m]["trajectory_id"] for m in bearing_locs}
    filler_pool: dict[str, list[dict]] = collections.defaultdict(list)
    for u in units:
        if fb[0] <= u["n_tokens"] <= fb[1] and u["trajectory_id"] not in fire_trajs:
            filler_pool[u["domain"]].append(u)
    for v in filler_pool.values():
        v.sort(key=lambda u: u["memory_unit_locator"])
    for d in sorted({c["domain"] for c in cells}):
        if len(filler_pool.get(d, [])) < args.k_filler:
            raise SystemExit(f"filler pool for {d!r} too small")
    pool_sha = S.sha256_text(json.dumps(
        {d: [u["memory_unit_locator"] for u in v] for d, v in sorted(filler_pool.items())},
        sort_keys=True))
    k2_fp = json.loads((REPO / "results/deltau_screened/cache.condition.json").read_text())
    if pool_sha != k2_fp["filler_pool_sha256"]:
        raise SystemExit("filler pool differs from the screened run's; design void")
    if S.sha256_text(SYSTEM) != k2_fp["system_prompt_sha256"]:
        raise SystemExit("system prompt differs from the screened run's")
    log("filler pool + system prompt MATCH the screened run's fingerprint")

    def select_filler(pool, *, k, task_id):
        order = sorted(pool, key=lambda u: u["memory_unit_locator"])
        random.Random(f"filler:{task_id}").shuffle(order)
        return order[:k]

    target_locs = {c["memory_unit_locator"] for c in cells}
    filler_locs = {u["memory_unit_locator"] for v in filler_pool.values() for u in v}
    if target_locs & filler_locs:
        raise SystemExit("a target memory is in the filler pool")

    def load_texts(locators: set[str]) -> dict[str, str]:
        need = {l.split(":")[0] for l in locators}
        out: dict[str, str] = {}
        for traj in lmev2.read_jsonl(args.root / "trajectories.jsonl"):
            if traj["id"] not in need:
                continue
            for pv in lmev2.segment_page_visits(traj):
                if pv.memory_unit_locator in locators:
                    out[pv.memory_unit_locator] = pv.text
            if len(out) >= len(locators):
                break
        if len(out) != len(locators):
            raise RuntimeError(f"text join matched {len(out)}/{len(locators)}; aborting")
        return out

    log(f"loading source text for {len(filler_locs | target_locs)} units ...")
    texts = load_texts(filler_locs | target_locs)

    # ---- build the memory text for every (arm, cell) --------------------
    import tiktoken  # noqa: PLC0415
    rdr_enc = tiktoken.get_encoding("o200k_harmony")

    memtext: dict[tuple[str, str], dict[str, Any]] = {}
    trunc_audit: list[dict[str, Any]] = []
    for arm in arms:
        cond, kind, fixed_budget = ARMS[arm]
        for loc in sorted(target_locs):
            full = texts[loc]
            if kind in ("raw", "summary", "structured"):
                w = written[(kind, loc)]
                txt, rule = w["memory_text"], w["prompt_version"]
                budget = None
            else:
                budget = fixed_budget if fixed_budget is not None else int(
                    written[("summary", loc)]["memory_tokens"])
                txt = truncate(full, budget, kind)
                rule = TRUNC_LAST_RULE if kind == "trunc_last" else TRUNC_FIRST_RULE
                assert_budget_exact(txt, budget, where=f"{arm}|{loc}")
                assert_budget_tight(txt, full, budget,
                                    from_end=(kind == "trunc_last"),
                                    where=f"{arm}|{loc}")
            n_off = count_tokens(txt)
            memtext[(arm, loc)] = {
                "text": txt, "rule": rule, "budget": budget,
                "tokens_official": n_off,
                "tokens_reader": len(rdr_enc.encode(txt)),
                "sha256": S.sha256_text(txt),
                "identical_to_raw": txt == full,
            }
            if kind in ("trunc_last", "trunc_first"):
                # 🔴 A cell whose WHOLE text already fits the budget was never
                # truncated, and its "shortfall" is a property of the source
                # segment, not of the truncation rule. Mixing the two makes
                # max|delta| report the longest untruncated memory (measured on
                # the 4-cell smoke run: 17,127, entirely from trunc_last_20000
                # cells that were never cut) and tells you nothing about
                # whether the rule hits its budget. The two cases are counted
                # separately, and C-TOK is evaluated on the cells that were
                # actually truncated.
                trunc_audit.append({
                    "arm": arm, "memory_unit_locator": loc, "budget": budget,
                    "achieved_official": n_off, "delta_vs_budget": n_off - budget,
                    "achieved_reader": len(rdr_enc.encode(txt)),
                    "was_truncated": bool(len(txt) < len(full)),
                    "identical_to_raw": txt == full})

    # C-AA: trunc_last_20000 must be byte-identical to raw everywhere -----
    c_aa = None
    if "trunc_last_20000" in arms and "raw" in arms:
        same = sum(1 for loc in target_locs
                   if memtext[("trunc_last_20000", loc)]["sha256"]
                   == memtext[("raw", loc)]["sha256"])
        c_aa = {"n_memories": len(target_locs), "n_byte_identical_to_raw": same}
        log(f"  [C-AA] trunc@20000 text identical to raw: {same}/{len(target_locs)}")
        if same != len(target_locs):
            raise SystemExit("C-AA: the identity arm is not identical to raw")
        # 🔴 C-AA is only a control if the two arms really issue SEPARATE
        # calls. Their rendered prompts are byte-identical by construction, so
        # if the cache key did not separate them the identity arm would be a
        # cache alias of raw and would reproduce raw's rewards TRIVIALLY --
        # a control that cannot fail. The key carries memory_repr=arm, so it
        # does separate them; that is asserted here rather than believed.
        from p1mem.cache import key_hash as _kh, make_key as _mk  # noqa: PLC0415
        _probe = {"benchmark": "longmemeval_v2", "source_item_id": "probe",
                  "memory_id": "same-content-hash", "future_task_id": "t",
                  "arm": "with_memory", "retrieval_method": "oracle",
                  "model_id": "gpt-oss-120b", "cluster": "metis",
                  "prompt_version": PROMPT_VERSION,
                  "decoding_params": {"temperature": 0.0, "max_tokens": 512},
                  "replicate_id": 0, "context_sha256": "identical-context"}
        _k_raw = _kh(_mk(**{**_probe, "memory_repr": "raw"}))
        _k_aa = _kh(_mk(**{**_probe, "memory_repr": "trunc_last_20000"}))
        c_aa["cache_keys_differ_under_identical_context"] = bool(_k_raw != _k_aa)
        log(f"  [C-AA] cache keys separate the two arms under a byte-identical "
            f"context: {_k_raw != _k_aa}")
        if _k_raw == _k_aa:
            raise SystemExit(
                "C-AA: the identity arm would share raw's cache rows, so it "
                "could not fail. Refusing to run a vacuous control.")

    # ---- jobs; POSITION IS ASSERTED EQUAL ACROSS ARMS -------------------
    jobs: list[dict[str, Any]] = []
    pos_by_cell: dict[tuple[str, str], set[int]] = collections.defaultdict(set)
    ctx_tokens: dict[str, list[int]] = collections.defaultdict(list)
    for arm in arms:
        for c in cells:
            loc = c["memory_unit_locator"]
            task = tasks[c["task_id"]]
            u = uloc[loc]
            fil = select_filler(filler_pool[u["domain"]], k=args.k_filler, task_id=task.id)
            fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                              texts[f["memory_unit_locator"]], f["n_tokens"],
                              f["domain"]) for f in fil]
            mt = memtext[(arm, loc)]
            tgt = MemoryUnit(u["memory_id"], loc, mt["text"], mt["tokens_official"],
                             u["domain"])
            # seed_parts use the MANIFEST memory_id -- never the per-arm content
            # hash -- so position is identical in every arm.
            with_ctx, pos = build_context(tgt, fus, seed_parts=(task.id, u["memory_id"]))
            without_ctx, npos = build_context(None, fus, seed_parts=(task.id, "none"))
            assert npos is None
            pos_by_cell[(loc, task.id)].add(pos)
            ctx_tokens[arm].append(count_tokens(with_ctx))
            for r in range(args.replicates):
                for sub, ctx, position in (("with_memory", with_ctx, pos),
                                           ("without_memory", without_ctx, None)):
                    jobs.append({"arm": arm, "cell": c, "unit": u, "task": task,
                                 "mt": mt, "sub": sub, "replicate_id": r,
                                 "position": position, "n_filler": len(fil),
                                 "filler_tokens": sum(f["n_tokens"] for f in fil),
                                 "messages": [
                                     {"role": "system", "content": SYSTEM},
                                     {"role": "user",
                                      "content": f"{ctx}\n\n--- Question ---\n{task.question}"}]})
    bad_pos = {k: sorted(v) for k, v in pos_by_cell.items() if len(v) != 1}
    log(f"  [C5-POSITION] cells whose target position differs across arms: {len(bad_pos)}")
    if bad_pos:
        raise SystemExit(f"C5: position varies across arms on {len(bad_pos)} cells")

    # C-PLANT #3 -- the C5 check above passed on the real data, which proves
    # nothing about whether it CAN fail. Re-seed position per arm on the real
    # cells, exactly the defect the precommitment names, and require the SAME
    # comparison to flag it. A guard verified only on its home case is not
    # known to discriminate.
    plant_pos: dict[tuple[str, str], set[int]] = collections.defaultdict(set)
    for arm in arms:
        for c in cells:
            loc, u = c["memory_unit_locator"], uloc[c["memory_unit_locator"]]
            task = tasks[c["task_id"]]
            fil = select_filler(filler_pool[u["domain"]], k=args.k_filler,
                                task_id=task.id)
            fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                              texts[f["memory_unit_locator"]], f["n_tokens"],
                              f["domain"]) for f in fil]
            mt = memtext[(arm, loc)]
            tgt = MemoryUnit(u["memory_id"], loc, mt["text"],
                             mt["tokens_official"], u["domain"])
            # THE PLANT: seed by the per-arm CONTENT HASH instead of the
            # manifest memory_id -- the exact mistake §3.2 forbids.
            _, ppos = build_context(tgt, fus, seed_parts=(task.id, mt["sha256"]))
            plant_pos[(loc, task.id)].add(ppos)
    n_plant_bad = sum(1 for v in plant_pos.values() if len(v) != 1)
    c5_plant = {"control": "P3_position_reseeded_per_arm_is_caught",
                "defect_planted": True, "guard_fired": bool(n_plant_bad > 0),
                "n_cells_flagged_when_planted": n_plant_bad,
                "n_cells_flagged_unplanted": len(bad_pos),
                "passed": bool(n_plant_bad > 0 and len(bad_pos) == 0)}
    plants.append(c5_plant)
    log(f"  [C-PLANT] P3_position_reseeded_per_arm_is_caught: "
        f"planted flags {n_plant_bad} cells, unplanted flags {len(bad_pos)} "
        f"{'PASS' if c5_plant['passed'] else 'FAIL'}")
    if not c5_plant["passed"]:
        raise SystemExit(
            "C-PLANT P3: the C5 position check did not discriminate -- it "
            "either missed a per-arm reseed or fires on the clean case")

    # C-PLANT #4 -- the memory_id trap, on THIS run's own memories rather than
    # only on the published rows. memory_id is a per-representation content
    # hash, so a join on it must return ZERO; the locator join must return all
    # 277. Both directions, because a join that matches nothing and a join
    # that matches everything look equally like "the code ran".
    _mid_raw = {memtext[("raw", c["memory_unit_locator"])]["sha256"] for c in cells}
    _mid_sum = {memtext[("summary", c["memory_unit_locator"])]["sha256"]
                for c in cells} if "summary" in arms else set()
    _loc_join = len({c["memory_unit_locator"] for c in cells}
                    & {c["memory_unit_locator"] for c in cells})
    # Expected from the cell set in hand, not a literal: a hardcoded 57 is
    # correct only for the full 277-cell set and turns any legitimate subset
    # into a spurious failure.
    _loc_expected = len({c["memory_unit_locator"] for c in cells})
    mid_plant = {"control": "P4_join_on_memory_id_returns_zero",
                 "defect_planted": True,
                 "n_rows_joining_on_memory_content_hash": len(_mid_raw & _mid_sum),
                 "n_units_joining_on_locator": _loc_join,
                 "n_units_expected": _loc_expected,
                 "guard_fired": bool(len(_mid_raw & _mid_sum) == 0),
                 "passed": bool(len(_mid_raw & _mid_sum) == 0
                                and _loc_join == _loc_expected > 0)}
    plants.append(mid_plant)
    log(f"  [C-PLANT] P4_join_on_memory_id_returns_zero: content-hash join "
        f"{len(_mid_raw & _mid_sum)} rows, locator join {_loc_join} units "
        f"{'PASS' if mid_plant['passed'] else 'FAIL'}")
    if not mid_plant["passed"]:
        raise SystemExit("C-PLANT P4: the memory_id trap did not behave as documented")

    for arm in arms:
        q = sorted(ctx_tokens[arm])
        log(f"{arm:20s} WITH-context tok  min={q[0]:6d} med={q[len(q)//2]:6d} max={q[-1]:6d}"
            f"   memory tok med="
            f"{int(np.median([memtext[(arm,l)]['tokens_official'] for l in target_locs])):6d}")
    log(f"PLANNED CALLS: {len(jobs)} (budget {args.max_calls})")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} exceeds --max-calls {args.max_calls}")

    # ---- retention: a property of the TEXT, no reader call --------------
    retention: list[dict[str, Any]] = []
    for arm in arms:
        for c in cells:
            loc = c["memory_unit_locator"]
            t = tasks[c["task_id"]]
            v = LK.detect(memtext[(arm, loc)]["text"], t.answer,
                          eval_function_spec=t.eval_function)
            retention.append({"arm": arm, "pair_key": f"{loc}|{t.id}",
                              "stratum": c["stratum"],
                              "fires": bool(v.any_leak),
                              "undecidable": bool(v.undecidable)})
    ret_tab = collections.Counter((r["arm"], r["stratum"], r["fires"]) for r in retention)
    for arm in arms:
        b = ret_tab[(arm, "BEARING", True)]
        m = ret_tab[(arm, "MATCHED_CONTROL", True)]
        log(f"  [retention] {arm:20s} BEARING {b:3d}/135   MATCHED_CONTROL {m:3d}/142")

    if args.dry_run:
        (args.out / "dry_run_plan.json").write_text(json.dumps(
            {"planned_calls": len(jobs), "arms": arms, "n_cells": len(cells),
             "c_join": c_join, "c_aa": c_aa, "plants": plants,
             "retention": ret_tab_json(ret_tab)}, indent=2))
        log("dry run: no calls issued")
        return 0

    # ---- embeddings: semantic_similarity is NON-NULLABLE ----------------
    # Measured, not assumed: schema.field_may_be_null('longmemeval_v2', f) is
    # False for embedding_model, embedding_version, memory_embedding_reference,
    # task_embedding_reference, semantic_similarity and
    # semantic_distance_band, and BENCHMARK_NULLABLE_EXEMPTIONS has no
    # longmemeval_v2 entry. An earlier draft passed None for all six; the
    # validator rejects every such row. These are reader-independent
    # properties of the memory text, so computing them changes no reader call
    # and no contrast -- it is what makes the rows writable at all.
    #
    # Each ARM gets its OWN vector: a truncated memory is different text from
    # the segment it was cut from, and reusing raw's vector would put raw's
    # similarity on a truncated row.
    log("embedding memories and tasks ...")
    emb = EmbeddingClient(cache_path=str(args.out / "embeddings.jsonl"))
    labelled: list[tuple[str, str]] = []
    for arm in arms:
        for loc in sorted(target_locs):
            labelled.append((f"{arm}|{loc}", memtext[(arm, loc)]["text"]))
    task_ids = sorted({c["task_id"] for c in cells})
    labelled += [(f"task|{t}", tasks[t].question) for t in task_ids]
    vmap, budget_used = embed_with_backoff(emb, labelled, EMBED_TOKEN_BUDGET)
    order = [k for k, _ in labelled]
    arr = np.asarray([vmap[k] for k in order], dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    store = args.out / "embeddings.npy"
    np.save(store, arr)
    emb_idx = {k: i for i, k in enumerate(order)}
    emb_sha = S.file_sha256(store)
    trunc_emb = {k: count_tokens(t) > budget_used[k] for k, t in labelled}
    log(f"embeddings {arr.shape} -> {store.name} "
        f"(truncated for embedding: {sum(trunc_emb.values())}/{len(trunc_emb)})")

    sim: dict[tuple[str, str, str], float] = {}
    for arm in arms:
        for c in cells:
            loc = c["memory_unit_locator"]
            sim[(arm, loc, c["task_id"])] = float(
                arr[emb_idx[f"{arm}|{loc}"]] @ arr[emb_idx[f"task|{c['task_id']}"]])
    # Terciles PER ARM, exactly as r2 does them per representation: a single
    # pooled cut would put most of one arm in one band, because an 8,344-token
    # trace and a 280-token slice embed differently by construction.
    cuts: dict[str, tuple[float, float]] = {}
    for arm in arms:
        vals = sorted(v for (a, _, _), v in sim.items() if a == arm)
        cuts[arm] = (vals[len(vals) // 3], vals[2 * len(vals) // 3])

    def band(arm: str, s: float) -> str:
        t1, t2 = cuts[arm]
        return "FAR" if s < t1 else ("MID" if s < t2 else "NEAR")

    # ---- C-SESSION, enforced before a single call is issued -------------
    # §5.1 is the design's first non-negotiable: gpt-oss-120b is deterministic
    # WITHIN a session and NOT across one (554/1,124 rows differed on a
    # byte-identical re-issue 24 h later). Two ways this run could silently
    # violate it, both guarded here rather than hoped against:
    #
    #   1. Running a SUBSET of arms. Then the missing arms would have to be
    #      filled from another execution, which is exactly the cross-session
    #      comparison that voided the published Raw-vs-Summary contrast.
    #   2. Resuming onto a cache written EARLIER. A cache hit returns the
    #      earlier session's text, so a "resumed" run is a blend of sessions
    #      wearing one run_id -- and it would look like a fast, clean run.
    #
    # The second is the dangerous one, because it presents as success.
    if set(arms) != set(ARMS) and not args.smoke_cells:
        raise SystemExit(
            f"C-SESSION: all eight arms must execute in ONE session; got "
            f"{sorted(arms)}. Running a subset means the rest come from a "
            f"different session and the whole comparison is void (§5.1).")
    cache_path = args.out / "eval_cache.jsonl"
    n_preexisting = (sum(1 for _ in cache_path.open()) if cache_path.exists() else 0)
    if n_preexisting and not args.resume_cache:
        raise SystemExit(
            f"C-SESSION: {cache_path} already holds {n_preexisting} responses "
            f"from an EARLIER execution. Serving them would mix sessions "
            f"invisibly. Point --out at a fresh directory, or pass "
            f"--resume-cache if the cache provably belongs to this session.")
    cache = ResponseCache(cache_path)
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                      max_concurrency=args.workers)
    results: dict[tuple, dict] = {}
    n_real = n_cached = n_err = 0
    t0 = time.monotonic()
    session_start = utc_now()

    def run_one(j):
        kf = {"benchmark": "longmemeval_v2",
              "source_item_id": j["unit"]["trajectory_id"],
              "memory_repr": j["arm"],
              "memory_id": j["mt"]["sha256"],
              "future_task_id": j["task"].id, "arm": j["sub"],
              "retrieval_method": "oracle", "prompt_version": PROMPT_VERSION,
              "replicate_id": j["replicate_id"]}
        try:
            c, rec = client.chat(j["messages"], max_tokens=args.max_tokens,
                                 temperature=0.0, reasoning_effort="low",
                                 cache_key_fields=kf)
            return j, c, rec, None
        except ClientError as e:
            return j, None, None, f"{type(e).__name__}: {e}"

    log(f"executing {len(jobs)} calls at concurrency {args.workers} IN ONE SESSION ...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            j, content, rec, err = fut.result()
            k = (j["arm"], j["unit"]["memory_unit_locator"], j["task"].id,
                 j["replicate_id"], j["sub"])
            if err is not None:
                n_err += 1
                results[k] = {"error": err, "job": j}
            else:
                if rec.cache_hit:
                    n_cached += 1
                else:
                    n_real += 1
                results[k] = {"content": content, "rec": rec, "job": j}
            if n % 500 == 0:
                el = time.monotonic() - t0
                log(f"  {n}/{len(jobs)} (real={n_real} cached={n_cached} err={n_err}) "
                    f"{n/el*60:.0f}/min")
    wall = time.monotonic() - t0
    session_end = utc_now()
    log(f"execution done in {wall:.1f}s: real={n_real} cached={n_cached} err={n_err}")

    # ---- C-WITHOUT: the free cross-arm control (§6) ----------------------
    # The WITHOUT arm's context is K=4 filler and no target, so its BYTES are
    # identical in all eight arms -- but it is re-generated per arm
    # (Amendment A1.4) rather than reused. If eight independent generations
    # come back byte-identical, that is a MEASURED demonstration that the
    # reader is deterministic in-session and that the arms differ only in the
    # target. Reusing one answer would have made that agreement true by
    # construction, i.e. unfalsifiable.
    without_agree = {"n_cells_compared": 0, "n_all_arms_identical": 0,
                     "n_disagreeing": 0, "examples": []}
    if len(arms) > 1:
        for c in cells:
            loc, tid = c["memory_unit_locator"], c["task_id"]
            for r in range(args.replicates):
                outs = []
                for a in arms:
                    got = results.get((a, loc, tid, r, "without_memory"), {})
                    if got.get("content") is not None:
                        outs.append(got["content"])
                if len(outs) < 2:
                    continue
                without_agree["n_cells_compared"] += 1
                if len(set(outs)) == 1:
                    without_agree["n_all_arms_identical"] += 1
                else:
                    without_agree["n_disagreeing"] += 1
                    if len(without_agree["examples"]) < 5:
                        without_agree["examples"].append(
                            {"pair_key": f"{loc}|{tid}", "replicate_id": r,
                             "n_distinct_outputs": len(set(outs))})
        log(f"  [C-WITHOUT] byte-identical across arms: "
            f"{without_agree['n_all_arms_identical']}/"
            f"{without_agree['n_cells_compared']} "
            f"(disagreeing {without_agree['n_disagreeing']})")

    # ---- score + write ---------------------------------------------------
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown)

    rows_path = args.out / "cells.jsonl"
    if rows_path.exists():
        rows_path.unlink()
    w = CellWriter(rows_path, strict=True)
    n_written = 0
    n_null_reward = 0
    for arm in arms:
        cond, kind, _ = ARMS[arm]
        for c in cells:
            loc = c["memory_unit_locator"]
            task = tasks[c["task_id"]]
            u = uloc[loc]
            mt = memtext[(arm, loc)]
            leak = LK.detect(mt["text"], task.answer, memory_id=mt["sha256"],
                             task_id=task.id, eval_function_spec=task.eval_function)
            src = written.get((kind, loc)) if kind in ("raw", "summary", "structured") else None
            for r in range(args.replicates):
                rw = results.get((arm, loc, task.id, r, "with_memory"), {})
                ro = results.get((arm, loc, task.id, r, "without_memory"), {})
                errs = [x.get("error") for x in (rw, ro) if x.get("error")]
                ow, oo = rw.get("content"), ro.get("content")
                if errs or ow is None or oo is None:
                    # reward None means COULD NOT BE SCORED. Never 0.0.
                    reward_w = reward_o = delta = None
                    joined = " | ".join(errs)
                    code = (S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH
                            if "TruncatedResponseError" in joined else "http_error")
                    unk_w = unk_o = None
                    n_null_reward += 1
                else:
                    pw, po = extract_boxed_answer(ow), extract_boxed_answer(oo)
                    unk_w, unk_o = is_unknown(pw), is_unknown(po)
                    reward_w = 0.0 if unk_w else float(task.score(pw))
                    reward_o = 0.0 if unk_o else float(task.score(po))
                    delta = reward_w - reward_o
                    code = None
                recs = [x["rec"] for x in (rw, ro) if x.get("rec") is not None]
                rt = [x.reasoning_tokens for x in recs if x.reasoning_tokens is not None]
                job = (rw or ro).get("job", {})
                row = w.build(
                    benchmark="longmemeval_v2",
                    benchmark_version=lmev2.UPSTREAM_COMMIT,
                    source_episode_id=u["trajectory_id"],
                    source_episode_metadata={
                        "domain": u["domain"], "environment": u["environment"],
                        "outcome": u["outcome"], "url": u["url"],
                        "memory_unit_locator": loc},
                    # 🔴 memory_representation is a CLOSED ENUM
                    # (schema.MEMORY_REPRESENTATIONS = raw|summary|structured)
                    # and it answers "HOW is this memory written down", not
                    # "which arm is this". An earlier draft passed the arm name
                    # here; measured, that makes the validator reject EVERY row
                    # of the five new arms with bad_enum, so the run would have
                    # produced nothing.
                    #
                    # A positional slice of the source segment IS written down
                    # raw -- verbatim extractive text, zero writer calls,
                    # memory_writer_model='none:deterministic_span'. What
                    # differs between the truncated arms is the BUDGET, and the
                    # budget is carried in fields built to carry it:
                    #   condition_id            -- distinct per arm (§3)
                    #   provenance.arm          -- the arm name
                    #   provenance.length_budget
                    #   memory_source_span.derived_from / span_rule_version
                    # so the arms stay separately addressable. CELL_ID_KEYS
                    # includes condition_id and MEMORY_ID_KEYS includes
                    # memory_text AND memory_writer_prompt_version (the rule
                    # version string), so cell_id and memory_id differ across
                    # arms too -- including for trunc_last_20000, whose TEXT is
                    # byte-identical to raw but whose rule version is not. That
                    # is what keeps C-AA a genuinely separate set of calls
                    # rather than a cache alias. Asserted below, not assumed.
                    memory_representation=REPR_OF_ARM[arm],
                    memory_semantic_type=((src or {}).get("native_semantic_type")
                                          or "episodic"),
                    memory_text=mt["text"], memory_tokens=mt["tokens_official"],
                    memory_source_span={
                        "trajectory_id": u["trajectory_id"],
                        "start_state_index": u["start_state_index"],
                        "end_state_index": u["end_state_index"],
                        "n_states": u["n_states"],
                        "memory_unit_locator": loc,
                        "derived_from": ("whole_segment" if mt["budget"] is None
                                         else f"positional_slice@{mt['budget']}tok"),
                        "span_rule_version": mt["rule"],
                        "text_sha256": mt["sha256"]},
                    # A truncated memory costs ZERO model calls, like raw. The
                    # sentinel is the schema's, not an invented value.
                    memory_writer_model=((src or {}).get("writer_model")
                                         or "none:deterministic_span"),
                    memory_writer_cluster=((src or {}).get("writer_cluster")
                                           or "none:deterministic_span"),
                    memory_writer_prompt_version=mt["rule"],
                    memory_extraction_latency=(src or {}).get("extraction_latency_s"),
                    memory_extraction_input_tokens=(src or {}).get("extraction_input_tokens"),
                    memory_extraction_output_tokens=(src or {}).get("extraction_output_tokens"),
                    embedding_model=EMBED_MODEL,
                    embedding_version=f"sophia_vllm_dim{EMBED_DIM}",
                    memory_embedding_reference={
                        "store": "embeddings.npy", "index": emb_idx[f"{arm}|{loc}"],
                        "dim": EMBED_DIM, "sha256": emb_sha,
                        "input_truncated": trunc_emb[f"{arm}|{loc}"],
                        "input_token_budget": budget_used[f"{arm}|{loc}"]},
                    future_task_id=task.id, future_task_family=task.question_type,
                    future_task_text=task.question,
                    task_embedding_reference={
                        "store": "embeddings.npy",
                        "index": emb_idx[f"task|{task.id}"],
                        "dim": EMBED_DIM, "sha256": emb_sha, "input_truncated": False,
                        "input_token_budget": budget_used[f"task|{task.id}"]},
                    semantic_similarity=sim[(arm, loc, task.id)],
                    semantic_distance_band=band(arm, sim[(arm, loc, task.id)]),
                    retrieval_method="oracle", retrieval_rank=None, retrieval_k=None,
                    memory_tokens_retrieved=mt["tokens_official"],
                    memory_tokens_exposed=mt["tokens_official"],
                    replicate_id=r,
                    seed_or_sampling_config={"temperature": 0.0,
                                             "max_tokens": args.max_tokens,
                                             "reasoning_effort": "low", "seed": None},
                    reader_model="gpt-oss-120b", reader_cluster="metis",
                    reader_endpoint="metis:/resource_server/metis/api/v1",
                    reader_prompt_version=PROMPT_VERSION,
                    reader_endpoint_sha256=S.sanitized_base_url_hash(
                        "https://inference-api.alcf.anl.gov/resource_server/metis/api/v1"),
                    reader_reasoning_effort="low", condition_id=cond,
                    output_without_memory=oo, output_with_memory=ow,
                    reward_without_memory=reward_o, reward_with_memory=reward_w,
                    delta_utility=delta, robustness_confidence=None,
                    write_latency=(src or {}).get("extraction_latency_s"),
                    retrieval_latency=None,
                    generation_latency=round(sum(x.latency_s for x in recs), 4),
                    end_to_end_latency=round(sum(x.latency_s for x in recs), 4),
                    embedding_calls=0, generation_calls=len(recs),
                    input_tokens=sum(x.input_tokens for x in recs),
                    output_tokens=sum(x.output_tokens for x in recs),
                    reasoning_tokens=sum(rt) if rt else None,
                    retry_count=sum(x.retry_count for x in recs),
                    error_code_if_any=code,
                    provenance={
                        "code_sha": CODE_SHA, "run_id": RUN_ID, "host": "laptop",
                        "writer": "scripts/len1_build_length_control.py",
                        "arm": arm,
                        "target_position": job.get("position"),
                        "n_filler": job.get("n_filler"),
                        "filler_tokens": job.get("filler_tokens"),
                        "prompt_arm": "handwritten",
                        "system_prompt_sha256": S.sha256_text(SYSTEM),
                        "stratum": c["stratum"], "why_stratum": c["why_stratum"],
                        "detector_fires": c["detector_fires"],
                        "task_pool_hits": c["task_pool_hits"],
                        "task_pool_size": c["task_pool_size"],
                        "n_bearing_tasks_for_this_memory":
                            c["n_bearing_tasks_for_this_memory"],
                        "is_unknown_with": unk_w, "is_unknown_without": unk_o,
                        "memory_unit_locator": loc,
                        "pair_key": f"{loc}|{task.id}",
                        # length-control specific
                        "length_budget": mt["budget"],
                        "span_rule_version": mt["rule"],
                        "memory_tokens_official": mt["tokens_official"],
                        "memory_tokens_reader_o200k": mt["tokens_reader"],
                        "memory_text_sha256": mt["sha256"],
                        "identical_to_raw_text": mt["identical_to_raw"],
                        "bearing_content_retained": bool(leak.any_leak),
                        "session_start_utc": session_start,
                    },
                    license_source_reference="longmemeval_v2:Apache-2.0",
                    verifier_id=task.eval_name,
                    verifier_version=f"vendored@{lmev2.VENDORED_SCORER_SHA256[:12]}",
                    reward_is_continuous=False,
                    leakage_flag=(bool(leak.any_leak) if not leak.undecidable else None),
                )
                w.write_row(row)
                n_written += 1
    log(f"wrote {n_written} rows -> {rows_path.name} ({w.close()})")

    ledger = {
        "_what": "LEN1 length-controlled representation test. All arms in ONE session.",
        "precommitment": "docs/LENGTH_CONTROL_PRECOMMITMENT.md",
        "is_smoke_run_not_a_result": bool(args.smoke_cells),
        "smoke_cells": args.smoke_cells or None,
        "run_at_utc": utc_now(), "run_id": RUN_ID, "code_sha": CODE_SHA,
        "session_start_utc": session_start, "session_end_utc": session_end,
        "wall_clock_s": round(wall, 2),
        "_session_note": "defect #25: gpt-oss-120b is deterministic WITHIN a session "
                         "and not across one. Every arm -- including raw and summary, "
                         "which have published numbers -- was re-executed here.",
        "arms": {a: {"condition_id": ARMS[a][0], "kind": ARMS[a][1],
                     "budget": ARMS[a][2]} for a in arms},
        "n_cells": len(cells),
        "n_strata": dict(collections.Counter(c["stratum"] for c in cells)),
        "replicates": args.replicates,
        "planned_calls": len(jobs), "real_endpoint_calls": n_real,
        "cache_hits": n_cached, "errors": n_err, "rows_written": n_written,
        # C-SESSION evidence: an empty pre-existing cache plus zero in-run
        # cache hits means every row came from THIS process. A nonzero value
        # here would mean some arm was served from another session.
        "n_preexisting_cache_rows": n_preexisting,
        "all_arms_executed_in_one_session": bool(
            n_preexisting == 0 and n_cached == 0 and set(arms) == set(ARMS)),
        "n_rows_with_null_reward": n_null_reward,
        "tokenizer": tokenizer_provenance(),
        "reader_tokenizer": "o200k_harmony",
        "filler_pool_sha256": pool_sha,
        "controls": {
            "C_PLANT": plants,
            "C_WITHOUT_cross_arm_identity": without_agree,
            "C_JOIN": c_join,
            "C_AA_text_identity": c_aa,
            "C5_position_equal_across_arms": {"n_cells_with_differing_position": len(bad_pos)},
            "leakage_detector_selftest": {"n_pass": sum(c.passed for c in ctrl),
                                          "n_total": len(ctrl)},
        },
        "truncation_audit": {
            "_what": "C-TOK. A cell whose whole text already fits the budget "
                     "was NEVER TRUNCATED; its shortfall is a property of the "
                     "source segment, not of the rule, so it is counted "
                     "separately. max_abs_delta is over the CUT cells only.",
            "n_slices_built": len(trunc_audit),
            "n_actually_truncated": sum(1 for t in trunc_audit if t["was_truncated"]),
            "n_whole_text_already_fit": sum(1 for t in trunc_audit
                                            if not t["was_truncated"]),
            "max_abs_delta_vs_budget_official": (
                max((abs(t["delta_vs_budget"]) for t in trunc_audit
                     if t["was_truncated"]), default=None)),
            "n_exact": sum(1 for t in trunc_audit
                           if t["was_truncated"] and t["delta_vs_budget"] == 0),
            "delta_histogram_cut_cells": dict(sorted(collections.Counter(
                t["delta_vs_budget"] for t in trunc_audit
                if t["was_truncated"]).items())),
            # kept under the old name so a reader of either ledger sees the
            # same count mean the same thing
            "n_truncated_memories": sum(1 for t in trunc_audit if t["was_truncated"]),
        },
        # §2.4: the budget is DEFINED in the official tokenizer but CONSUMED by
        # the reader, so the reader-tokenizer count is recorded per locator and
        # the trunc-vs-summary difference is auditable in the tokenizer that
        # actually reads the text.
        "reader_tokens_summary_by_locator": (
            {l: memtext[("summary", l)]["tokens_reader"] for l in sorted(target_locs)}
            if "summary" in arms else {}),
        "retention_by_arm": ret_tab_json(ret_tab),
        "context_tokens_with_arm": {
            a: {"min": sorted(ctx_tokens[a])[0],
                "median": sorted(ctx_tokens[a])[len(ctx_tokens[a]) // 2],
                "max": sorted(ctx_tokens[a])[-1]} for a in arms},
        "memory_tokens_by_arm": {
            a: {"median_official": float(np.median(
                    [memtext[(a, l)]["tokens_official"] for l in target_locs])),
                "median_reader_o200k": float(np.median(
                    [memtext[(a, l)]["tokens_reader"] for l in target_locs]))}
            for a in arms},
    }
    ledger_path = (args.out / "length_control_run_SMOKE.json" if args.smoke_cells
                   else REPO / "results/ledgers/length_control_run.json")
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True))
    (args.out / "truncation_audit.json").write_text(
        json.dumps(trunc_audit, indent=2, sort_keys=True))
    log(f"ledger -> {ledger_path.name}")
    return 0


def ret_tab_json(ret_tab) -> dict:
    out: dict[str, dict[str, int]] = {}
    for (arm, strat, fires), n in ret_tab.items():
        out.setdefault(arm, {})[f"{strat}_{'fires' if fires else 'silent'}"] = n
    return out


CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
RUN_ID = f"len1_{utc_now().replace(':', '').replace('-', '')}"

if __name__ == "__main__":
    raise SystemExit(main())
