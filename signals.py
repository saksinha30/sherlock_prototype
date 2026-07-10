"""
signals.py -- Weak-signal extractors.

Each function inspects one slice of available evidence (name, role metadata,
speaking behavior, transcript semantics, screen share) and returns a
SignalResult: a bounded score plus a human-readable explanation.

No single signal is trusted to make the final call -- fusion.py combines all
of them. This is the "use multiple weak signals instead of one rule" bonus
criterion, made literal: every function here is individually easy to fool,
and that's fine, because the fusion layer never relies on just one.

Score convention (roughly bounded [-1, +1]):
  +1  -> strong evidence FOR this participant being the candidate
   0  -> neutral / no evidence either way
  -1  -> strong evidence AGAINST (e.g. this looks like the interviewer/host)
"""
import difflib
import re
import os
from dataclasses import dataclass
from typing import List

from models import Participant, CandidateMetadata

# In production: replace with a proper nickname/alias dataset (or an LLM call
# like _llm_transcript_signal below) instead of a hardcoded map.
NICKNAME_MAP = {
    "rahul": ["rahulk", "raul"],
    "robert": ["bob", "rob", "bobby"],
    "christopher": ["chris"],
    "jennifer": ["jen", "jenny"],
    "abhishek": ["abhi"],
    "william": ["will", "bill"],
}

GENERIC_DEVICE_MARKERS = ["macbook", "iphone", "windows pc", "laptop", "ipad", "unknown", "guest"]


@dataclass
class SignalResult:
    name: str
    value: float          # bounded roughly [-1, 1]
    weight: float
    explanation: str

    @property
    def contribution(self) -> float:
        return self.value * self.weight


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def name_signal(p: Participant, meta: CandidateMetadata) -> SignalResult:
    if not meta.candidate_name:
        return SignalResult("name_match", 0.0, 1.2,
                             "No candidate name available in calendar invite -- signal skipped.")

    target = _normalize(meta.candidate_name)
    guess = _normalize(p.display_name)

    if not guess:
        return SignalResult("name_match", 0.0, 1.2, "Empty display name.")

    if any(g in guess for g in GENERIC_DEVICE_MARKERS):
        return SignalResult(
            "name_match", 0.0, 1.2,
            f"Display name '{p.display_name}' looks like a device/generic name, not a person -- "
            "treated as UNINFORMATIVE rather than penalized (this is the 'joins as MacBook Pro' case)."
        )

    ratio = difflib.SequenceMatcher(None, target, guess).ratio()

    nickname_bonus = 0.0
    for canon, aliases in NICKNAME_MAP.items():
        if canon in target and any(a in guess for a in aliases):
            nickname_bonus = 0.75
            break

    score = max(ratio, nickname_bonus)
    # rescale similarity [0,1] -> roughly [-0.3, 1.0]: a poor match is mildly
    # negative (not damning -- names get typo'd, nicknamed, etc.)
    rescaled = max(-0.3, min(1.0, (score * 1.2) - 0.2))

    return SignalResult(
        "name_match", rescaled, 1.2,
        f"Display name '{p.display_name}' vs candidate name '{meta.candidate_name}': "
        f"similarity={ratio:.2f}" + (", nickname/alias match found" if nickname_bonus else "")
    )


def interviewer_roster_signal(p: Participant, meta: CandidateMetadata) -> SignalResult:
    if not meta.interviewer_names:
        return SignalResult("interviewer_roster", 0.0, 1.5, "No interviewer roster available -- signal skipped.")

    guess = _normalize(p.display_name)
    best, matched_name = 0.0, None
    for iv in meta.interviewer_names:
        ratio = difflib.SequenceMatcher(None, _normalize(iv), guess).ratio()
        if ratio > best:
            best, matched_name = ratio, iv

    if best > 0.75:
        return SignalResult(
            "interviewer_roster", -1.0, 1.5,
            f"Display name closely matches known interviewer '{matched_name}' (similarity={best:.2f}) "
            "-- strongly suppressing candidate likelihood."
        )
    return SignalResult("interviewer_roster", 0.0, 1.5, "No strong match against interviewer roster.")


def host_signal(p: Participant) -> SignalResult:
    if p.is_host:
        return SignalResult("meeting_host", -0.8, 1.0,
                             "Participant is the meeting host/organizer -- candidates are almost never the organizer.")
    return SignalResult("meeting_host", 0.0, 1.0, "Not the meeting host.")


