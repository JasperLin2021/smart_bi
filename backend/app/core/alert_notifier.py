"""
Synchronous notification senders for email, WeChat Work, and DingTalk.
These are called from APScheduler background threads (no asyncio event loop).
"""
import base64
import hashlib
import hmac
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx


def send_wechat_sync(webhook_url: str, content: str) -> None:
    """Send a Markdown message to a WeChat Work group robot."""
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }
    with httpx.Client(timeout=10) as client:
        resp = client.post(webhook_url, json=payload)
        resp.raise_for_status()


def send_dingtalk_sync(
    webhook_url: str, secret: Optional[str], content: str
) -> None:
    """Send a Markdown message to a DingTalk group robot (with optional HMAC sign)."""
    params: dict = {}
    if secret:
        timestamp = str(round(time.time() * 1000))
        sign_str = f"{timestamp}\n{secret}"
        digest = hmac.new(
            secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        sign = base64.b64encode(digest).decode()
        params = {"timestamp": timestamp, "sign": sign}

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "Smart BI 通知",
            "text": content,
        },
    }
    with httpx.Client(timeout=10) as client:
        resp = client.post(webhook_url, json=payload, params=params)
        resp.raise_for_status()


def send_email_sync(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    smtp_from: str,
    use_ssl: bool,
    recipients: list[str],
    subject: str,
    html_content: str,
) -> None:
    """Send an HTML email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from, recipients, msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from, recipients, msg.as_string())
