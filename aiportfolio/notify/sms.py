"""Trade alerts over multiple channels (user-selectable): SMS (Twilio) and/or
Telegram (free). Email / web-push are documented extension points.

Channels come from config notify.channels, e.g. ["sms", "telegram"]. The buddy
sends each alert to every enabled+configured channel. Messages are deliberately
specific: share counts, exact exit plan, and whether an auto-sell was set.
"""
from __future__ import annotations

import json
import urllib.request


class Notifier:
    def __init__(self, secrets, cfg):
        self.secrets = secrets
        self.cfg = cfg.get("notify", {}) or {}
        self.channels = self.cfg.get("channels") or [self.cfg.get("provider", "console")]
        self._twilio = None
        if "sms" in self.channels and secrets.twilio_ready:
            try:
                from twilio.rest import Client
                self._twilio = Client(secrets.twilio_sid, secrets.twilio_token)
            except Exception:
                self._twilio = None

    @property
    def enabled(self):
        return bool(self.cfg.get("enabled", True))

    def send(self, body):
        if not self.enabled:
            return
        delivered = False
        if "sms" in self.channels and self._twilio:
            try:
                self._twilio.messages.create(body=body, from_=self.secrets.twilio_from,
                                             to=self.secrets.alert_to)
                delivered = True
            except Exception as e:
                print(f"[notify] Twilio failed ({e}).")
        if "telegram" in self.channels and self.secrets.telegram_ready:
            if self._telegram(body):
                delivered = True
        if "email" in self.channels and self.secrets.email_ready:
            if self._email(body):
                delivered = True
        if not delivered:
            print("\n" + "=" * 50 + f"\n📲 {body}\n" + "=" * 50 + "\n")

    def _telegram(self, body) -> bool:
        try:
            url = f"https://api.telegram.org/bot{self.secrets.telegram_token}/sendMessage"
            data = json.dumps({"chat_id": self.secrets.telegram_chat_id, "text": body}).encode()
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            print(f"[notify] Telegram failed ({e}).")
            return False

    def _email(self, body) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(body)
            msg["Subject"] = "🤖 Trading Buddy alert"
            msg["From"] = self.secrets.smtp_from or self.secrets.smtp_user
            msg["To"] = self.secrets.email_to
            with smtplib.SMTP(self.secrets.smtp_host, self.secrets.smtp_port or 587, timeout=15) as s:
                s.starttls()
                s.login(self.secrets.smtp_user, self.secrets.smtp_pass)
                s.send_message(msg)
            return True
        except Exception as e:
            print(f"[notify] Email failed ({e}).")
            return False

    # ── exit-plan phrasing ───────────────────────────────────────────
    @staticmethod
    def _exit_phrase(plan: dict) -> str:
        t = (plan or {}).get("type", "manual_next_day")
        if t == "bracket":
            return (f"Exit (AUTO, set now): limit-sell ${plan.get('limit_price'):g} "
                    f"OR stop-sell ${plan.get('stop_price'):g}. If copying, set both sells.")
        if t == "limit":
            return f"Exit (AUTO, set now): limit-sell ${plan.get('limit_price'):g}. If copying, set that sell."
        if t == "stop":
            return f"Exit (AUTO, set now): stop-sell ${plan.get('stop_price'):g}. If copying, set that stop."
        if t == "time":
            return f"Exit: hold ~{plan.get('hold_days',1)}d, then I'll ping you to market-sell."
        if t == "hold":
            return "Exit: long-term hold, no preset sell."
        return "Exit: MANUAL — no auto-sell set; I'll text you when it's time to sell."

    def format_proposal(self, t, lead, price=None, shares=None, signals_only=False):
        when = f"in ~{lead} min"
        if t.instrument == "option":
            risk = f", max risk ~${t.est_premium:.0f}" if t.est_premium else ""
            if getattr(t, "strategy", "single") == "vertical" and getattr(t, "short_strike", 0):
                legs = f"${t.strike:g}/${t.short_strike:g} {t.right.upper()} vertical"
            else:
                legs = f"${t.strike:g} {t.right.upper()}"
            head = (f"🤖 ({t.confidence:.0%}) {t.action} {t.contracts}x {t.underlying} "
                    f"{t.expiry_label} {legs}{risk}")
        else:
            sh = f"~{shares:g} share{'s' if (shares or 0) != 1 else ''}" if shares else ""
            px = f" (~${price:g}/sh, ${t.notional:g} total)" if price else f" (${t.notional:g})"
            head = f"🤖 ({t.confidence:.0%}) {t.action} {sh} {t.symbol}{px}"
        exit_line = self._exit_phrase(t.exit_plan) if t.action == "BUY" else ""
        # Signals-only: heads-up just for you; the buddy is not paper-trading it.
        plan = "Heads-up only — not paper-trading this." if signals_only else f"Paper-executing {when}."
        return f"{head}. {plan}\n{exit_line}\nWhy: {t.rationale[:170]}"

    def format_consult(self, symbol, verdict, reasoning, intent, agree, acted=False):
        head = f"🤖 Take on {symbol}: {verdict.upper()}"
        if intent == "conditional_buy" and not acted:
            head += f" — I'd {'agree' if agree else 'pass'} on buying"
        return f"{head}.\nWhy: {reasoning[:220]}"

    def format_exit(self, symbol, lead, kind="planned", fraction=1.0, note=""):
        amt = "all shares" if fraction >= 1 else f"{fraction:.0%} of the position"
        if kind == "risk":
            return f"⚠️ Risk exit: SELLING {amt} of {symbol} now. {note}"
        return (f"📉 From a prior buy of {symbol}: SELLING {amt} in ~{lead} min (market). "
                f"If you copied the buy, sell yours too. {note}")
