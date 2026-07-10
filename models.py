"""
models.py -- Core data structures for the Sherlock candidate-identification prototype.

These are intentionally simple, serializable dataclasses. In production these
would be populated by a real meeting-bot integration (Recall.ai, or native
Zoom/Meet/Teams SDKs) instead of the Simulator used in this prototype.

Design note: `participant_id` is the ONE stable identifier we ever key on.
Display names are treated as untrusted, mutable evidence -- never as an
identity key -- because candidates rename themselves mid-call, join as
"MacBook Pro", etc.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Utterance:
    speaker_id: str
    text: str
    timestamp: float


@dataclass
class Participant:
    participant_id: str          # stable ID assigned at join time -- never changes
    display_name: str
    email: Optional[str] = None       # only sometimes available (SSO participants)
    is_host: bool = False
    webcam_on: bool = False
    joined_at: float = 0.0
    left_at: Optional[float] = None

    # running stats, updated every tick by the simulator / real ingestion layer
    total_speaking_seconds: float = 0.0
    turn_count: int = 0
    question_utterances: int = 0
    statement_utterances: int = 0
    screen_share_seconds: float = 0.0
    utterances: List[Utterance] = field(default_factory=list)
    name_history: List[str] = field(default_factory=list)

    def rename(self, new_name: str):
        self.name_history.append(self.display_name)
        self.display_name = new_name


@dataclass
class CandidateMetadata:
    """External metadata pulled from the ATS / calendar invite.

    Treated as UNVERIFIED evidence, not ground truth -- it can be wrong
    (wrong name entered, stale invite, interviewer typo), so the fusion
    engine never trusts it blindly. See fusion.evaluate()'s adaptive
    reliability check.
    """
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    interviewer_names: List[str] = field(default_factory=list)
    company_email_domain: Optional[str] = None
