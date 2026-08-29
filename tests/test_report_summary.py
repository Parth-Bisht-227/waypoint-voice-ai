from pathlib import Path

from observability.summarize_reports import summarize_report


def test_summary_reports_metrics_without_transcript_text(tmp_path: Path) -> None:
    report = {
        "room": "test-room",
        "events": [
            {"type": "agent_state_changed", "created_at": 10.0},
            {
                "type": "error",
                "created_at": 11.0,
                "source": {"provider": "groq", "model": "test-model"},
                "error": {"recoverable": True},
            },
            {
                "type": "error",
                "created_at": 12.0,
                "source": {"provider": "groq", "model": "test-model"},
                "error": {"recoverable": False},
            },
            {
                "type": "close",
                "created_at": 20.0,
                "reason": "participant_disconnected",
            },
        ],
        "chat_history": {
            "items": [
                {
                    "type": "message",
                    "role": "user",
                    "content": ["private caller text"],
                    "metrics": {
                        "transcription_delay": 0.1,
                        "end_of_turn_delay": 0.2,
                    },
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": ["private assistant text"],
                    "interrupted": True,
                    "metrics": {
                        "llm_node_ttft": 0.3,
                        "tts_node_ttfb": 0.4,
                        "e2e_latency": 0.5,
                    },
                },
                {
                    "type": "function_call",
                    "name": "apply_pending_travel_date_change",
                    "call_id": "call-1",
                    "created_at": 13.0,
                },
                {
                    "type": "function_call_output",
                    "name": "apply_pending_travel_date_change",
                    "call_id": "call-1",
                    "created_at": 13.05,
                    "is_error": False,
                    "output": "{'changed': True}",
                },
            ]
        },
        "usage": [
            {
                "provider": "groq",
                "model": "test-model",
                "input_tokens": 100,
                "output_tokens": 20,
            }
        ],
    }

    summary = summarize_report(report, tmp_path / "report.json")

    assert "E2E latency: n=1 p50=0.500s p95=0.500s max=0.500s" in summary
    assert "apply_pending_travel_date_change: ok 0.050s" in summary
    assert "Mutation: succeeded (changed=true)" in summary
    assert "groq / test-model: retryable=1 terminal=1" in summary
    assert "Shutdown: participant_disconnected" in summary
    assert "private caller text" not in summary
    assert "private assistant text" not in summary