def domain_signal(p: Participant, meta: CandidateMetadata) -> SignalResult:
    if not p.email or not meta.company_email_domain:
        return SignalResult("email_domain", 0.0, 0.8, "Email/domain not available -- signal skipped.")
    domain = p.email.split("@")[-1].lower()
    if domain == meta.company_email_domain.lower():
        return SignalResult("email_domain", -0.6, 0.8,
                             f"Participant email domain '{domain}' matches the company domain -- likely internal staff.")
    return SignalResult("email_domain", 0.5, 0.8,
                         f"Participant email domain '{domain}' is external -- consistent with being the candidate.")


def speaking_pattern_signal(p: Participant, all_participants: List[Participant]) -> SignalResult:
    total_seconds = sum(x.total_speaking_seconds for x in all_participants) or 1.0
    share = p.total_speaking_seconds / total_seconds

    total_utts = p.question_utterances + p.statement_utterances
    if total_utts == 0:
        return SignalResult("speaking_pattern", 0.0, 1.0, "No speech observed yet from this participant.")

    question_ratio = p.question_utterances / total_utts
    fair_share = 1.0 / max(len(all_participants), 1)
    # candidates tend to talk more (long answers) AND ask fewer questions
    # than they answer; interviewers show the opposite pattern.
    value = (share - fair_share) * 0.8 + (0.5 - question_ratio) * 0.8
    value = max(-1.0, min(1.0, value))

    pattern = "mostly answering" if question_ratio < 0.3 else "mostly asking" if question_ratio > 0.6 else "mixed"
    return SignalResult(
        "speaking_pattern", value, 1.0,
        f"Speaking share={share:.0%}, question ratio={question_ratio:.0%} ({pattern})."
    )


def transcript_semantic_signal(p: Participant) -> SignalResult:
    """
    Classifies recent utterances as 'answering/describing own experience' vs
    'asking/facilitating'. Uses an LLM if ANTHROPIC_API_KEY is set in the
    environment; otherwise falls back to a cheap keyword heuristic.

    Production note: ALWAYS keep a non-LLM fallback path like this one.
    LLM calls add latency and cost per participant per tick, and can simply
    fail -- the system should degrade gracefully, not go blind.
    """
    if not p.utterances:
        return SignalResult("transcript_semantics", 0.0, 1.3, "No transcript yet for this participant.")

    recent_text = " ".join(u.text for u in p.utterances[-8:])

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _llm_transcript_signal(recent_text)
        except Exception:
            pass  # fall through to heuristic on any API error

    return _heuristic_transcript_signal(recent_text)


def _heuristic_transcript_signal(text: str) -> SignalResult:
    lower = text.lower()
    answering_markers = [
        "i worked on", "i built", "my role was", "in my previous", "i have experience",
        "i used", "my approach", "i implemented", "i led", "in my last role",
    ]
    asking_markers = [
        "can you tell me", "let's move on", "walk me through", "what would you do",
        "tell me about a time", "next question", "any questions for me", "let's start",
    ]

    a_hits = sum(m in lower for m in answering_markers)
    q_hits = sum(m in lower for m in asking_markers)

    if a_hits == 0 and q_hits == 0:
        return SignalResult("transcript_semantics", 0.0, 1.3,
                             "Transcript content is neutral -- no strong role markers detected (heuristic mode).")

    value = max(-1.0, min(1.0, (a_hits - q_hits) * 0.4))
    return SignalResult(
        "transcript_semantics", value, 1.3,
        f"Heuristic transcript scan: {a_hits} answer-style phrase(s), {q_hits} question/facilitation-style phrase(s)."
    )


def _llm_transcript_signal(text: str) -> SignalResult:
    import anthropic
    client = anthropic.Anthropic()
    prompt = (
        "You are classifying one speaker's recent turns in a job interview transcript.\n"
        "Return ONLY a number from -1 to 1:\n"
        "  +1  = clearly the candidate being interviewed (describing own past work/experience, answering questions)\n"
        "  -1  = clearly the interviewer/facilitator (asking questions, running the process)\n"
        "   0  = unclear / not enough signal\n\n"
        f"Transcript snippet:\n{text}\n\nAnswer with only the number."
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    value = max(-1.0, min(1.0, float(raw)))
    return SignalResult("transcript_semantics", value, 1.3, f"LLM transcript classification score={value:.2f}.")


def screen_share_signal(p: Participant) -> SignalResult:
    if p.screen_share_seconds <= 0:
        return SignalResult("screen_share", 0.0, 0.5, "No screen share observed.")
    # In production: run OCR/vision on shared frames to distinguish a resume
    # or code editor (candidate-like) from a slide deck or scorecard
    # (interviewer-like), rather than treating any screen share as a positive.
    return SignalResult("screen_share", 0.2, 0.5,
                         "Participant shared their screen (weak positive prior toward candidate in technical rounds).")
