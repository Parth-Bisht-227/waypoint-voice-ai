"""Print a concise summary of one Waypoint session report."""

from __future__ import annotations

import argparse
import ast
import json
import math
from pathlib import Path
from typing import Any


REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]

    return ordered[lower] + (
        (ordered[upper] - ordered[lower]) * (position - lower)
    )


def _metric_line(label: str, values: list[float]) -> str:
    if not values:
        return f"{label}: n=0"

    return (
        f"{label}: n={len(values)} "
        f"p50={_percentile(values, 0.5):.3f}s "
        f"p95={_percentile(values, 0.95):.3f}s "
        f"max={max(values):.3f}s"
    )


def _metric_values(messages: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for message in messages:
        value = message.get("metrics", {}).get(key)
        if value is not None:
            values.append(float(value))
    return values


def _tool_lines(items: list[dict[str, Any]]) -> tuple[list[str], str]:
    outputs = {
        item.get("call_id"): item
        for item in items
        if item.get("type") == "function_call_output"
    }
    lines = []
    mutation = "not requested"

    calls = [item for item in items if item.get("type") == "function_call"]
    for index, call in enumerate(calls, start=1):
        output = outputs.get(call.get("call_id"))
        if output is None:
            status = "missing output"
            duration = ""
        else:
            status = "error" if output.get("is_error") else "ok"
            elapsed = float(output.get("created_at", 0)) - float(
                call.get("created_at", 0)
            )
            duration = f" {max(elapsed, 0):.3f}s"

        name = str(call.get("name", "unknown_tool"))
        lines.append(f"{index}. {name}: {status}{duration}")

        if name == "apply_pending_travel_date_change":
            mutation = "failed" if status != "ok" else "succeeded"
            if output and not output.get("is_error"):
                try:
                    payload = ast.literal_eval(str(output.get("output", "")))
                except (SyntaxError, ValueError):
                    payload = None
                if isinstance(payload, dict) and "changed" in payload:
                    mutation += f" (changed={str(payload['changed']).lower()})"

    return lines or ["none"], mutation


def summarize_report(report: dict[str, Any], source: Path) -> str:
    """Return a transcript-free summary for one report."""

    events = list(report.get("events", []))
    items = list(report.get("chat_history", {}).get("items", []))
    user_messages = [
        item
        for item in items
        if item.get("type") == "message" and item.get("role") == "user"
    ]
    assistant_messages = [
        item
        for item in items
        if item.get("type") == "message" and item.get("role") == "assistant"
    ]

    created_times = [
        float(event["created_at"])
        for event in events
        if event.get("created_at") is not None
    ]
    close_event = next(
        (event for event in reversed(events) if event.get("type") == "close"),
        {},
    )
    duration = (
        max(created_times) - min(created_times) if len(created_times) >= 2 else 0
    )

    tool_lines, mutation = _tool_lines(items)

    error_groups: dict[tuple[str, str], list[int]] = {}
    for event in events:
        if event.get("type") != "error":
            continue
        source_info = event.get("source", {})
        error = event.get("error", {})
        key = (
            str(source_info.get("provider", "unknown provider")),
            str(source_info.get("model", error.get("label", "unknown model"))),
        )
        counts = error_groups.setdefault(key, [0, 0])
        counts[0 if error.get("recoverable") else 1] += 1

    lines = [
        f"Report: {source.resolve()}",
        f"Room: {report.get('room', 'unknown')}",
        f"Duration: {duration:.1f}s",
        (
            "Conversation: "
            f"user_turns={len(user_messages)} "
            f"assistant_turns={len(assistant_messages)} "
            f"assistant_interruptions="
            f"{sum(bool(item.get('interrupted')) for item in assistant_messages)}"
        ),
        "",
        "Latency",
        _metric_line(
            "STT transcription delay",
            _metric_values(user_messages, "transcription_delay"),
        ),
        _metric_line(
            "End-of-turn delay",
            _metric_values(user_messages, "end_of_turn_delay"),
        ),
        _metric_line(
            "LLM TTFT",
            _metric_values(assistant_messages, "llm_node_ttft"),
        ),
        _metric_line(
            "TTS TTFB",
            _metric_values(assistant_messages, "tts_node_ttfb"),
        ),
        _metric_line(
            "E2E latency",
            _metric_values(assistant_messages, "e2e_latency"),
        ),
        "",
        "Tools",
        *tool_lines,
        f"Mutation: {mutation}",
        "",
        "Provider errors",
    ]

    if error_groups:
        for (provider, model), (recoverable, terminal) in sorted(
            error_groups.items()
        ):
            lines.append(
                f"{provider} / {model}: "
                f"retryable={recoverable} terminal={terminal}"
            )
    else:
        lines.append("none")

    lines.extend(["", "Usage"])
    usage = list(report.get("usage", []))
    if not usage:
        lines.append("none")
    for item in usage:
        provider = item.get("provider", "unknown provider")
        model = item.get("model", "unknown model")
        if "characters_count" in item:
            lines.append(
                f"{provider} / {model}: characters={item['characters_count']} "
                f"audio={float(item.get('audio_duration', 0)):.2f}s"
            )
        elif "audio_duration" in item and not item.get("input_tokens"):
            lines.append(
                f"{provider} / {model}: "
                f"audio={float(item.get('audio_duration', 0)):.2f}s"
            )
        else:
            lines.append(
                f"{provider} / {model}: input_tokens={item.get('input_tokens', 0)} "
                f"output_tokens={item.get('output_tokens', 0)}"
            )

    lines.extend(
        [
            "",
            f"Shutdown: {close_event.get('reason', 'unknown')}",
        ]
    )
    return "\n".join(lines)


def _latest_report() -> Path:
    reports = sorted(
        REPORTS_DIR.glob("session-*.json"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    if not reports:
        raise FileNotFoundError(f"No session reports found in {REPORTS_DIR}")
    return reports[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize one Waypoint session report without transcript text."
    )
    parser.add_argument("report", nargs="?", type=Path)
    parser.add_argument(
        "--latest",
        action="store_true",
        help="summarize the newest report in observability/reports",
    )
    args = parser.parse_args()

    if args.latest and args.report:
        parser.error("use either --latest or a report path, not both")

    report_path = _latest_report() if args.latest or not args.report else args.report
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(summarize_report(report, report_path))


if __name__ == "__main__":
    main()
