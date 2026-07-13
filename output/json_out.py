"""
Structured JSON output mode (--json flag).
Serializes DiagnosisResult to a JSON object for scripting / Slack integration.
"""
import dataclasses
import json
import sys

from core.prompts import DiagnosisResult


def print_json(result: DiagnosisResult) -> None:
    """Print DiagnosisResult as pretty JSON to stdout."""
    data = dataclasses.asdict(result)
    json.dump(data, sys.stdout, indent=2)
    print()  # trailing newline
