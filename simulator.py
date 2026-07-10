"""
simulator.py -- Stand-in for a real meeting-bot integration (e.g. Recall.ai,
or native Zoom/Meet/Teams SDKs). Produces a believable multi-participant
interview timeline so the fusion engine can be exercised end-to-end without
needing live meeting infrastructure for this prototype.

The scenario deliberately exercises several edge cases named in the brief:
  - candidate joins with a device name ("MacBook Pro")           [tick 0-1]
  - candidate later changes display name to a nickname mid-call  [tick 2]
  - calendar lists two interviewer names but only one attends    (Priya never joins)
  - a silent, camera-off third-party observer is present throughout
"""
import time
from models import Participant, Utterance, CandidateMetadata

CANDIDATE_META = CandidateMetadata(
    candidate_name="Rahul Kumar",
    candidate_email="rahul.kumar@gmail.com",
    interviewer_names=["Sarah Chen", "Priya Singh"],   # Priya is on the invite but never joins
    company_email_domain="sherlock.sh",
)


def build_participants():
    interviewer = Participant(
        participant_id="P1", display_name="Sarah Chen",
        email="sarah.chen@sherlock.sh", is_host=True, webcam_on=True,
    )
    candidate = Participant(
        participant_id="P2", display_name="MacBook Pro",   # edge case: device name
        email="rahul.kumar@gmail.com", is_host=False, webcam_on=True,
    )
    observer = Participant(
        participant_id="P3", display_name="Amit S",
        email=None, is_host=False, webcam_on=False,          # camera off, silent throughout
    )
    return [interviewer, candidate, observer]


INTERVIEWER_LINES = [
    "Hi, thanks for joining -- can you walk me through your background?",
    "Great, can you tell me about a time you optimized a slow system?",
    "Let's move on to a system design question.",
    "Any questions for me before we wrap up?",
]

CANDIDATE_LINES = [
    "Sure, I worked on a computer vision pipeline for X-ray baggage screening at my last role.",
    "I built a YOLO-based detector and led the effort to distill it into a smaller student model.",
    "For that I'd start by profiling the bottleneck -- I implemented batching and caching.",
    "Yes, what does the day-to-day look like for this role?",
]

NAME_CHANGE_AT_TICK = 2   # candidate renames from "MacBook Pro" to "Rahul K" mid-call


def run_tick(t: int, participants):
    """Mutates participant state to simulate ~30s of additional meeting activity."""
    interviewer, candidate, observer = participants

    if t == NAME_CHANGE_AT_TICK:
        candidate.rename("Rahul K")

    if t < len(INTERVIEWER_LINES):
        line = INTERVIEWER_LINES[t]
        interviewer.utterances.append(Utterance(interviewer.participant_id, line, time.time()))
        interviewer.total_speaking_seconds += 8
        interviewer.turn_count += 1
        if "?" in line:
            interviewer.question_utterances += 1
        else:
            interviewer.statement_utterances += 1

    if t < len(CANDIDATE_LINES):
        line = CANDIDATE_LINES[t]
        candidate.utterances.append(Utterance(candidate.participant_id, line, time.time()))
        candidate.total_speaking_seconds += 22
        candidate.turn_count += 1
        if "?" in line:
            candidate.question_utterances += 1
        else:
            candidate.statement_utterances += 1

    # observer stays silent throughout -- webcam off, no utterances, no stat changes.
    return participants
