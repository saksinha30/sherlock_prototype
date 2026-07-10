"""
main.py -- Drives the simulated meeting through several ticks and prints the
fusion engine's evolving belief + explanation at each step, exactly like a
live dashboard would render it.

Run:  python3 main.py
Optional: export ANTHROPIC_API_KEY=... to use the real LLM transcript
          classifier instead of the built-in heuristic fallback.
"""
from simulator import build_participants, run_tick, CANDIDATE_META
from fusion import evaluate

TICKS = 4


def print_tick_report(t, result):
    print(f"\n{'=' * 78}")
    print(f"TICK {t}  (~{(t + 1) * 30}s into the interview)   STATUS = {result.status}")
    if result.notes:
        print(f"NOTE: {result.notes}")

    for b in result.beliefs:
        marker = "   <-- IDENTIFIED AS CANDIDATE" if b.participant_id == result.identified_participant_id else ""
        print(f"\n  {b.display_name:20s} P(candidate) = {b.probability:5.0%}   raw_score = {b.raw_score:+.2f}{marker}")
        for s in b.signals:
            print(f"      [{s.name:20s} val={s.value:+.2f} w={s.weight:.2f}]  {s.explanation}")


def main():
    participants = build_participants()
    result = None
    for t in range(TICKS):
        run_tick(t, participants)
        result = evaluate(participants, CANDIDATE_META)
        print_tick_report(t, result)

    print(f"\n{'=' * 78}")
    print("FINAL DECISION: ", end="")
    if result.identified_participant_id:
        winner = next(b for b in result.beliefs if b.participant_id == result.identified_participant_id)
        print(f"'{winner.display_name}' identified as CANDIDATE with {winner.probability:.0%} confidence.")
    else:
        print("Not confidently identified yet -- system correctly reports uncertainty rather than guessing.")


if __name__ == "__main__":
    main()
