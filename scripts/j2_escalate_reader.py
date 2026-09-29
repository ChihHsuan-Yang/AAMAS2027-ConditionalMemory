#!/usr/bin/env python3
"""J2: re-issue the SAME cells under STRONGER readers, as NEW ARMS.

Decides READER vs TASK. Everything except the reader configuration is held
byte-identical to the two completed arms: same cells, same filler, same target
position, same system prompt, same question. The context is not re-derived by
hand -- it is rebuilt by IMPORTING ``scripts/run_deltau_pilot.py``'s own
``sample_memories`` / ``select_filler`` / ``render_text`` / ``load_texts`` and
driving them with the same seed, then ASSERTED byte-identical against the
prompt the completed run actually sent (recovered from its cache row's
prompt_tokens and, where recoverable, the row's own memory_text). A
hand-rewritten prompt would make this a different experiment wearing the same
name.

NEW ARMS, never backfills: ``reader_model``, ``reader_reasoning_effort`` and
``max_tokens`` are pinned experimental identity and enter ``condition_id`` and
the cache key. Nothing is written into the existing arms' artifacts.

Design
------
Two cell groups, both fixed BEFORE any call:
  ORACLE  -- the DISCRIMINATIVE oracle-bearing subgroup (j1b): the memory
             literally carries the gold answer AND the detector singles this
             memory out among the same-domain pool. Content-defined, not
             outcome-selected.
  CONTROL -- a matched random sample of NON-flagged cells, stratified to the
             same (domain, question_type) mix. Without it "accuracy went up"
             cannot be told apart from "these cells are easier".

Reader configurations (each a separate arm):
  base     gpt-oss-120b / metis / effort=low  / 512   -- REPLICATION of the
           completed official arm, re-issued now. If this does not reproduce
           the recorded rewards, the comparison is void and the run says so.
  high     gpt-oss-120b / metis / effort=high / 2048
  strong   a different model, probed live before use.

POSITIVE CONTROL: a trivially-easy item is sent through the SAME scoring path
in every configuration. If a configuration reports no gain, the positive
control proves the harness could have detected one.

Writes: results/j2_escalation/{responses.jsonl,summary.json}. Does not touch
results/deltau_official or results/deltau_pilot.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem import schema as S  # noqa: E402
from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.analysis.common import wilson_ci  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.cells import SYSTEM, official_system_prompt  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402


def _load_runner():
    """Import the ORIGINAL runner so the context is built by the same code."""
    spec = importlib.util.spec_from_file_location(
        "p1_run_deltau_pilot", REPO / "scripts/run_deltau_pilot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


# ---- reader configurations. Each is a NEW ARM with its own identity.
CONFIGS: dict[str, dict[str, Any]] = {
    "base_replication": {
        "cluster": "metis", "model": "gpt-oss-120b",
        "reasoning_effort": "low", "max_tokens": 512,
        "condition_id": "lmev2_raw_metis_gptoss120b_officialprompt_v1",
        "_note": "byte-identical to the completed official arm; a REPLICATION "
                 "check, and the anchor the other configs are compared against",
    },
    "high_effort": {
        "cluster": "metis", "model": "gpt-oss-120b",
        "reasoning_effort": "high", "max_tokens": 2048,
        "condition_id": "lmev2_raw_metis_gptoss120b_officialprompt_hi2048_v1",
    },
    "nemotron": {
        "cluster": "minerva", "model": "nemotron-3-ultra",
        "reasoning_effort": "high", "max_tokens": 2048,
        "condition_id": "lmev2_raw_minerva_nemotron3ultra_officialprompt_hi2048_v1",
    },
    "inkling": {
        "cluster": "minerva", "model": "inkling-bf16",
        "reasoning_effort": "high", "max_tokens": 2048,
        "condition_id": "lmev2_raw_minerva_inklingbf16_officialprompt_hi2048_v1",
    },
}

#: A trivially easy item, scored through the SAME path as every real cell.
#: If an arm reports no gain, this proves the harness can register a 1.
POSCTRL = {
    "task_id": "__posctrl_trivial__",
    "question": "What is the capital city of France? Put the final answer in \\boxed{}.",
    "answer": "Paris",
    "eval_function": "norm_phrase_set_match|lower=true|normalize_hyphen=true"
                     "|strip_punct=true|separators=,;|require_non_empty=true",
    "domain": "web",
}


def build_all_contexts(root: Path, seed: int, k_filler: int,
                       tok_lo: int, tok_hi: int, filler_trajs: int,
                       prompt_arm: str):
    """Rebuild every (memory, task) context using the ORIGINAL runner's code."""
    R = _load_runner()
    units = [json.loads(l) for l in
             open(REPO / "data/manifests/lmev2_memory_units_small.jsonl")]
    pairs = [json.loads(l) for l in
             open(REPO / "data/manifests/lmev2_pairs_small_seed20261008.jsonl")]
    tasks = {t.id: t for t in lmev2.load_tasks(root)}
    targets, filler_pool = R.sample_memories(
        units, n=60, lo=tok_lo, hi=tok_hi, n_filler_trajs=filler_trajs, seed=seed)
    tgt_ids = {u["memory_id"] for u in targets}
    by_mem = collections.defaultdict(list)
    for p in pairs:
        if p["memory_id"] in tgt_ids:
            by_mem[p["memory_id"]].append(p)
    cell_specs = [(u, p) for u in targets
                  for p in sorted(by_mem[u["memory_id"]], key=lambda p: p["task_id"])]
    locators = {u["memory_unit_locator"] for u in targets}
    locators |= {u["memory_unit_locator"] for v in filler_pool.values() for u in v}
    log(f"loading text for {len(locators)} units from trajectories.jsonl ...")
    texts = R.load_texts(root, locators)
    log(f"loaded {len(texts)} unit texts; {len(cell_specs)} cell specs")

    out: dict[tuple[str, str], dict] = {}
    for u, p in cell_specs:
        task = tasks[p["task_id"]]
        fil = R.select_filler(filler_pool[u["domain"]], k=k_filler, task_id=task.id)
        with_ctx, pos = R.render_text(fil, texts, u, task_id=task.id)
        without_ctx, npos = R.render_text(fil, texts, None, task_id=task.id)
        assert npos is None
        sys_prompt = (SYSTEM if prompt_arm == "handwritten"
                      else official_system_prompt(task.domain))
        out[(u["memory_unit_locator"], task.id)] = {
            "unit": u, "task": task, "position": pos,
            "manifest_memory_id": u["memory_id"],
            "system": sys_prompt,
            "user_with": f"{with_ctx}\n\n--- Question ---\n{task.question}",
            "user_without": f"{without_ctx}\n\n--- Question ---\n{task.question}",
            "memory_text": texts[u["memory_unit_locator"]],
        }
    return out


