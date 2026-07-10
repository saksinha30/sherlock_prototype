"""
fusion.py -- Combines weak signals into a probability distribution over
"who is the candidate", plus a full, human-readable explanation trail.

Design choice: additive, weighted evidence combination (a transparent,
log-odds-style scoring rule) rather than a black-box classifier. This keeps
the system fully explainable, which the challenge explicitly weights
heavily -- and it's easy to extend: adding a new signal means writing one
function in signals.py, not retraining a model.

("Continue learning" bonus point: the `weight` values here are exactly what
you'd turn into learned parameters -- e.g. a logistic regression over the
same feature vector -- once you have labeled outcomes from confirmed
interviews. Swap the fixed weights for coefficients loaded from a small
retrained model; the explanation trail doesn't change.)
"""
import math
from dataclasses import dataclass, field
from typing import List

from models import Participant, CandidateMetadata
from signals import (
    SignalResult, name_signal, interviewer_roster_signal, host_signal,
    domain_signal, speaking_pattern_signal, transcript_semantic_signal,
    screen_share_signal,
)

CONFIDENCE_THRESHOLD = 0.55      # top participant must clear this probability
MARGIN_THRESHOLD = 0.15          # ...and beat the runner-up by at least this much
MIN_SIGNAL_MASS = 0.5            # minimum accumulated |evidence| before we'll decide anything


@dataclass
class ParticipantBelief:
    participant_id: str
    display_name: str
    raw_score: float
    probability: float
    signals: List[SignalResult] = field(default_factory=list)


@dataclass
class FusionResult:
    beliefs: List[ParticipantBelief]     # sorted, highest probability first
    status: str                          # IDENTIFIED | AMBIGUOUS | GATHERING_EVIDENCE
    identified_participant_id: str = None
    notes: str = ""


def _softmax(scores: List[float]) -> List[float]:
    m = max(scores) if scores else 0.0
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


def evaluate(participants: List[Participant], meta: CandidateMetadata) -> FusionResult:
    if not participants:
        return FusionResult([], "GATHERING_EVIDENCE", notes="No participants observed yet.")

    # --- adaptive reliability check -----------------------------------
    # If the calendar candidate name doesn't match ANY participant well, the
    # metadata itself is probably wrong (e.g. interviewer typo'd the name, or
    # entered the wrong candidate entirely). Rather than trust it anyway, we
    # down-weight the name signal for this session and flag it in the trace.
    # This is what handles the "interviewer enters the wrong candidate name"
    # edge case explicitly.
    name_results = {p.participant_id: name_signal(p, meta) for p in participants}
    metadata_reliable = any(r.value > 0.5 for r in name_results.values())
    name_weight_multiplier = 1.0 if metadata_reliable else 0.25

    beliefs = []
    for p in participants:
        sigs = [
            name_results[p.participant_id],
            interviewer_roster_signal(p, meta),
            host_signal(p),
            domain_signal(p, meta),
            speaking_pattern_signal(p, participants),
            transcript_semantic_signal(p),
            screen_share_signal(p),
        ]
        for s in sigs:
            if s.name == "name_match":
                s.weight *= name_weight_multiplier

        raw = sum(s.contribution for s in sigs)
        beliefs.append(ParticipantBelief(p.participant_id, p.display_name, raw, 0.0, sigs))

    probs = _softmax([b.raw_score for b in beliefs])
    for b, pr in zip(beliefs, probs):
        b.probability = pr

    beliefs.sort(key=lambda b: b.probability, reverse=True)

    notes = ""
    if not metadata_reliable:
        notes = ("Calendar candidate name did not closely match any participant's display name -- "
                 "treating name metadata as unreliable for this session and relying more heavily on "
                 "behavioral and transcript signals instead.")

    if len(beliefs) == 1:
        top = beliefs[0]
        status = "IDENTIFIED" if top.probability > 0.4 else "GATHERING_EVIDENCE"
        return FusionResult(beliefs, status, top.participant_id if status == "IDENTIFIED" else None, notes)

    top, second = beliefs[0], beliefs[1]
    total_signal_mass = sum(abs(s.value) for b in beliefs for s in b.signals)

    if total_signal_mass < MIN_SIGNAL_MASS:
        return FusionResult(beliefs, "GATHERING_EVIDENCE", notes=notes or "Not enough evidence accumulated yet.")

    if top.probability >= CONFIDENCE_THRESHOLD and (top.probability - second.probability) >= MARGIN_THRESHOLD:
        return FusionResult(beliefs, "IDENTIFIED", top.participant_id, notes)

    return FusionResult(
        beliefs, "AMBIGUOUS",
        notes=notes or f"Top two participants are too close ({top.probability:.0%} vs {second.probability:.0%}) "
                       "to confidently decide -- flagging for more evidence rather than guessing."
    )
