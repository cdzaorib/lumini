"""Model-assisted understanding and wording, off by default (ADR-007, ADR-018).

Models never decide prices, times, rules or anything clinical. They receive only redacted text
and approved catalog facts; their output is checked before anyone sees it, and every failure
falls back to the deterministic flow or to the team.
"""
