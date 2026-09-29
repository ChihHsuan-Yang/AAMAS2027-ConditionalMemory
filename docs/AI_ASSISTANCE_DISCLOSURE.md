# AI-Assistance Disclosure — draft for the manuscript

**AAMAS 2027 requires this, and names inappropriate use as a desk-reject trigger.**
Policy text, verified from the official site 2026-09-29:

> *"AI-assisted technologies may not be listed as authors or co-authors… It is permissible
> to use AI-assisted technologies for the polishing and formatting of text and in the
> creation of code and scripts used in proofs-of-concept, demonstrations and experiments.
> **Where used in the creation of hypotheses or methodologies, including experimental
> design, detailed information should be provided in the paper or in the supplementary
> material, including the prompt used, as well as the AI tool and its version.**"*

Two facts that bind us:
1. AI was used in **experimental design**, not only in code and polishing. The heavier
   disclosure clause therefore applies.
2. *"Hallucinated citations"* are named as a desk-reject trigger.

---

## Draft disclosure text (for the manuscript)

> **Use of AI-assisted technologies.** This work was carried out with substantial use of
> AI coding and research assistants (Claude Opus 5 via Claude Code, accessed 2026-09-29),
> operating under human direction. Their use extended beyond text polishing to the
> creation of code, the execution and monitoring of experiments, and participation in
> experimental design; we therefore disclose it under the stronger clause of the AAMAS
> policy.
>
> Specifically, AI assistants: implemented the measurement harness, the benchmark adapter,
> the counterfactual cell construction, and the analysis code; screened the memory–task
> corpus; executed the inference campaigns; and proposed elements of the experimental
> design, including the discriminative screening criterion and the stratified
> bearing/matched-control/random design.
>
> Every quantitative claim in this paper was re-derived by a human-directed verification
> pass from the row-level artifact, independently of the agent that produced it, and the
> artifacts are released. Analysis definitions, denominators, the contrast that carries
> the claim, and a stopping rule capable of terminating the study were committed to
> version control **before** the corresponding data existed; the repository's history
> makes that ordering checkable. Every citation was verified against a fetched primary
> source, and a list of claims we were unable to verify is given in the limitations.
>
> Prompts are reproduced in the supplementary material.

⚠️ **The final version must be written and signed off by the human authors.** The text
above is a draft prepared for their review, and the first-person plural in it is
theirs to accept or rewrite.

## What must accompany it in supplementary material

| required | status |
|---|---|
| tool + version | ✅ Claude Opus 5 via Claude Code, 2026-09-29 |
| prompts used | ⚠️ **to assemble** — the sub-agent task prompts are the substantive ones |
| where AI shaped **design** (not just code) | ✅ listed above; the screening criterion and stratified design are the honest cases |
| human verification procedure | ✅ described; the defect register is the evidence |

## Why the defect register belongs in the supplement

`docs/DEFECT_REGISTER.md` records 15+ instrument defects found on the first execution day,
of which **eleven produced a plausible-looking number** before being caught. It is the
concrete evidence that the verification described above was real and adversarial rather
than nominal — including cases where the coordinating agent's own published numbers were
retracted after a sub-agent re-measured them.

**A reviewer is entitled to ask what human oversight of a largely AI-executed study
actually consisted of.** The register, the retractions visible in the results ledger, and
the pre-commitment history are the answer, and they are stronger evidence than any
assurance in prose.

## Standing rule for this project

No AI-produced claim enters the manuscript unless a human-directed pass re-derived it from
the artifact. Where that was not possible, the claim is marked unverified and the reason
is stated — see the channel-dead entries in `docs/LITERATURE_BOUNDARY.md`.
