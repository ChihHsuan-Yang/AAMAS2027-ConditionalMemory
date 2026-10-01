# The 8-page body limit — measured state and the options

**Written 2026-10-01 by the Master Agent.** AAMAS 2027 allows **8 pages of
body** plus unlimited references. The body currently runs **~5,400 characters
onto page 9**. This document exists because closing that gap now requires
removing *content*, which is a decision the author should make, not an agent.

## What has already been tried, with measurements

| attempt | prose removed | overflow moved | note |
|---|---:|---:|---|
| earlier agent's word-level tightening | 2,186 | 1,122 | **~52% efficient** |
| my reader-transfer paragraph tighten | 196 | 247 | |
| my Figure 5 caption tighten | 14 | **0** | reflow absorbed it entirely |
| relax tables `[t]` → `[tb]` | — | **0** | **float placement is not the binding constraint** |

**Cutting prose is only about half efficient here.** Text reflows and floats
repack, so roughly half of every cut is reabsorbed. Closing ~5,400 characters
therefore needs **~10,000 characters** of prose removed — roughly a fifth of
the body's running text.

## Why there is no more cheap prose

Section-by-section prose sizes (comments and floats excluded):

| chars | section |
|---:|---|
| 7,200 | Benchmarks and Experimental Setup |
| 5,203 | Limitations |
| 4,278 | Introduction |
| 3,841 | Related Work |
| 3,727 | Utility, floors, and robust labels |
| 3,157 | Memory utility survives a change of reader |
| 2,882 | Screening the pairing makes the effect measurable |

I read the two largest. **Neither is padding.** The setup section is the
verification detail that makes the measurements checkable — the eight distinct
scorer specification strings, the containment-not-equality matcher, the
positive control on haystack identity. The limitations section is where the
corrections live: the within-session floor scope, the leakage lower bound, the
SciCode counterexample. Several of those sentences exist **because a defect
was found**, and the audit has guards requiring specific ones to be *present*.

**Adding to the problem, correctly:** the required AI-Assisted Technologies
section was an empty `TODO` and is now written (~2,400 chars). AAMAS requires
it wherever AI shaped experimental design and names misuse as a desk-reject
trigger, so it is not optional and not compressible below its required content.

## The options, with their costs

Each removes content. **None should be taken by an agent.**

| # | option | frees | what is lost |
|---|---|---:|---|
| **A** | Move **Figure 1** (`fig:pipeline`, 4,886 chars) to supplementary | ~1 col | the protocol diagram. The paper is readable without it — it illustrates rather than evidences — but it is the fastest orientation for a reviewer |
| **B** | Move **Figure 3** (`fig:similarity`, 3,248) to supplementary | ~0.7 col | a real negative finding: similarity does not locate a useful memory. The prose states it; the figure shows the flatness |
| **C** | Move the **AI disclosure** to supplementary | ~1,036 | permitted by the policy (it allows paper *or* supplementary), and the cheapest legitimate option. Costs reviewer visibility of the disclosure |
| **D** | Drop a results subsection | 500–3,200 | a measured result |
| **E** | Compress Limitations | up to 5,203 | the corrections that make the paper trustworthy. **Worst option** |

**My recommendation: C, then A.** C is explicitly permitted by the AAMAS
policy and loses no scientific content. A loses a diagram, not a measurement.
Together they are approximately the gap. **B, D and E all delete evidence and
should not be used to buy space.**

## What must not be done

No `\vspace`, no `\enlargethispage`, no body font-size change, no geometry
change, no moving body text into footnotes. The template's declared geometry
is the submission's format contract; beating it typographically is the
"format gaming" failure, and reviewers check.
