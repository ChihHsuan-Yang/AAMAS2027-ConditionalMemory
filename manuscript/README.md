# Manuscript source

LaTeX source of **What Is This Memory Useful For? Measuring Task-Conditioned Utility in Long-Term Agent
Memory** (preprint, October 2026; not accepted). Exported from the authors' Overleaf project on
2026-11-06. This is the source of the release PDF at [`../website/paper.pdf`](../website/paper.pdf).

The older single-file snapshot in [`../paper/`](../paper/) is superseded; do not use it.

## Build

```bash
latexmk -pdf -interaction=nonstopmode main.tex
```

`main.tex` is the paper with the supplement included after the references. `seperate_supplement.tex`
(the spelling is the project's) builds the supplement alone. The document class `aamas.cls` and
`ACM-Reference-Format.bst` are the conference's files. The build needs a TeX Live installation with the
Libertine and newtx fonts, which Overleaf has by default; a minimal LaTeX install fails with a
font-expansion error.

## Layout

| Path | Contents |
|---|---|
| `main.tex` | Paper |
| `sections/` | One file per section (`00_abstract` … `07_ai_disclosure`) and the supplement (`supp_*`) |
| `figures/` | Figure PDFs and the two TikZ figures |
| `macros/` | Generated number macros. Every measured number in the text comes from here. **Do not edit by hand** |
| `xref/` | Static label tables, so the paper and the supplement each compile alone |
| `p1refs.bib` | References |

## What is not here

The comments in `main.tex` and the macro files name generator scripts that are not in this repository
(`tools/build.sh`, `tools/make_results_figure.py`, `scripts/audit_claims.py`). The macros are therefore
the checked-in record of the numbers, not something this repository regenerates. To check the numbers
against the data, use [`../docs/REPRODUCIBILITY.md`](../docs/REPRODUCIBILITY.md) and
[`../docs/RELEASE_COVERAGE.md`](../docs/RELEASE_COVERAGE.md).
