# Sherlock Candidate Identification -- Prototype

Identifies which participant in a live interview is the **candidate** (as opposed to
interviewers or silent observers), continuously, with a confidence score and a
full explanation of *why*.

## The core idea

No single signal reliably identifies the candidate -- display names get typo'd,
candidates join as "MacBook Pro", calendars list interviewers who never show up.
So this system never asks "which rule matched?" -- it asks **"given everything
we've observed so far, what's the probability distribution over who the
candidate is?"**, and keeps updating that distribution as new evidence arrives.

Seven independent weak signals are extracted per participant, per update cycle:

| Signal | What it checks | Why it's only *weak* evidence |
|---|---|---|
| `name_match` | Fuzzy/nickname match of display name vs. calendar candidate name | Candidates rename, use device names, or use nicknames |
| `interviewer_roster` | Fuzzy match against known interviewer names | Suppresses interviewers; but the roster itself can be incomplete |
| `meeting_host` | Is this participant the organizer? | Candidates are almost never the host -- but this alone doesn't confirm who *is* the candidate |
| `email_domain` | Internal company domain vs. external | Not always available (guest links have no email) |
| `speaking_pattern` | Speaking-time share + question-vs-answer ratio | A quiet candidate or a chatty interviewer can look atypical |
| `transcript_semantics` | LLM (or heuristic fallback) classification of "answering" vs. "asking" language | Needs some transcript to accumulate; can misfire on short turns |
| `screen_share` | Whether/how they used screen share | Not every interview involves screen share |

`fusion.py` combines these with fixed weights into a raw score per participant,
turns the scores into a probability distribution via softmax, and returns one of:

- **IDENTIFIED** -- confident, with a specific participant and full reasoning trail
- **AMBIGUOUS** -- top two candidates too close to call; system asks for more evidence rather than guessing
- **GATHERING_EVIDENCE** -- not enough signal yet (e.g. right at meeting start)

It also runs an **adaptive reliability check**: if the calendar-provided candidate
name doesn't match *any* participant well, that's evidence the metadata itself
is wrong (typo, wrong invite) -- so the name signal is automatically down-weighted
for that session, and a note is surfaced explaining why.

## Running it

```bash
cd sherlock_prototype
python3 main.py
```

No dependencies are required for the default (heuristic) mode. To use the real
LLM-based transcript classifier instead of the keyword heuristic:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here
python3 main.py
```

## What's simulated vs. what's real here

This prototype's **fusion engine, signal extractors, and decision logic are
real and fully functional.** What's simulated is the meeting itself:
`simulator.py` stands in for a live Google Meet / Teams / Zoom bot, replaying a
realistic interview timeline (including the "joins as MacBook Pro," "renames
mid-call," "interviewer roster has a no-show," and "silent observer" edge
cases named in the brief) instead of pulling from a real meeting SDK.

This was a deliberate scope decision given the timeline: building/authenticating
three separate platform integrations (Meet, Teams, Zoom) is a multi-week
project on its own and would come at the direct expense of the actual
intellectual content of the challenge -- the fusion/reasoning engine. The
signal extraction and fusion layers are written against the same `Participant`
/ `Utterance` data model that a real integration would populate, so swapping
`simulator.py` for a real ingestion layer (see "Path to production" below)
requires no changes to `fusion.py` or `signals.py`.

## Path to production

1. **Ingestion**: Use a unified meeting-bot API (e.g. Recall.ai) to get one
   consistent event/media interface across Meet, Teams, and Zoom instead of
   three separate SDK integrations.
2. **Real-time loop**: Call `fusion.evaluate()` on every new transcript
   utterance or speaking-activity event (event-driven), not just on a fixed
   timer, so confidence updates the instant new evidence arrives.
3. **Face verification (fraud-specific)**: If a reference photo is available
   (LinkedIn, ID upload during scheduling), add a face-embedding-similarity
   signal (e.g. ArcFace) comparing webcam frames to the reference. This is
   the single strongest possible signal and doubles as impersonation/deepfake
   detection -- directly useful to Sherlock's core product.
4. **Screen-share content**: Replace the placeholder screen-share signal with
   real OCR/vision classification (resume/IDE = candidate-like; slide deck/
   scorecard = interviewer-like).
5. **Learning loop**: Log the full feature vector (all signal values) per
   interview alongside the human-confirmed candidate identity after the call.
   Periodically retrain the fixed weights in `fusion.py` as a small logistic
   regression over that feature vector -- same explanation trail, learned
   coefficients instead of hand-tuned ones.
6. **Downstream hookup**: Once `status == IDENTIFIED`, route that
   participant's audio/video stream to the deepfake/voice-clone/behavioral
   detectors. If confidence later drops or flips (e.g. a name change reveals
   a misidentification), re-route automatically.

## Assumptions

- `participant_id` is stable for the duration of the call even if the display
  name changes (true for Meet/Teams/Zoom -- the platform ID persists).
- Speaker-attributed transcript is available in near-real time.
- Calendar metadata (candidate name/email, interviewer names) is available
  but is treated as *unverified* -- the whole point of several signals is to
  work correctly even when it's wrong or incomplete.
- Company email domain is known when checking internal vs. external
  participants; this signal is skipped gracefully when it isn't.

## Files

- `models.py` -- data structures (Participant, Utterance, CandidateMetadata)
- `signals.py` -- the seven weak-signal extractors
- `fusion.py` -- combines signals into probability + decision + explanation
- `simulator.py` -- mock meeting timeline exercising the named edge cases
- `main.py` -- runs the simulation and prints a live confidence report
- `ARCHITECTURE.md` -- system diagram and component breakdown
- `EVALUATION.md` -- testing approach, edge cases covered, limitations
