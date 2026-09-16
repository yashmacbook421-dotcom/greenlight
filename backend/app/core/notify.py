"""Outbound notices to the applicant.

Every notice is recorded in the database first and delivered second, so the portal and the engineer can always
see what was sent, even with no mail server configured. Delivery is off unless SMTP settings are present:
in that case rows stay `queued`, which is what a demo install shows.
"""

import logging
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.core.models import Notification, NotificationStatus

log = logging.getLogger(__name__)


def record(session: Session, *, case_id: uuid.UUID, kind: str, recipient: str | None, subject: str,
           body: str) -> Notification:
    """Store the notice. Returns it unsent; call `deliver` to attempt delivery."""
    notification = Notification(
        case_id=case_id, kind=kind, channel="email", recipient=(recipient or None), subject=subject, body=body,
        status=NotificationStatus.NO_RECIPIENT if not recipient else NotificationStatus.QUEUED,
    )
    session.add(notification)
    session.flush()
    return notification


def deliver(session: Session, notification: Notification) -> Notification:
    """Send by SMTP when it is configured. Failures are recorded, never raised: a notice must not undo a decision."""
    if notification.status != NotificationStatus.QUEUED:
        return notification
    if not settings.smtp_host:
        log.info("notification %s queued (no SMTP configured): %s -> %s", notification.id, notification.subject,
                 notification.recipient)
        return notification
    message = EmailMessage()
    message["Subject"] = notification.subject
    message["From"] = settings.smtp_from
    message["To"] = notification.recipient or ""
    message.set_content(notification.body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now(UTC)
    except Exception as exc:
        log.exception("notification %s could not be delivered", notification.id)
        notification.status = NotificationStatus.FAILED
        notification.error = str(exc)[:500]
    session.flush()
    return notification
