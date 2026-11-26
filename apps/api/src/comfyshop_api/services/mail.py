"""发送平台邮件。没有配置邮件服务时把内容写入服务日志，开发环境据此完成流程。"""

import logging
import smtplib
from email.message import EmailMessage
from html import escape
from itertools import groupby

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import localize, msg
from comfyshop_api.core.languages import LANGUAGES
from comfyshop_api.design_tokens import COLORS

log = logging.getLogger("comfyshop.mail")


FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif"


def _logo() -> str:
    """以新版图标的像素轮廓绘制表格，邮件屏蔽图片时也能显示。"""
    pixels = (
        "...########.....",
        "..#########.....",
        ".########..#....",
        ".###......####..",
        "###.....#######.",
        "###.....##......",
        "###.....##......",
        "###.....#######.",
        "###......######.",
        "####.........###",
        ".###############",
        "..#############.",
        "...###########..",
        "...........#....",
    )

    def row(height: int, cells: list[tuple[int, bool]]) -> str:
        columns = "".join(
            f'<td width="{width}" height="{height}"'
            + (f' bgcolor="{COLORS["accent"]}"' if filled else "")
            + f' style="padding:0;width:{width}px;height:{height}px;font-size:0;line-height:0'
            + (f";background:{COLORS['accent']}" if filled else "")
            + f'"><div style="width:{width}px;height:{height}px;font-size:0;line-height:0">'
            "</div></td>"
            for width, filled in cells
        )
        return (
            '<tr><td style="padding:0;font-size:0;line-height:0"><table role="presentation" '
            f'cellpadding="0" cellspacing="0" border="0"><tr>{columns}</tr></table></td></tr>'
        )

    return (
        '<table role="presentation" aria-hidden="true" '
        'cellpadding="0" cellspacing="0" border="0" width="32">'
        + "".join(
            row(2, [(2 * len(list(run)), pixel == "#") for pixel, run in groupby(line)])
            for line in pixels
        )
        + "</table>"
    )


def branded_mail(
    title: str, paragraphs: list[str], action: tuple[str, str] | None, footnote: str, language: str
) -> str:
    """生成带 Logo 的深色主题邮件正文。`action` 是主按钮的文字和链接，链接同时以文字给出。"""
    text = f"margin:0 0 16px;font-size:14px;line-height:1.7;color:{COLORS['text']}"
    body = "".join(f'<p style="{text}">{escape(paragraph)}</p>' for paragraph in paragraphs)
    if action:
        fallback = escape(localize(msg("mail.copyUrl"), language))
        label, url = escape(action[0]), escape(action[1], quote=True)
        body += (
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:8px 0 24px"><tr><td bgcolor="{COLORS["accent"]}" '
            f'style="background:{COLORS["accent"]}">'
            f'<a href="{url}" style="display:inline-block;padding:12px 24px;font-size:14px;'
            f'font-weight:600;color:{COLORS["on-accent"]};text-decoration:none">{label}</a>'
            "</td></tr></table>"
            f'<p style="margin:0 0 16px;font-size:12px;line-height:1.7;color:{COLORS["muted"]};'
            f'word-break:break-all">{fallback}<br>'
            f'<a href="{url}" style="color:{COLORS["muted"]}">{url}</a></p>'
        )
    return (
        f'<!doctype html><html lang="{LANGUAGES[language]["locale"]}"><head><meta charset="utf-8">'
        '<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" '
        f'content="dark"></head><body style="margin:0;padding:0;background:{COLORS["canvas"]}">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'bgcolor="{COLORS["canvas"]}" style="background:{COLORS["canvas"]};font-family:{FONT}">'
        '<tr><td align="center" style="padding:32px 16px">'
        '<table role="presentation" width="480" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:480px">'
        '<tr><td style="padding:0 0 24px"><table role="presentation" cellpadding="0" '
        f'cellspacing="0" border="0"><tr><td style="padding:0 10px 0 0">{_logo()}</td>'
        f'<td style="font-size:20px;font-weight:700;letter-spacing:-0.06em;color:{COLORS["text"]}">'
        "ComfyShop</td></tr></table></td></tr>"
        f'<tr><td bgcolor="{COLORS["surface"]}" style="background:{COLORS["surface"]};'
        f'border:1px solid {COLORS["border"]};padding:32px">'
        f'<h1 style="margin:0 0 20px;font-size:18px;font-weight:600;color:{COLORS["text"]}">'
        f"{escape(title)}</h1>{body}"
        f'<p style="margin:0;font-size:12px;line-height:1.7;color:{COLORS["muted"]}">'
        f"{escape(footnote)}</p></td></tr></table></td></tr></table></body></html>"
    )


def send_mail(
    settings: Settings, to: str, subject: str, body: str, html: str | None = None
) -> None:
    """发送邮件，`body` 是纯文本正文，`html` 是可选的主题样式正文。

    发送失败只记录日志，调用方的请求不受影响。"""
    if not settings.smtp_host:
        log.warning("未配置邮件服务，邮件未发送。收件人 %s，主题「%s」：\n%s", to, subject, body)
        return
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    try:
        client = (smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP)(
            settings.smtp_host, settings.smtp_port, timeout=15
        )
        with client:
            if settings.smtp_security == "starttls":
                client.starttls()
            if settings.smtp_username and settings.smtp_password:
                client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        log.exception("邮件发送失败，收件人 %s", to)
