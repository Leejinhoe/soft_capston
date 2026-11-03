"""메일 발송 공통 모듈 (비밀번호 재설정 인증번호, 정지·탈퇴 안내 등).

- .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD (보내는 주소 = 답장 받는 주소 = SMTP_USER)
- 포트 465면 SSL, 그 외(587 등)는 STARTTLS로 접속합니다.
- 발송은 실패해도 예외를 던지지 않고 서버 로그에만 남깁니다. (원래 동작은 그대로 진행)
- 화면 응답이 늦어지지 않게 보통 FastAPI BackgroundTasks로 send_mail을 넘겨서 씁니다.
"""
import asyncio
import html
import logging
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("uvicorn.error")

APP_NAME = "AI Fairy Tale"
SMTP_HOST = (os.getenv("SMTP_HOST") or "").strip()
SMTP_PORT = int((os.getenv("SMTP_PORT") or "587").strip() or 587)
SMTP_USER = (os.getenv("SMTP_USER") or "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or ""
SMTP_TIMEOUT = 15  # 초

KST = timedelta(hours=9)


def mail_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def kst_text(value: datetime | None = None) -> str:
    """UTC datetime → '2026년 11월 3일 14:05 (한국 시간)'"""
    d = (value or datetime.utcnow()) + KST
    return f"{d.year}년 {d.month}월 {d.day}일 {d.hour:02d}:{d.minute:02d} (한국 시간)"


def mask_email(email: str) -> str:
    """로그용: ab***@gmail.com"""
    name, _, domain = (email or "").partition("@")
    return f"{name[:2]}***@{domain}" if domain else "(없음)"


# ----------------------------------------
# HTML 템플릿
# ----------------------------------------
def esc(text: str) -> str:
    """사용자/관리자가 입력한 글은 반드시 이걸로 감싸서 넣습니다. (줄바꿈 유지)"""
    return html.escape(text or "").replace("\n", "<br>")


def render_mail(title: str, body_html: str, footer_note: str = "") -> str:
    """앱 이름이 들어간 공통 메일 틀. body_html 안의 사용자 입력은 esc()로 이미 처리돼 있어야 합니다."""
    note = footer_note or "이 메일은 발신 전용이 아니에요. 궁금한 점은 이 메일에 답장해 주세요."
    return f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f1fb;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1fb;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:520px;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 6px 24px rgba(91,33,182,0.12);">
        <tr><td style="background:linear-gradient(135deg,#8B5CF6,#EC4899);background-color:#8B5CF6;padding:24px 28px;">
          <div style="color:#ffffff;font-size:22px;font-weight:bold;">📖 {esc(APP_NAME)}</div>
          <div style="color:#f3e8ff;font-size:13px;margin-top:4px;">AI와 함께 만드는 나만의 동화</div>
        </td></tr>
        <tr><td style="padding:28px;">
          <h1 style="margin:0 0 18px;font-size:20px;color:#1f1235;">{esc(title)}</h1>
          <div style="font-size:15px;line-height:1.7;color:#3b3355;">{body_html}</div>
        </td></tr>
        <tr><td style="padding:18px 28px;background:#faf8ff;border-top:1px solid #ede9fe;font-size:12px;line-height:1.6;color:#8a7fa8;">
          {esc(note)}<br>© {esc(APP_NAME)}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def info_table(rows: list[tuple[str, str]]) -> str:
    """'항목 | 내용' 표 (값은 esc 처리됨)"""
    cells = "".join(
        f'<tr><td style="padding:10px 12px;background:#f5f3ff;color:#6d5d99;font-size:13px;width:84px;'
        f'vertical-align:top;border-bottom:1px solid #ede9fe;">{esc(k)}</td>'
        f'<td style="padding:10px 12px;color:#1f1235;border-bottom:1px solid #ede9fe;">{esc(v)}</td></tr>'
        for k, v in rows
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;border:1px solid #ede9fe;border-radius:12px;margin:16px 0;">{cells}</table>'
    )


# ----------------------------------------
# 발송
# ----------------------------------------
def _send_blocking(to: str, subject: str, html_body: str, text_body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[{APP_NAME}] {subject}"
    msg["From"] = formataddr((APP_NAME, SMTP_USER))
    msg["To"] = to
    msg["Reply-To"] = SMTP_USER
    msg["Message-ID"] = make_msgid(domain=SMTP_USER.partition("@")[2] or None)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)


async def send_mail(to: str, subject: str, html_body: str, text_body: str, *, kind: str = "mail") -> bool:
    """메일 1통 보내기. 성공하면 True, 실패/미설정이면 로그만 남기고 False. (예외를 던지지 않음)"""
    to = (to or "").strip()
    if not to:
        logger.warning("[mail:%s] 받는 주소가 없어 보내지 않음", kind)
        return False
    if not mail_configured():
        logger.warning("[mail:%s] SMTP 설정(.env)이 없어 보내지 않음 → %s", kind, mask_email(to))
        return False
    try:
        await asyncio.to_thread(_send_blocking, to, subject, html_body, text_body)
        logger.info("[mail:%s] 보냄 → %s", kind, mask_email(to))
        return True
    except Exception as e:  # noqa: BLE001 - 어떤 오류든 원래 동작은 계속돼야 합니다.
        logger.error("[mail:%s] 발송 실패 → %s: %s: %s", kind, mask_email(to), type(e).__name__, e)
        return False


# ----------------------------------------
# 안내 메일 내용 (관리자 조치)
# ----------------------------------------
async def send_admin_action_mail(to: str, nickname: str, action: str, reason: str, when: datetime) -> bool:
    """정지·강제 탈퇴 안내. action: '이용 정지' / '강제 탈퇴'"""
    date_text = kst_text(when)
    if action == "강제 탈퇴":
        lead = f"{nickname}님의 {APP_NAME} 계정이 운영 정책에 따라 탈퇴 처리되었어요."
        after = "탈퇴된 계정으로는 더 이상 로그인할 수 없어요."
    else:
        lead = f"{nickname}님의 {APP_NAME} 계정 이용이 운영 정책에 따라 정지되었어요."
        after = "정지된 동안에는 로그인과 서비스 이용이 어려워요."
    appeal = "이 조치에 이의가 있으면 이 메일에 답장해 주세요. 확인 후 안내해 드릴게요."

    body = (
        f"<p style='margin:0 0 8px;'>{esc(lead)}</p>"
        + info_table([("조치", action), ("사유", reason), ("날짜", date_text)])
        + f"<p style='margin:0 0 8px;'>{esc(after)}</p>"
        + f"<p style='margin:16px 0 0;padding:14px 16px;background:#fdf2f8;border-radius:12px;color:#9d174d;'>"
          f"✉️ {esc(appeal)}</p>"
    )
    text = (
        f"{lead}\n\n조치: {action}\n사유: {reason}\n날짜: {date_text}\n\n{after}\n{appeal}\n\n- {APP_NAME}"
    )
    return await send_mail(
        to, f"계정 {action} 안내", render_mail(f"계정 {action} 안내", body), text, kind=f"admin:{action}"
    )
