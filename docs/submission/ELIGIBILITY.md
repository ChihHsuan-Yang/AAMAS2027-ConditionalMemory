# AAMAS 2027 Main Track — Submission Eligibility Dossier

**Compiled 2026-09-29 by the Master Agent. Every fact below was fetched today from a
primary source; the source is named inline.** This file supersedes the inherited
`AAMAS_SUBMISSION_CHECKLIST.md` where they differ.

> The inherited checklist's own header records that a *previous* version of it confidently
> reported AAMAS 2027 as unannounced, and was wrong. So nothing here is inherited: each
> line was re-fetched today.

---

## 0. Verdict

| Item | Status |
|---|---|
| Conference exists, submissions open | ✅ VERIFIED |
| Dates (1 Oct abstract / 8 Oct paper, AoE) | ✅ VERIFIED — match the user's independent check |
| Area to select | ✅ RESOLVED — **LEARN** primary |
| Abstract length | ✅ VERIFIED — "around 100-300 words in plain text" |
| Abstract drafted in range | ✅ 268 words, forbidden-claim scan clean |
| **Author list** | 🔴 **DECISION NEEDED FROM USER** — cannot be inferred |
| **OpenReview profiles for all authors** | 🔴 **CANNOT VERIFY PROGRAMMATICALLY** — channel is login-gated |
| **Reciprocal reviewer designation** | 🔴 **DECISION NEEDED FROM USER** — desk-rejectable if unmet |

**No eligibility problem is confirmed. Two items are unresolvable without the user**, and
both are hard-gated on 1 Oct AoE.

---

## 1. Dates — VERIFIED

Source: <https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-main-track/> (fetched
2026-09-29). Independently corroborated by the OpenReview API: the venue group
`ifaamas.org/AAMAS/2027/Conference` resolves with `readers: ["everyone"]`
(positive-controlled against `ICLR.cc/2026/Conference`, which also resolved).

| Milestone | Date |
|---|---|
| Author registration on OpenReview | 17 Sep 2026 — ⚠️ **already passed** |
| **Abstract submission** | **1 Oct 2026** |
| **Paper submission** | **8 Oct 2026** |
| Rebuttal | 20–24 Nov 2026 |
| Notification | 21 Dec 2026 |
| Camera-ready | 25 Jan 2027 |
| Conference | 3–7 May 2027 |

Verbatim: *"All deadlines are at the end of the specified day, Anywhere on Earth (UTC-12)."*

⚠️ The inherited note claims OpenReview allows a 30-minute hard grace past the due time.
**Not re-verified today, and not to be planned around.**

## 2. Areas — VERIFIED, recommendation RESOLVED

Verbatim, authors *"will be asked to associate your paper with one of the following areas
of interest"*: Learning and Adaptation (**LEARN**); Generative and Agentic AI (GAAI); Game
Theory and Economic Paradigms (GTEP); Coordination, Organizations, Institutions, Norms and
Ethics (COINE); Search, Optimization, Planning and Scheduling (SOPS); Representation and
Reasoning (RR); Engineering and Analysis of Multiagent Systems (EMAS); Modelling and
Simulation of Societies (SIM); Human-Agent Interaction (HAI); Robotics and Control (ROBOT);
Innovative Applications and Societal Impact (IASI).

**Recommended primary: LEARN.** The paper is an empirical measurement study of what an
adaptive agent should retain from experience — learning and adaptation is its home.

**Recommended secondary (≤2 permitted): GAAI**, and **EMAS** as the alternate. GAAI covers
LLM-agent systems, which is the substrate; EMAS covers empirical analysis methodology,
which is the paper's mode. Pick GAAI first if only one is taken.