def pick_cells(rows_path: Path, root: Path, max_pool_hits: int,
               n_control: int, seed: int):
    """ORACLE (discriminative, content-defined) + a matched random CONTROL."""
    tasks = {t.id: t for t in lmev2.load_tasks(root)}
    rows = load_jsonl(rows_path)
    cells = collections.defaultdict(list)
    for r in rows:
        if not r.get("error_code_if_any"):
            cells[(r["memory_id"], r["future_task_id"])].append(r)
    memtext, memdom, loc_of = {}, {}, {}
    for k, v in cells.items():
        memtext[v[0]["memory_id"]] = v[0]["memory_text"]
        memdom[v[0]["memory_id"]] = v[0]["source_episode_metadata"]["domain"]
        loc_of[v[0]["memory_id"]] = v[0]["source_episode_metadata"]["memory_unit_locator"]
    taskdom = {v[0]["future_task_id"]: v[0]["source_episode_metadata"]["domain"]
               for v in cells.values()}
    fired = {}
    for tid in {k[1] for k in cells}:
        t = tasks[tid]
        fired[tid] = {m: bool(LK.detect(memtext[m], t.answer,
                                        eval_function_spec=t.eval_function).any_leak)
                      for m in memtext if memdom[m] == taskdom[tid]}
    flagged = [k for k in cells if fired[k[1]][k[0]]]
    pool_hits = {k: sum(fired[k[1]].values()) for k in flagged}
    oracle = sorted(k for k in flagged if pool_hits[k] <= max_pool_hits)

    # matched control: same (domain, question_type) mix, drawn from NON-flagged
    want = collections.Counter(
        (taskdom[k[1]], tasks[k[1]].question_type) for k in oracle)
    scale = n_control / max(len(oracle), 1)
    nonflag = collections.defaultdict(list)
    for k in cells:
        if not fired[k[1]][k[0]]:
            nonflag[(taskdom[k[1]], tasks[k[1]].question_type)].append(k)
    rng = random.Random(f"j2_control:{seed}")
    control: list[tuple[str, str]] = []
    for stratum, cnt in sorted(want.items()):
        pool = sorted(nonflag.get(stratum, []))
        take = min(len(pool), max(1, round(cnt * scale)))
        rng.shuffle(pool)
        control.extend(pool[:take])
    # top up from the global non-flagged pool if strata ran short
    rest = sorted({k for v in nonflag.values() for k in v} - set(control))
    rng.shuffle(rest)
    while len(control) < n_control and rest:
        control.append(rest.pop())
    control = sorted(set(control))[:n_control]
    return oracle, control, cells, tasks, loc_of


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--rows", type=Path,
                    default=REPO / "results/deltau_official/cells.jsonl")
    ap.add_argument("--out", type=Path, default=REPO / "results/j2_escalation")
    ap.add_argument("--configs", default="base_replication,high_effort,nemotron")
    ap.add_argument("--max-pool-hits", type=int, default=8)
    ap.add_argument("--n-control", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--k-filler", type=int, default=6)
    ap.add_argument("--tok-lo", type=int, default=1500)
    ap.add_argument("--tok-hi", type=int, default=5000)
    ap.add_argument("--filler-trajs", type=int, default=12)
    ap.add_argument("--prompt-arm", default="official")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-calls", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    cfg_names = [c.strip() for c in args.configs.split(",") if c.strip()]
    for c in cfg_names:
        if c not in CONFIGS:
            raise SystemExit(f"unknown config {c!r}; known {sorted(CONFIGS)}")

    oracle, control, cells, tasks, loc_of = pick_cells(
        args.rows, args.root, args.max_pool_hits, args.n_control, args.seed)
    log(f"ORACLE (discriminative, <= {args.max_pool_hits} pool hits): {len(oracle)} cells")
    log(f"CONTROL (matched random, non-flagged):                      {len(control)} cells")
    overlap = set(oracle) & set(control)
    assert not overlap, f"oracle and control overlap: {overlap}"

    ctxs = build_all_contexts(args.root, args.seed, args.k_filler,
                              args.tok_lo, args.tok_hi, args.filler_trajs,
                              args.prompt_arm)

    # ---- ASSERT the rebuilt context IS what the completed run sent.
    #
    # Three clauses, each negative-controlled (see J report 4b):
    #
    #  (1) the target memory_text is byte-equal to the row's, present in the
    #      WITH context and ABSENT from the WITHOUT context;
    #  (2) the per-cell WITH-context token count, counted with the OFFICIAL
    #      tokenizer, reproduces the quantiles the completed run recorded in
    #      its own summary.json. Clause (1) alone is NOT sufficient: rebuilding
    #      with K=4 filler instead of K=6 passes it (the target is still
    #      there, only the fillers differ), which would silently make this a
    #      different experiment wearing the same name. Clause (2) covers every
    #      filler byte.
    #  (3) the server-counted prompt_tokens in the completed run's cache must
    #      track our count by a CONSTANT tokenizer ratio. The server does not
    #      use the official Qwen tokenizer -- measured ratio 1.15-1.21 over all
    #      960 prompts -- so an absolute match is the WRONG test and would have
    #      rejected a perfectly faithful rebuild. A ratio that is stable across
    #      cells but wrong for one cell is the signal that matters.
    from p1mem.memory.tokens import count_tokens  # noqa: PLC0415

    nchk = 0
    ctx_of: dict[tuple[str, str], dict] = {}
    for k in list(oracle) + list(control):
        ck = (loc_of[k[0]], k[1])
        if ck not in ctxs:
            raise SystemExit(
                f"cell {k} (locator {ck[0]}) not reproducible from seed {args.seed}")
        recorded = cells[k][0]["memory_text"]
        c = ctxs[ck]
        ctx_of[k] = c
        if c["memory_text"] != recorded:
            raise SystemExit(
                f"rebuilt memory_text != recorded for {k}: "
                f"{len(c['memory_text'])} vs {len(recorded)} chars")
        if recorded not in c["user_with"]:
            raise SystemExit(f"rebuilt WITH context does not contain the memory for {k}")
        if recorded in c["user_without"]:
            raise SystemExit(f"rebuilt WITHOUT context CONTAINS the memory for {k}")
        nchk += 1

    # clause (2): reproduce the completed run's OWN recorded quantiles, with
    # the same tokenizer and over the same quantity (context body only, no
    # system prompt, no question -- that is what run_deltau_pilot.py counted).
    recorded_q = json.loads(
        (args.rows.parent / "summary.json").read_text())["context_tokens_with_arm"]
    body_toks = sorted(
        count_tokens(c["user_with"].rsplit("\n\n--- Question ---\n", 1)[0])
        for c in ctxs.values())
    ours_q = {"min": body_toks[0], "p25": body_toks[len(body_toks) // 4],
              "median": body_toks[len(body_toks) // 2],
              "p75": body_toks[3 * len(body_toks) // 4], "max": body_toks[-1]}
    if ours_q != recorded_q:
        raise SystemExit(
            f"WITH-context token quantiles do not reproduce the completed run: "
            f"rebuilt {ours_q} vs recorded {recorded_q}. The filler composition "
            f"differs -- refusing to spend calls on a different experiment.")
    log(f"context token quantiles reproduce the completed run exactly: {ours_q}")

    # clause (3): constant tokenizer ratio against the server's own counts
    completed_cache: dict[tuple, int] = {}
    cpath = args.rows.parent / "cache.jsonl"
    for line in open(cpath):
        rec = json.loads(line)
        kk = rec["key"]
        completed_cache[(kk["memory_id"], kk["future_task_id"], kk["arm"],
                         kk["replicate_id"])] = rec["response"]["prompt_tokens"]
    ratios = []
    for k in list(oracle) + list(control):
        c = ctx_of[k]
        for arm, user in (("with_memory", c["user_with"]),
                          ("without_memory", c["user_without"])):
            rec_tok = completed_cache.get((c["manifest_memory_id"], k[1], arm, 0))
            if rec_tok is None:
                raise SystemExit(
                    f"no recorded prompt_tokens for {k} {arm}; refusing to spend "
                    f"calls on an unverified context")
            ratios.append((count_tokens(c["system"]) + count_tokens(user)) / rec_tok)
    rlo, rhi = min(ratios), max(ratios)
    if not (1.05 <= rlo and rhi <= 1.35):
        raise SystemExit(
            f"qwen/server token ratio out of the measured band: [{rlo:.4f},{rhi:.4f}]")
    log(f"context reproduction ASSERTED for {nchk} cells; qwen/server token ratio "
        f"[{rlo:.4f},{rhi:.4f}] over {len(ratios)} prompts")

    # ---- build every job up front so the call count is known before spending
    jobs: list[dict] = []
    for cname in cfg_names:
        cfg = CONFIGS[cname]
        for group, keys in (("oracle", oracle), ("control", control)):
            for k in keys:
                c = ctx_of[k]
                for arm, user in (("with_memory", c["user_with"]),
                                  ("without_memory", c["user_without"])):
                    jobs.append({
                        "config": cname, "group": group, "arm": arm,
                        "memory_id": k[0], "task_id": k[1],
                        "trajectory_id": c["unit"]["trajectory_id"],
                        "position": c["position"],
                        "messages": [{"role": "system", "content": c["system"]},
                                     {"role": "user", "content": user}],
                    })
        # positive control: one trivially-easy item per config, same scoring path
        jobs.append({
            "config": cname, "group": "positive_control", "arm": "with_memory",
            "memory_id": "__posctrl__", "task_id": POSCTRL["task_id"],
            "trajectory_id": "__posctrl__", "position": None,
            "messages": [{"role": "system",
                          "content": official_system_prompt(POSCTRL["domain"])},
                         {"role": "user", "content": POSCTRL["question"]}],
        })

    log(f"PLANNED CALLS: {len(jobs)} (budget {args.max_calls}) over configs {cfg_names}")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} > --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        write_json_atomic(args.out / "plan.json", {
            "planned_calls": len(jobs), "configs": cfg_names,
            "n_oracle": len(oracle), "n_control": len(control),
            "oracle_cells": [list(k) for k in oracle],
            "control_cells": [list(k) for k in control],
        })
        return 0

    cache = ResponseCache(args.out / "cache.jsonl")
    clients = {c: P1Client(cluster=CONFIGS[c]["cluster"], model=CONFIGS[c]["model"],
                           cache=cache, max_concurrency=args.workers)
               for c in cfg_names}

    def run_one(j: dict):
        cfg = CONFIGS[j["config"]]
        kf = {
            "benchmark": "longmemeval_v2",
            "source_item_id": j["trajectory_id"],
            "memory_repr": "raw",
            "memory_id": j["memory_id"],
            "future_task_id": j["task_id"],
            "arm": j["arm"],
            "retrieval_method": "oracle",
            # the arm's identity is IN the cache key, so no config can hit
            # another's row
            "prompt_version": f"p1_deltau_raw_official_v1|j2:{j['config']}",
            "replicate_id": 0,
        }
        try:
            c, rec = clients[j["config"]].chat(
                j["messages"], max_tokens=cfg["max_tokens"], temperature=0.0,
                reasoning_effort=cfg["reasoning_effort"], cache_key_fields=kf)
            return j, c, rec, None
        except ClientError as e:
            return j, None, None, f"{type(e).__name__}: {e}"

    log(f"executing {len(jobs)} calls at concurrency {args.workers} ...")
    t0 = time.monotonic()
    out_rows, n_err, n_real, n_cached = [], 0, 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            j, content, rec, err = fut.result()
            row = {"config": j["config"], "group": j["group"], "arm": j["arm"],
                   "memory_id": j["memory_id"], "task_id": j["task_id"],
                   "position": j["position"]}
            if err:
                n_err += 1
                row.update({"error": err, "content": None})
            else:
                if rec.cache_hit:
                    n_cached += 1
                else:
                    n_real += 1
                row.update({
                    "content": content, "error": None,
                    "finish_reason": rec.finish_reason,
                    "prompt_tokens": rec.input_tokens,
                    "completion_tokens": rec.output_tokens,
                    "reasoning_tokens": getattr(rec, "reasoning_tokens", None),
                    "latency_s": rec.latency_s,
                })
            out_rows.append(row)
            if n % 50 == 0:
                log(f"  {n}/{len(jobs)} (real={n_real} cached={n_cached} err={n_err})")
    wall = time.monotonic() - t0
    log(f"done in {wall:.1f}s real={n_real} cached={n_cached} errors={n_err}")

    # ---- score with the BENCHMARK'S OWN scorer + the official abstention rule
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown,
    )
    for row in out_rows:
        if row["content"] is None:
            row["reward"] = None
            row["is_unknown"] = None
            continue
        if row["task_id"] == POSCTRL["task_id"]:
            spec, gold = POSCTRL["eval_function"], POSCTRL["answer"]
        else:
            t = tasks[row["task_id"]]
            spec, gold = t.eval_function, t.answer
        # Score the EXTRACTED answer, exactly as run_deltau_pilot.py does
        # (`task.score(pw)` where `pw = extract_boxed_answer(ow)`). Passing the
        # RAW content instead scores "boxedparis" against "paris" and returns
        # False for a correct answer -- caught by the offline control below,
        # which is why the control exists.
        parsed = extract_boxed_answer(row["content"])
        unk = bool(is_unknown(parsed))
        from p1mem.adapters.vendor.lmev2_qa_eval_metrics import eval_from_spec
        raw = bool(eval_from_spec(spec, parsed, gold))
        row["is_unknown"] = unk
        # harness.py:1055 -- an abstention scores 0 exactly like a wrong answer
        row["reward"] = 0.0 if unk else float(raw)
        row["reward_raw_before_unknown_rule"] = float(raw)

    resp_path = args.out / "responses.jsonl"
    with open(resp_path, "w") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    log(f"wrote {len(out_rows)} rows -> {resp_path}")

    # ---- summarise, paired within each (config, group)
    idx = {(r["config"], r["group"], r["memory_id"], r["task_id"], r["arm"]): r
           for r in out_rows}
    summary: dict[str, Any] = {
        "run_at_utc": utc_now(),
        "rows_artifact": str(resp_path),
        "wall_clock_s": round(wall, 2),
        "real_endpoint_calls": n_real, "cache_hits": n_cached, "errors": n_err,
        "planned_calls": len(jobs),
        "n_oracle_cells": len(oracle), "n_control_cells": len(control),
        "max_pool_hits": args.max_pool_hits,
        "configs": {c: CONFIGS[c] for c in cfg_names},
        "oracle_cells": [list(k) for k in oracle],
        "control_cells": [list(k) for k in control],
        "results": {},
        "positive_control": {},
    }
    for cname in cfg_names:
        summary["results"][cname] = {}
        for group, keys in (("oracle", oracle), ("control", control)):
            nw = no = n = bf = unkw = 0
            missing = 0
            for k in keys:
                rw = idx.get((cname, group, k[0], k[1], "with_memory"))
                ro = idx.get((cname, group, k[0], k[1], "without_memory"))
                if not rw or not ro or rw["reward"] is None or ro["reward"] is None:
                    missing += 1
                    continue
                n += 1
                nw += rw["reward"]
                no += ro["reward"]
                unkw += bool(rw["is_unknown"])
                if max(rw["reward"], ro["reward"]) == 0.0:
                    bf += 1
            if n == 0:
                summary["results"][cname][group] = {"n_cells": 0, "missing": missing}
                continue
            _, wlo, whi = wilson_ci(round(nw), n)
            summary["results"][cname][group] = {
                "n_cells": n, "missing": missing,
                "n_correct_with": round(nw), "acc_with": nw / n,
                "acc_with_wilson": [wlo, whi],
                "n_correct_without": round(no), "acc_without": no / n,
                "delta": (nw - no) / n,
                "both_arms_fail": bf, "both_arms_fail_rate": bf / n,
                "abstentions_with": unkw,
            }
        pc = idx.get((cname, "positive_control", "__posctrl__", POSCTRL["task_id"],
                      "with_memory"))
        summary["positive_control"][cname] = {
            "reward": None if not pc else pc["reward"],
            "content": None if not pc else (pc["content"] or "")[:200],
            "_reading": "must be 1.0. If an arm shows no gain and this is 1.0, the "
                        "harness could have registered a gain and did not.",
        }
    write_json_atomic(args.out / "summary.json", summary)

    print("\n================ J2 RESULT ================")
    for cname in cfg_names:
        pc = summary["positive_control"][cname]
        print(f"\n-- {cname}  ({CONFIGS[cname]['cluster']}/{CONFIGS[cname]['model']} "
              f"effort={CONFIGS[cname]['reasoning_effort']} "
              f"max_tokens={CONFIGS[cname]['max_tokens']})")
        print(f"   POSITIVE CONTROL reward={pc['reward']}  content={pc['content']!r}")
        for group in ("oracle", "control"):
            s = summary["results"][cname][group]
            if not s.get("n_cells"):
                print(f"   {group:8s} NO DATA (missing={s.get('missing')})")
                continue
            print(f"   {group:8s} n={s['n_cells']:3d} accW={s['acc_with']:.4f} "
                  f"[{s['acc_with_wilson'][0]:.3f},{s['acc_with_wilson'][1]:.3f}] "
                  f"accWO={s['acc_without']:.4f} d={s['delta']:+.4f} "
                  f"bothfail={s['both_arms_fail']}/{s['n_cells']} "
                  f"abstainW={s['abstentions_with']}")
    print(f"\n[wrote] {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
