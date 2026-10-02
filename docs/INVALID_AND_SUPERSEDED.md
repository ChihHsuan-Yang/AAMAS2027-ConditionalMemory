# Invalid and superseded work — do not use these

**One canonical list of what must not be cited, pooled, or re-run.** Retraction
here is *labelling, not deletion*: the artifacts stay on disk so a reader can
check the correction, and every entry says what replaced it.

Last verified: **2026-10-02**.

## VOID — produced by a defective instrument, never valid

| artifact | why | replaced by |
|---|---|---|
| `results/swebench/representations_v1.json` | the contagion screen false-positived on `+---+` **ASCII table borders in issue text**, over-excluding memory bodies | `representations_v2.json` + the v3 chunks |
| `results/raw_session_matched_VOID_mislabelled/` | **defect 27** — `condition_id` said `gemma4_31B` on rows whose `reader_model` was `gpt-oss-120b`; the label contradicted the measurement | `results/raw_session_matched/` |
| SWE-bench floor pilot #1 | the model was shown the wrong 90 lines while the gold patch edited line 1386 | floor pilot #2 → `parity_v2.json` |
| "variance shares all 0.0000" | a `ZeroDivisionError` crashed the stage while the script exited 0; the caller read an empty dict | **never measured** — do not quote any value |

🔴 `representations_v1.json` was once the **default `--src`** of the analysis
script, so running it bare analysed voided data. The default is removed and all
three scripts now refuse the file **by name**.

## SUPERSEDED — validly measured, then replaced by a better measurement

| superseded | value | replaced by | why |
|---|---|---|---|
| cross-session reader transfer | +0.1268 [+0.0511, +0.2050], n=276 | **session-matched +0.0982 [+0.0247, +0.1730]**, 275 cells | arms ran 11 h apart and this endpoint is deterministic *within* a session, not across (**defect 25**) |
| the "about half the gain is a weaker reader" split | −0.0688 | **−0.0364** session-matched | roughly half of that figure was a day of endpoint drift |
| SWE-bench matched set | n=15, then n=17 | **n=40** (django 37 + sympy 3) | the arm was completed to 107/107 recipients |
| SWE-bench rewards from pre-fix runs | 37 arm-reads scored `0.0` | demoted to `None` | **defect 21** — a pytest *collection error* is not a wrong answer |
| embedding truncation share | 93.6% | **96.6%** | the 3,400-token cap it was computed against was withdrawn |
| "948 of 948, zero filler" | — | the measured form (median 6,913 of 6,913 tokens) | no artifact ever supported the count |
| unscreened pairing arms | both-arms-fail ~78.5% / 83.75% | the screened design | valid but floor-limited; keep only as the dilution comparator |
| n=8 representation pilot | — | the 277-cell scale-up | superseded for every rate; keep only its compression ratios |

## Not superseded — deliberately kept as a reported negative

| result | status |
|---|---|
| the **founding sign-reversal hypothesis** | **unsupported, and reported as such.** 0/35 on bearing cells, Wilson [0, 0.0989]. This is a finding, not a gap |
| **GF-LEX**, the lexical gold-free screen | found **no** effect, and is **published alongside** the screen that did. Reporting only the screen that worked would select an instrument on its outcome |

## Rules that follow from the above

1. **Never pool a cross-session comparison.** Re-run comparators in one session.
2. **Never coerce `reward: None` to `0.0`.** An unapplicable edit, a collection
   error, a truncation and an unavailable scorer are all *unscorable*.
3. **Check `_VOID_`/`v1` by name, not by glob** — `results/swebench/representations_*.json`
   sweeps in the voided file and changes the demoted-zero count.
4. Full defect history, 30+ entries: [`DEFECT_REGISTER.md`](DEFECT_REGISTER.md).
