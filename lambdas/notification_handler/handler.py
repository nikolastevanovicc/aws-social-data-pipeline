import json
import os
import urllib.error
import urllib.request


def get_discord_webhook_url() -> str:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL environment variable is not set.")

    return webhook_url


def extract_sns_messages(event: dict) -> list[dict]:
    messages = []

    records = event.get("Records", [])

    if not isinstance(records, list):
        return messages

    for record in records:
        sns = record.get("Sns", {})

        if not isinstance(sns, dict):
            continue

        raw_message = sns.get("Message")

        if not raw_message:
            continue

        try:
            parsed_message = json.loads(raw_message)
        except json.JSONDecodeError:
            parsed_message = {
                "raw_message": raw_message,
            }

        messages.append(parsed_message)

    return messages


def format_alarm_message(message: dict) -> str:
    alarm_name = message.get("AlarmName", "Unknown alarm")
    new_state = message.get("NewStateValue", "UNKNOWN")
    reason = message.get("NewStateReason", "No reason provided")
    region = message.get("Region", "Unknown region")
    state_change_time = message.get("StateChangeTime", "Unknown time")

    trigger = message.get("Trigger", {})
    metric_name = trigger.get("MetricName", "Unknown metric") if isinstance(trigger, dict) else "Unknown metric"
    namespace = trigger.get("Namespace", "Unknown namespace") if isinstance(trigger, dict) else "Unknown namespace"

    return (
        "**AWS Pipeline Alert**\n\n"
        f"**Alarm:** {alarm_name}\n"
        f"**State:** {new_state}\n"
        f"**Metric:** {namespace}/{metric_name}\n"
        f"**Region:** {region}\n"
        f"**Time:** {state_change_time}\n\n"
        f"**Reason:** {reason}"
    )


def send_discord_message(webhook_url: str, content: str) -> None:
    payload = {
        "content": content,
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "aws-social-data-pipeline-notifier/1.0"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(f"Discord webhook response status: {response.status}")

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"Discord HTTP error: {exc.code} {error_body}")
        raise

    except urllib.error.URLError as exc:
        print(f"Discord URL error: {exc}")
        raise


def lambda_handler(event, context):
    print("Received notification event:")
    print(json.dumps(event))

    webhook_url = get_discord_webhook_url()

    messages = extract_sns_messages(event)

    if not messages:
        print("No SNS messages found in event.")
        return {
            "status": "no_messages",
            "messages_sent": 0,
            "request_id": getattr(context, "aws_request_id", None),
        }

    sent_count = 0

    for message in messages:
        discord_message = format_alarm_message(message)
        send_discord_message(webhook_url, discord_message)
        sent_count += 1

    return {
        "status": "success",
        "messages_sent": sent_count,
        "request_id": getattr(context, "aws_request_id", None),
    }