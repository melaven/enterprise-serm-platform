"""
Email notification service for critical reputation threats
Sends immediate alerts when threat_level == 5 (lawsuit, health inspection, scandal)
"""

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.logger import get_logger

logger = get_logger("notifications")


# ============================================================================
# Email Configuration
# ============================================================================

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@serm-platform.com")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"


# ============================================================================
# HTML Email Template
# ============================================================================


def _create_critical_threat_email(
    company_name: str,
    review_text: str,
    suggested_reply: str,
    platform: str,
    author_name: str,
) -> str:
    """
    Create HTML email template for critical threat alert.
    Red/dark accent theme for urgency.
    """
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Critical Threat Alert</title>
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #0a0a0a;
            color: #ffffff;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #1a1a1a;
            border: 2px solid #dc2626;
            border-radius: 8px;
            overflow: hidden;
        }}
        .header {{
            background-color: #dc2626;
            padding: 24px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 24px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .content {{
            padding: 32px;
        }}
        .alert-box {{
            background-color: #7f1d1d;
            border-left: 4px solid #dc2626;
            padding: 16px;
            margin-bottom: 24px;
            border-radius: 4px;
        }}
        .alert-box h2 {{
            margin: 0 0 8px 0;
            color: #ffffff;
            font-size: 18px;
            font-weight: 600;
        }}
        .alert-box p {{
            margin: 0;
            color: #fecaca;
            font-size: 14px;
        }}
        .section {{
            margin-bottom: 24px;
        }}
        .section h3 {{
            margin: 0 0 12px 0;
            color: #e5e7eb;
            font-size: 16px;
            font-weight: 600;
            border-bottom: 1px solid #374151;
            padding-bottom: 8px;
        }}
        .review-text {{
            background-color: #111827;
            padding: 16px;
            border-radius: 4px;
            border-left: 3px solid #dc2626;
            margin: 12px 0;
            font-style: italic;
            color: #d1d5db;
        }}
        .suggested-reply {{
            background-color: #064e3b;
            border-left: 3px solid #10b981;
            padding: 16px;
            border-radius: 4px;
            margin: 12px 0;
        }}
        .suggested-reply h4 {{
            margin: 0 0 8px 0;
            color: #10b981;
            font-size: 14px;
            font-weight: 600;
        }}
        .suggested-reply p {{
            margin: 0;
            color: #d1fae5;
            white-space: pre-wrap;
        }}
        .metadata {{
            background-color: #1f2937;
            padding: 12px;
            border-radius: 4px;
            font-size: 13px;
            color: #9ca3af;
        }}
        .metadata-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .metadata-row:last-child {{
            margin-bottom: 0;
        }}
        .footer {{
            background-color: #111827;
            padding: 16px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #374151;
        }}
        .cta-button {{
            display: inline-block;
            background-color: #dc2626;
            color: #ffffff;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            margin-top: 16px;
        }}
        .cta-button:hover {{
            background-color: #b91c1c;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Critical Threat Alert</h1>
        </div>

        <div class="content">
            <div class="alert-box">
                <h2>Immediate Action Required</h2>
                <p>A critical reputation threat has been detected for <strong>{company_name}</strong>.</p>
            </div>

            <div class="section">
                <h3>📝 Review Details</h3>
                <div class="metadata">
                    <div class="metadata-row">
                        <span><strong>Platform:</strong></span>
                        <span>{platform}</span>
                    </div>
                    <div class="metadata-row">
                        <span><strong>Author:</strong></span>
                        <span>{author_name}</span>
                    </div>
                </div>

                <div class="review-text">
                    "{review_text}"
                </div>
            </div>

            <div class="section">
                <h3>💡 Suggested Response</h3>
                <div class="suggested-reply">
                    <h4>AI-Generated Draft Reply:</h4>
                    <p>{suggested_reply}</p>
                </div>
            </div>

            <div class="section">
                <h3>🎯 Recommended Actions</h3>
                <ul style="color: #d1d5db; padding-left: 20px; margin: 0;">
                    <li>Review the suggested response above</li>
                    <li>Respond to the review within 24 hours</li>
                    <li>Consider escalating to legal or PR team</li>
                    <li>Monitor for similar threats</li>
                </ul>

                <a href="#" class="cta-button">View in Dashboard</a>
            </div>
        </div>

        <div class="footer">
            <p>This is an automated alert from SERM Platform. Please do not reply to this email.</p>
            <p>Threat Level: 5/5 (Critical - Lawsuit/Health Inspection/Scandal)</p>
        </div>
    </div>
</body>
</html>
"""
    return html


# ============================================================================
# Email Service
# ============================================================================


class NotificationError(Exception):
    """Custom exception for notification errors"""

    pass


async def send_critical_threat_alert(
    recipient_email: str,
    company_name: str,
    review_text: str,
    suggested_reply: str,
    platform: str,
    author_name: str,
) -> bool:
    """
    Send critical threat alert email to company owner.

    Args:
        recipient_email: Email address of the company owner
        company_name: Name of the company
        review_text: Text of the critical review
        suggested_reply: AI-generated suggested response
        platform: Platform where the review was posted
        author_name: Name of the review author

    Returns:
        True if email sent successfully, False otherwise

    Raises:
        NotificationError: If email configuration is missing or sending fails
    """
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        logger.error(
            "smtp_configuration_missing",
            host_configured=bool(SMTP_HOST),
            user_configured=bool(SMTP_USER),
            password_configured=bool(SMTP_PASSWORD),
        )
        raise NotificationError(
            "SMTP configuration is incomplete. Please set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD environment variables."
        )

    # Create email message
    message = MIMEMultipart("alternative")
    message["Subject"] = (
        f"⚠️ CRITICAL THREAT: {company_name} - Immediate Action Required"
    )
    message["From"] = SMTP_FROM
    message["To"] = recipient_email

    # Create HTML content
    html_content = _create_critical_threat_email(
        company_name=company_name,
        review_text=review_text,
        suggested_reply=suggested_reply,
        platform=platform,
        author_name=author_name,
    )

    # Attach HTML content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    try:
        # Send email
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            use_tls=SMTP_USE_TLS,
            timeout=30,
        )

        logger.info(
            "critical_threat_email_sent",
            recipient=recipient_email,
            company=company_name,
            platform=platform,
        )

        return True

    except aiosmtplib.SMTPException as e:
        logger.error(
            "smtp_error",
            error=str(e),
            recipient=recipient_email,
            company=company_name,
        )
        raise NotificationError(f"Failed to send email: {str(e)}") from e

    except Exception as e:
        logger.error(
            "email_sending_failed",
            error=str(e),
            error_type=type(e).__name__,
            recipient=recipient_email,
        )
        raise NotificationError(f"Unexpected error sending email: {str(e)}") from e


async def check_and_notify_critical_threat(
    recipient_email: str,
    company_name: str,
    review_text: str,
    suggested_reply: str | None,
    platform: str,
    author_name: str,
    threat_level: int | None,
) -> bool:
    """
    Check if threat level is critical (5) and send notification.

    Args:
        recipient_email: Email address of the company owner
        company_name: Name of the company
        review_text: Text of the review
        suggested_reply: AI-generated suggested response
        platform: Platform where the review was posted
        author_name: Name of the review author
        threat_level: Threat level from LLM analysis (1-5)

    Returns:
        True if notification was sent, False otherwise
    """
    # Only send alert for critical threats (level 5)
    if threat_level != 5:
        logger.debug(
            "threat_not_critical",
            threat_level=threat_level,
            company=company_name,
        )
        return False

    if not suggested_reply:
        logger.warning(
            "critical_threat_no_suggested_reply",
            company=company_name,
            platform=platform,
        )
        # Still send alert even without suggested reply
        suggested_reply = "No AI-generated response available. Please review manually."

    try:
        await send_critical_threat_alert(
            recipient_email=recipient_email,
            company_name=company_name,
            review_text=review_text,
            suggested_reply=suggested_reply,
            platform=platform,
            author_name=author_name,
        )
        return True

    except NotificationError as e:
        logger.error(
            "critical_threat_notification_failed",
            company=company_name,
            error=str(e),
        )
        # Don't raise - notification failure shouldn't block the main flow
        return False
