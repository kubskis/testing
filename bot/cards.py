"""Карточка заявки для владелиц (чистый текст, без зависимости от aiogram)."""
import html

from . import forms, texts


def user_label(req: dict) -> str:
    """@юзернейм, если есть, иначе ник со ссылкой на профиль."""
    username = req.get("username")
    if username:
        return f"@{html.escape(username)}"
    name = html.escape(req.get("full_name") or str(req["user_id"]))
    return f'<a href="tg://user?id={req["user_id"]}">{name}</a>'


def status_title(req: dict) -> str:
    table = texts.STATUS_QUESTION if req["kind"] == "question" else texts.STATUS_ORDER
    return table.get(req["status"], req["status"])


def render_card(req: dict) -> str:
    kind = req["kind"]
    data = req["data"]
    lines = [
        f"📩 <b>Заявка №{req['id']}</b> · {texts.KIND_TITLES[kind]}",
        f"От: {user_label(req)} · ID <code>{req['user_id']}</code>",
        "",
    ]

    if kind == "question":
        if data.get("text"):
            lines.append(html.escape(data["text"]))
        if data.get("has_media"):
            lines.append("📎 Вложение — сообщением ниже.")
    else:
        for step in forms.FORMS[kind].steps:
            if step.kind == "photos":
                lines.append(f"<b>{step.label}:</b> {len(req['photos'])} шт. (выше)")
                continue
            value = data.get(step.key)
            text = html.escape(str(value)) if value not in (None, "") else "—"
            if step.key == "contact" and data.get("contact_auto"):
                text += " <i>(определён автоматически)</i>"
            lines.append(f"<b>{step.label}:</b> {text}")

        extra = forms.extra_cost(int(data.get("count") or 0))
        if extra:
            over, price = extra
            lines.append(f"💰 Сверх бесплатных: +{over} шт. (≈ {price}⭐/₽)")

    lines += ["", f"<b>Статус:</b> {status_title(req)}"]
    if req["status"] == "rejected":
        reason = req.get("reject_reason")
        lines.append(f"<b>Причина:</b> {html.escape(reason) if reason else 'без причины'}")
    return "\n".join(lines)


def short_line(req: dict) -> str:
    """Одна строка для списка /queue."""
    name = req["data"].get("name") or ""
    title = texts.KIND_TITLES[req["kind"]]
    tail = f" · {html.escape(name)}" if name else ""
    return f"№{req['id']} · {title}{tail} · {user_label(req)}"
