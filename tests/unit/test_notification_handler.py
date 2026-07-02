import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest


HANDLER_PATH = (
    Path(__file__).resolve().parents[2]
    / "lambdas"
    / "notification_handler"
    / "handler.py"
)
SPEC = importlib.util.spec_from_file_location("notification_handler", HANDLER_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


class FakeContext:
    aws_request_id = "request-123"


def _sns_event(message):
    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "Sns": {
                    "Message": json.dumps(message)
                    if isinstance(message, dict)
                    else message
                },
            }
        ]
    }


def _alarm_message():
    return {
        "AlarmName": "hn-bronze-ingestion-errors",
        "NewStateValue": "ALARM",
        "NewStateReason": "Threshold Crossed: 1 datapoint was greater than threshold.",
        "Region": "EU (Frankfurt)",
        "StateChangeTime": "2026-07-02T10:15:00.000+0000",
        "Trigger": {
            "Namespace": "AWS/Lambda",
            "MetricName": "Errors",
        },
    }


def test_extract_sns_messages_parses_json_and_raw_messages():
    event = {
        "Records": [
            {"Sns": {"Message": json.dumps({"AlarmName": "pipeline-alarm"})}},
            {"Sns": {"Message": "plain text failure"}},
            {"Sns": {}},
            {"Sns": None},
        ]
    }

    messages = handler.extract_sns_messages(event)

    assert messages == [
        {"AlarmName": "pipeline-alarm"},
        {"raw_message": "plain text failure"},
    ]


def test_extract_sns_messages_ignores_non_list_records():
    assert handler.extract_sns_messages({"Records": "not-a-list"}) == []


def test_format_alarm_message_contains_alarm_details():
    formatted = handler.format_alarm_message(_alarm_message())

    assert "**AWS Pipeline Alert**" in formatted
    assert "**Alarm:** hn-bronze-ingestion-errors" in formatted
    assert "**State:** ALARM" in formatted
    assert "**Metric:** AWS/Lambda/Errors" in formatted
    assert "**Region:** EU (Frankfurt)" in formatted
    assert "**Time:** 2026-07-02T10:15:00.000+0000" in formatted
    assert "Threshold Crossed" in formatted


def test_lambda_handler_sends_one_discord_message_for_valid_sns_event(monkeypatch):
    sent_messages = []
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setattr(
        handler,
        "send_discord_message",
        lambda webhook_url, content: sent_messages.append((webhook_url, content)),
    )

    response = handler.lambda_handler(_sns_event(_alarm_message()), FakeContext())

    assert response == {
        "status": "success",
        "messages_sent": 1,
        "request_id": "request-123",
    }
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "https://example.com/webhook"
    assert "hn-bronze-ingestion-errors" in sent_messages[0][1]


def test_lambda_handler_handles_no_records_without_sending(monkeypatch):
    send_calls = []
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setattr(
        handler,
        "send_discord_message",
        lambda webhook_url, content: send_calls.append((webhook_url, content)),
    )

    response = handler.lambda_handler({}, FakeContext())

    assert response == {
        "status": "no_messages",
        "messages_sent": 0,
        "request_id": "request-123",
    }
    assert send_calls == []


def test_send_discord_message_reraises_url_errors(monkeypatch):
    def raise_url_error(request, timeout):
        raise urllib.error.URLError("network unavailable")

    monkeypatch.setattr(handler.urllib.request, "urlopen", raise_url_error)

    with pytest.raises(urllib.error.URLError):
        handler.send_discord_message("https://example.com/webhook", "content")
