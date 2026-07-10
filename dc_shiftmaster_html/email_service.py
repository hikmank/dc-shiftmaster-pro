"""Email notification service for DC-ShiftMaster Pro.

Sends coverage event email notifications via AWS SES. Emails are dispatched
in background daemon threads to avoid blocking HTTP request handling.
"""

import logging
import os
import threading

import boto3
from botocore.exceptions import ClientError

from dc_shiftmaster.database import DatabaseManager

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """Return True if email has exactly one '@' with non-empty local and domain parts."""
    parts = email.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts
    return len(local) > 0 and len(domain) > 0


def _build_email_body(event_type: str, coverage_request, requester, claimer=None) -> tuple[str, str]:
    """Return (subject, body) for the given event type and request details."""
    if event_type == "created":
        subject = f"[ShiftMaster] New Coverage Request from {requester.display_name}"
        body = (
            f"{requester.display_name} needs coverage for the "
            f"{coverage_request.shift_type} shift on {coverage_request.date}."
        )
        if coverage_request.note:
            body += f"\n\nNote: {coverage_request.note}"
        return subject, body

    if event_type == "claimed":
        subject = "[ShiftMaster] Your Coverage Request Was Claimed"
        claimer_name = claimer.display_name if claimer else "Someone"
        body = (
            f"{claimer_name} has claimed your "
            f"{coverage_request.shift_type} shift on {coverage_request.date}."
        )
        return subject, body

    return "", ""


def _send_ses_email(recipient_email: str, subject: str, body: str) -> None:
    """Send a single email via SES. Called in a background thread.

    Reads SES_SENDER_EMAIL and SES_AWS_REGION from environment.
    Logs errors without raising.
    """
    sender = os.environ.get("SES_SENDER_EMAIL", "")
    region = os.environ.get("SES_AWS_REGION", "us-east-1")

    try:
        client = boto3.client("ses", region_name=region)
        client.send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except Exception:
        logger.exception("Failed to send email to %s", recipient_email)


def send_coverage_email(event_type: str, request_id: int, db: DatabaseManager) -> None:
    """Send email notifications for a coverage event.

    Determines the recipient set based on event_type, composes the email,
    and dispatches sending to background daemon threads.

    Args:
        event_type: "created" or "claimed"
        request_id: ID of the coverage request
        db: DatabaseManager instance for looking up users and request details
    """
    sender = os.environ.get("SES_SENDER_EMAIL", "")
    if not sender:
        logger.warning("SES_SENDER_EMAIL not set; skipping email notifications")
        return

    # Look up the coverage request
    all_requests = db.get_coverage_requests()
    coverage_request = next((r for r in all_requests if r.id == request_id), None)
    if coverage_request is None:
        logger.warning("Coverage request %d not found; skipping email", request_id)
        return

    requester = db.get_user_by_id(coverage_request.requester_id)
    if requester is None:
        logger.warning("Requester user %d not found; skipping email", coverage_request.requester_id)
        return

    claimer = None
    if coverage_request.claimer_id is not None:
        claimer = db.get_user_by_id(coverage_request.claimer_id)

    # Determine recipients
    if event_type == "created":
        recipients = db.get_notification_recipients(exclude_user_id=requester.id)
    elif event_type == "claimed":
        # Only the requester, if opted in
        if requester.email and requester.email_notifications_enabled:
            recipients = [requester]
        else:
            recipients = []
    else:
        return

    subject, body = _build_email_body(event_type, coverage_request, requester, claimer)
    if not subject:
        return

    for recipient in recipients:
        t = threading.Thread(
            target=_send_ses_email,
            args=(recipient.email, subject, body),
            daemon=True,
        )
        t.start()
