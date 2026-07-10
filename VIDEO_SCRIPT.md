# Demo Video Script (target: 7-8 minutes)

Structure follows exactly what the brief asks for: Architecture, Approach, Demo,
Trade-offs, What you'd improve next. Timings are approximate -- talk naturally,
don't read this verbatim.

---

## 1. Framing the problem (0:00-0:45)

"Sherlock's fraud detectors need to point their cameras and microphones at the
*right* person. The hard part isn't detection -- it's that every individual
signal for 'who is the candidate' can be wrong on its own: wrong calendar
name, device-name display names, nicknames, silent observers, multiple
interviewers. So I treated this as an evidence-fusion problem under
uncertainty, not a single classification rule."

## 2. Architecture (0:45-2:15)

Walk through `ARCHITECTURE.md`'s diagram, top to bottom:
- Event ingestion layer (mention: in production this would be a unified
  meeting-bot API like Recall.ai, rather than three separate SDK integrations)
- Seven independent signal extractors, each scoring every participant
- A fusion engine that combines them transparently
- Output: confidence + full reasoning trail, feeding the downstream fraud detectors

Say explicitly: "I deliberately chose a transparent weighted-evidence model
over a black-box classifier, because the brief weights explainability as
highly as raw accuracy."

## 3. Approach -- the two ideas that matter most (2:15-4:00)

Show `signals.py` and `fusion.py` briefly. Explain two design decisions,
concretely:

**a) No signal is trusted alone.** E.g. show the `name_match` function: a
device-name display name ("MacBook Pro") is treated as *neutral*, not
negative -- because punishing it would bias the system against exactly the
case the brief calls out.

**b) Metadata is evidence, not ground truth.** Show the adaptive reliability
check in `fusion.py`: if the calendar name doesn't match anyone, the system
infers the metadata itself might be wrong and down-weights it automatically,
rather than either trusting a bad name or failing outright.

## 4. Live demo (4:00-6:00)

Run `python3 main.py` on screen. Narrate the output tick by tick:
- Tick 0: candidate is still "MacBook Pro" -- point out it's already at 83%
  confidence from domain + speaking pattern + transcript alone, and the
  system is flagging the name metadata as unreliable.
- Tick 2: candidate renames to "Rahul K" -- confidence jumps to 96%, and the
  "unreliable metadata" note disappears on its own.
- Point at Sarah Chen (interviewer) and Amit S (silent observer) staying near
  0% throughout -- explain *why* for each (roster suppression + host signal;
  no speech at all, correctly left unclassified rather than forced).
- Finish on the FINAL DECISION line.

## 5. Trade-offs (6:00-7:00)

Be direct about the scope call:
- "I simulated the meeting timeline instead of integrating live Zoom/Meet/
  Teams SDKs. Building three platform integrations in a day would have taken
  time directly away from the reasoning engine, which is the actual
  intellectual content being evaluated. The signal and fusion code is written
  against the same data model a real integration would populate, so that
  swap doesn't touch the core logic."
- "I used fixed, hand-tuned weights rather than a learned model, because I
  have no labeled outcome data yet -- but the design is built so those
  weights become learned coefficients the moment that data exists."
- "The transcript classifier defaults to a keyword heuristic rather than
  always calling an LLM, on purpose -- it's a deliberate reliability/cost
  trade-off, with the LLM path available as an upgrade, not a dependency."

## 6. What I'd improve next (7:00-7:45)

In priority order (see `EVALUATION.md` for the full list):
1. Face-embedding verification against a reference photo -- the single
   strongest signal, and it doubles as impersonation/deepfake detection.
2. Replace hand-tuned weights with a small logistic regression trained on
   real labeled outcomes.
3. Event-driven re-evaluation instead of fixed-interval ticks.
4. Real OCR/vision-based screen-share content classification.
5. A real labeled benchmark from anonymized interviews for an actual
   precision/recall number.

## Close (7:45-8:00)

"The core bet I made: in a domain where every individual signal is
individually fragile, the right architecture is one that fuses many weak
signals transparently and is honest about uncertainty -- rather than one
clever rule that looks good on the happy path and breaks silently on the
edge cases."
