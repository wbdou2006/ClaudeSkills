#!/usr/bin/env python3
"""Send the drawdown report email from YOUR OWN computer over SMTP.

Run this yourself in Terminal; Claude never runs it and never handles your password.
The password is read from the SMTP_PASSWORD environment variable or prompted for
(hidden) — use an app password, not your main account password:
  Gmail: myaccount.google.com/apppasswords   Yahoo: Account security → App passwords

Usage:
    python3 send_email.py drawdown_report.eml --from you@example.com \
        [--smtp smtp.gmail.com] [--port 587] [--to someone@example.com]

--smtp defaults by sender domain (gmail, yahoo, icloud/me/mac, outlook/hotmail).
--to overrides the recipients stored in the .eml.
"""
import argparse
import getpass
import os
import smtplib
import ssl
import sys
from email import policy
from email.parser import BytesParser

DEFAULT_SMTP = {
    "gmail.com": "smtp.gmail.com", "googlemail.com": "smtp.gmail.com",
    "yahoo.com": "smtp.mail.yahoo.com",
    "icloud.com": "smtp.mail.me.com", "me.com": "smtp.mail.me.com", "mac.com": "smtp.mail.me.com",
    "outlook.com": "smtp-mail.outlook.com", "hotmail.com": "smtp-mail.outlook.com", "live.com": "smtp-mail.outlook.com",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eml")
    ap.add_argument("--from", dest="sender", required=True)
    ap.add_argument("--to", nargs="+")
    ap.add_argument("--smtp")
    ap.add_argument("--port", type=int, default=587)
    ap.add_argument("--user", help="SMTP login if different from --from")
    a = ap.parse_args()

    with open(a.eml, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    del msg["X-Unsent"]
    del msg["From"]
    msg["From"] = a.sender
    if a.to:
        del msg["To"]
        msg["To"] = ", ".join(a.to)
    recipients = [r.strip() for r in str(msg["To"] or "").split(",") if r.strip()]
    if not recipients:
        sys.exit("No recipients: pass --to.")

    host = a.smtp or DEFAULT_SMTP.get(a.sender.split("@")[-1].lower())
    if not host:
        sys.exit("Unknown mail provider: pass --smtp (and --port if not 587).")

    print(f"From:    {a.sender}\nTo:      {', '.join(recipients)}\nSubject: {msg['Subject']}\nServer:  {host}:{a.port}")
    if input("Send this email? [y/N] ").strip().lower() != "y":
        sys.exit("Not sent.")
    pw = os.environ.get("SMTP_PASSWORD") or getpass.getpass("App password (hidden): ")

    ctx = ssl.create_default_context()
    if a.port == 465:
        server = smtplib.SMTP_SSL(host, a.port, context=ctx, timeout=30)
    else:
        server = smtplib.SMTP(host, a.port, timeout=30)
        server.starttls(context=ctx)
    with server:
        server.login(a.user or a.sender, pw)
        server.send_message(msg, from_addr=a.sender, to_addrs=recipients)
    print("Sent.")


if __name__ == "__main__":
    main()
