# Evaluation

## How it was tested

Given the timeline, testing focused on **scenario-based validation** through
`simulator.py` rather than a large labeled dataset: each named edge case in
the brief was built into a concrete scenario and the fusion engine's output
was checked at every tick for (a) correctness of the final decision and
(b) sanity of the intermediate confidence trajectory.

The included scenario (`simulator.py`) exercises, in a single run:

| Edge case from the brief | How it's exercised | Result |
|---|---|---|
| Candidate joins as device name | Candidate's `display_name = "MacBook Pro"` for ticks 0-1 | `name_match` correctly returns neutral (not negative); other signals still identify them at 83-89% confidence |
| Candidate changes display name mid-call | Rename to `"Rahul K"` at tick 2 | Belief re-evaluated immediately using the new name; confidence rises to 96% |
| Nickname vs. legal name | `"Rahul K"` vs. calendar `"Rahul Kumar"` | Fuzzy match (0.75 similarity) + nickname table both contribute positively |
| Interviewer entered/implied wrong candidate name | Calendar name doesn't match anyone well pre-rename | `metadata_reliable` flips to `False`; name-signal weight cut to 25%; surfaced as an explicit note |
| Multiple interviewer names, one no-show | Roster lists `["Sarah Chen", "Priya Singh"]`, only Sarah joins | System doesn't wait for/expect Priya; correctly suppresses only the participant who matches |
| Silent observer | `"Amit S"`, camera off, zero speech throughout | Stays at 4-17% probability the whole time -- never forced into either role |
| Host bias | Interviewer is also meeting host | `meeting_host` signal adds independent negative evidence beyond just the roster match |

## Accuracy on the test scenario

Final state: **Rahul K identified as candidate at 95% confidence**, correct
participant, by tick 2 (~90 simulated seconds). Sarah Chen (interviewer) and
Amit S (observer) both stay under 5% throughout. No tick produces an
incorrect `IDENTIFIED` result.

This is evaluation on one authored scenario, not a statistically meaningful
accuracy number -- see Limitations.

## Limitations

- **One scenario, hand-authored.** This does not demonstrate generalization.
  A real evaluation needs a labeled set of actual (or recorded/anonymized)
  interviews spanning different company norms (e.g. cultures where the
  interviewer talks more), different numbers of participants, and different
  failure combinations (e.g. *both* wrong name *and* no domain info at once).
- **Fixed, hand-tuned weights.** The signal weights in `fusion.py` were set
  by judgment, not fit to data. They should be treated as a reasonable prior,
  not a calibrated model -- retraining them (see README "Path to production")
  is the natural next step once labeled outcomes exist.
- **Heuristic transcript classifier by default.** The keyword-based fallback
  is intentionally crude; it will misfire on interviews that don't use the
  specific phrases it looks for. The LLM path is more robust but adds
  latency/cost and wasn't extensively tuned here.
- **No face/voice biometric signal yet**, despite this being arguably the
  single strongest possible signal for Sherlock's use case (and the one most
  directly tied to deepfake/impersonation detection). Not included because it
  requires a reference image/voice sample pipeline that's out of scope for a
  one-day prototype, but it's the highest-leverage addition in "path to
  production."
- **No handling of >1 candidate in the room** (e.g. a paired/team interview
  format) -- current design assumes exactly one candidate is the target.
- **English-only heuristics** (nickname table, keyword lists) -- would need
  localization for non-English interviews.

## What I'd improve next (in priority order)

1. Replace the hand-tuned weights with a small logistic regression trained on
   real labeled outcomes (the "continue learning" bonus point).
2. Add face-embedding verification against a reference photo where available.
3. Move from tick-based to event-driven re-evaluation (recompute on every new
   transcript utterance / speaking-activity change instead of a fixed timer).
4. Build the real ingestion layer against a unified meeting-bot API.
5. Add OCR/vision-based screen-share content classification.
6. Build a small labeled benchmark from real (anonymized) interview
   recordings to get an actual precision/recall number instead of scenario
   spot-checks.