⚠️ *"Out-of-area papers may be desk rejected"* — per the inherited note; area scope is also
checked by ACs at abstract time (instructions page: ACs *"check that abstracts are within
scope for the area"*).

## 3. Abstract requirements — VERIFIED

Source: <https://warwick.ac.uk/fac/sci/dcs/aamas2027/guidelines-and-policies/instructions/>

- Registering an abstract is *"required one week before the paper submission deadline"*.
- Length: *"of around 100-300 words in plain text"*.
- Also collected at abstract time: *"some additional information at this time, such as
  keywords characterizing your paper"*, plus the AAMAS area association.
- A student-paper checkbox exists (*"the primary author is a student"*), withheld from
  reviewers, governing Best Student Paper eligibility.

⚠️ **"Plain text"** — the abstract must not rely on LaTeX math. The drafted abstract is
plain prose with no symbols, deliberately.

⚠️ The instructions page does **not** itemize the full form. Budget time on 1 Oct for
unlisted fields.

## 4. 🔴 Reciprocal reviewer — the real blocker

Sources: [policy page] and [Q&A], both fetched 2026-09-29.

**Requirement**, verbatim: *"Each submission must designate at least one qualified author
who agrees to serve as a reviewer for AAMAS."*

**Two binding deadlines**, verbatim from the Q&A:
- *"The reciprocal reviewer must be designated in OpenReview by the abstract submission
  deadline (1 October 2026, Anywhere on Earth)."*
- *"At least one qualified designated reciprocal reviewer must accept the AAMAS 2027
  Reviewer invitation in OpenReview by the paper submission deadline (8 October 2026,
  Anywhere on Earth)."*

**Penalty**, verbatim: *"Submissions that fail to satisfy this requirement may be
desk-rejected."* AAMAS further *"reserves the right to reject submissions that do not
satisfy the reciprocal reviewer policy, including cases where designated reviewers fail to
complete their assigned reviews."*

**Eligibility** (Reviewer Guidelines, fetched today): *"hold a PhD in Computer Science or a
closely related field"*, **or** be a third-year-or-later PhD student with *"at least 3
peer-reviewed publications in relevant venues (e.g., NeurIPS, ICML, AAAI, IJCAI)"*.
Selection may also weigh *"prior reviewing experience and overall research maturity"*.

**Downstream obligations the nominee is accepting** (Reviewer Guidelines):
reviews due **13 Nov 2026**; ~half done by **26 Oct 2026**; discussion 25 Nov–3 Dec;
**mandatory rebuttal acknowledgement by 3 Dec 2026** — skipping it *"counts as not
completing the review."*

**Load: NOT PUBLISHED.** Confirmed absent from the policy page, the Q&A, and the Reviewer
Guidelines. Contact `aamas2027pcs@gmail.com` if the number matters to the nominee's consent.

**Changing the nominee later**, verbatim from Q&A: *"No, except when there is a reasonable
justification and the change is approved by the Program Chairs."* — so **designate
carefully on 1 Oct; this is not freely revisable.**

**Exemption** (policy page): available only if *"None of the authors is qualified"* or
*"All qualified authors are serving as Area Chairs (ACs), Senior Program Committee (SPC),
or in other official organizing roles for AAMAS 2027."* Claimed via a declaration in the
abstract form. Given the likely author list includes multiple PhD holders, **the exemption
almost certainly does not apply to us.**

### What the user must decide

**Who is the designated reciprocal reviewer?** They must (a) be an author on this paper,
(b) meet the PhD criterion, (c) personally accept an OpenReview reviewer invitation by
8 Oct, and (d) actually review, with a hard 13 Nov deadline and a 3 Dec acknowledgement.

This is a real commitment to a third party's calendar. It cannot be assigned by an agent.

## 5. 🔴 OpenReview profiles — CHANNEL FAILURE, not an absence

**I could not verify any author's profile, and I am reporting that as a channel failure.**

What I ran and what happened:

| Route | Result |
|---|---|
| `api.openreview.net/profiles/search?email=` | **HTTP 403** — *"This action is forbidden. You must be logged in to access this resource."* |
| `api2.openreview.net/profiles/search?email=` | returns `{"profiles":[]}` — **a silent empty, not an error** |
| `api2.openreview.net/profiles/search?term=` | **HTTP 403**, same message |
| `api2.openreview.net/profiles?id=~Ian_Foster1` | `count 0` |
| `api2.openreview.net/profiles/search?fullname=Ian Foster` | `count 0` |

**Positive control:** I queried `foster@uchicago.edu` — a profile that certainly exists
(Ian Foster is a long-standing author at these venues). It returned **zero** on `api2` and
**403** on `api1`. Since the control fails, every "NO PROFILE" result from this channel is
meaningless. **Profile lookup requires authentication; the empty result is the API refusing
an anonymous caller, not a statement about the person.**

This is precisely the trap that produced five false negatives in the inherited audit.

### Consequence

**Someone with an OpenReview login must check this manually.** The registration deadline
(17 Sep) has already passed; no sanction for late creation is stated anywhere on the site,
so this is a risk rather than a certain bar — but a missing profile silently breaks an
`authorid` field on deadline night, and profile activation is not instant.

Verbatim requirement (instructions page): *"every author on a paper must have an account on
OpenReview"*, due two weeks before abstract submission. The inherited note records an
attestation checkbox requiring *"full publication name, current position,
institution-affiliated email address, and DBLP URL if available."* — **not re-verified
today** (it is inside the submission form, which needs a login).

## 6. Author list — DECISION NEEDED

**No author list for P1 exists in any local record.** `collaborator-info.md` holds per-paper
lists for four *other* papers, and P1 is not among them. Inferring one would be a
fabrication.

Recorded metadata for plausible candidates (from `collaborator-info.md`, affiliations
public):

| Name | Email | Affiliation |
|---|---|---|
| Chih-Hsuan (Bella) Yang | `bellayang@anl.gov` | Argonne National Laboratory |
| Jingyan Jiang | `jingyan.jiang@anl.gov` | Argonne National Laboratory |
| Cheng-Hau Yang | `chenghau.yang@anl.gov` | Argonne National Laboratory |
| Vikram Vasudevan | `vasudevv@oregonstate.edu` | Oregon State University |
| Huihuo Zheng | `huihuo.zheng@anl.gov` | Argonne National Laboratory |
| Le Chen | `lechen@anl.gov` | Argonne National Laboratory |
| Venkatram Vishwanath | `venkat@anl.gov` | Argonne National Laboratory |
| Rajeev Thakur | `thakur@anl.gov` | Argonne National Laboratory |
| Ian T. Foster | `foster@uchicago.edu` | University of Chicago; Argonne National Laboratory |
| Eliu A. Huerta | `elihu@anl.gov` | Argonne National Laboratory; University of Chicago |
| Tanwi Mallick | `tmallick@anl.gov` | Argonne National Laboratory |
| Krishnan Raghavan | `kraghavan@anl.gov` | Argonne National Laboratory |
| Amal Gueroudji | `agueroudji@anl.gov` | Argonne National Laboratory |

Corresponding author for all prior papers: **Chih-Hsuan Yang, `bellayang@anl.gov`**.

⚠️ The user's instruction: *"Do not change the author list casually after registration."*
Note the site only forbids changes **after acceptance**; the Q&A does **not** address
changes between abstract and paper submission (verified today — genuinely absent, not
missed). AAMAS 2026 froze the list at the abstract deadline. **Treat the 1 Oct list as
final.**

## 7. Format constraints that bind the writing

- **8 pages**, references unlimited: *"at most eight (8) pages long, with any number of
  additional pages containing bibliographic references."*
- 🔴 **Appendices COUNT toward the 8 pages** — Q&A, verbatim: *"An appendix included in the
  main paper is considered part of the paper and therefore counts towards the 8-page
  limit."* and *"Appendices do not provide additional pages beyond the standard page
  limit."* **This differs from AAMAS 2026.** The inherited note flags that the Reviewer
  Guidelines contradict this; the Q&A is author-facing and specific, so **plan to 8 pages
  including any appendix** and put overflow in supplementary.
- **LaTeX mandatory**, no Word template. Do *"not modify the style files or any of the
  layout parameters"*; *"Excessive use of typesetting tricks"* is called out.
- **Double-blind**, including supplementary.
- **No extended abstracts in 2027** — that fallback no longer exists.
- **Findings**: archival opt-out-not-opt-in track, same length and format.
- **AI-assistance disclosure is REQUIRED and binds this project**, verbatim: *"Where used
  in the creation of hypotheses or methodologies, including experimental design, detailed
  information should be provided in the paper or in the supplementary material, including
  the prompt used, as well as the AI tool and its version."* Hallucinated citations are a
  named desk-reject trigger → **every citation must be human-verified against a fetched
  source.**

## 8. Open items to confirm with the PCs (`aamas2027pcs@gmail.com`)

1. How many papers must a reciprocal reviewer review? (unpublished — verified absent from
   all three policy pages)
2. The appendix page-limit contradiction between the Q&A and the Reviewer Guidelines.
3. Whether the author list may change between 1 Oct and 8 Oct.

None of these blocks registering the abstract.
