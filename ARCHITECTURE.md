# Architecture

```mermaid
flowchart TD
    A["Meeting Platform: Meet / Teams / Zoom"] --> B["Event Ingestion Layer"]
    B --> B1["Join, leave, and rename events"]
    B --> B2["Per-participant audio and speaking activity"]
    B --> B3["Speaker-attributed transcript"]
    B --> B4["Screen-share events"]
    B --> B5["Calendar metadata: name, email, interviewers, domain"]

    subgraph SIG["Signal Extraction Layer"]
        C1["name_match"]
        C2["interviewer_roster"]
        C3["meeting_host"]
        C4["email_domain"]
        C5["speaking_pattern"]
        C6["transcript_semantics"]
        C7["screen_share"]
    end

    B1 --> C1
    B1 --> C2
    B1 --> C3
    B2 --> C5
    B3 --> C6
    B4 --> C7
    B5 --> C1
    B5 --> C2
    B5 --> C4

    C1 --> D["Fusion and Belief Engine"]
    C2 --> D
    C3 --> D
    C4 --> D
    C5 --> D
    C6 --> D
    C7 --> D

    D --> D1["Adaptive reliability check"]
    D --> D2["Weighted evidence sum, then softmax"]
    D --> D3["Decision: IDENTIFIED, AMBIGUOUS, or GATHERING EVIDENCE"]

    D3 --> E["Live Confidence and Explanation Output"]
    E --> F["Downstream fraud detectors: deepfake, voice clone, behavioral"]
```

## Why this shape

**Signals are independent and additive.** Each signal function only needs to
know about the participant it's scoring plus the shared calendar metadata --
it never talks to other signals. That means adding, removing, or reweighting
a signal is a one-line change in `fusion.py`, and a bad/failing signal (e.g.
an LLM API outage) degrades gracefully instead of breaking the pipeline.

**Fusion is transparent by construction.** Using a weighted linear combination
+ softmax (instead of, say, a black-box neural classifier) means every
probability the system reports comes with a full, human-readable trace of
which evidence produced it. That directly serves the challenge's
explainability requirement, and it's the same design pattern production
fraud/trust systems use precisely because auditability matters as much as
accuracy.

**The engine treats external metadata as evidence, not ground truth.** The
calendar invite is just another (fallible) input. The adaptive reliability
check explicitly detects when that input looks wrong (no participant matches
the given candidate name) and compensates by leaning harder on behavioral and
transcript evidence -- rather than either blindly trusting a wrong name or
crashing/refusing to proceed.

**Decisions default to uncertainty, not force.** `fusion.evaluate()` has three
outcomes, not two -- `AMBIGUOUS` and `GATHERING_EVIDENCE` are first-class
results, not error states. A system that must always output "the candidate is
X" will eventually output a confidently wrong answer; a system that can say
"not sure yet" is safer for a fraud-detection product where the downstream
consequence of misidentifying the candidate is analyzing the wrong person's
video for deepfakes.

## Component responsibilities

| Component | Responsibility | Real-world equivalent |
|---|---|---|
| Event Ingestion | Normalize platform-specific events into one schema | Recall.ai / native Meet-Teams-Zoom SDKs |
| Signal Extraction | Turn raw evidence into bounded, explainable scores | Independent scoring microservices/functions |
| Fusion/Belief Engine | Combine signals, track reliability, decide | Central reasoning service, re-run per event or on a timer |
| Output | Confidence + reasoning trace | Dashboard API consumed by ops UI and by the fraud detectors themselves |
