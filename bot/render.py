"""Сборка текста заявки для владельцев. Без зависимостей от aiogram."""
import html

from . import texts
from .forms import FORMS, extra_cost

STATUS_LABELS = {
    "pending": "На рассмотрении",
    "queued": "В очереди",
    "done": "Выполнено",
    "rejected": "Отклонено",
}


def status_label(req: dict) -> str:
    if req["kind"] == "question" and req["status"] == "done":
        return "Закрыт"
    return STATUS_LABELS.get(req["status"], req["status"])


def user_label(req: dict) -> str:
    """Юзернейм, если он есть, иначе имя."""
    if req.get("username"):
        return f"@{req['username']}"
    return req.get("full_name") or "без имени"


def controls_text(req: dict) -> str:
    """Короткий текст сообщения с кнопками (когда заявка идёт вместе с фото)."""
    return f"Заявка #{req['id']} — {status_label(req)}"


def request_text(req: dict) -> str:
    esc = html.escape
    label = user_label(req)
    lines = [
        f"<b>Заявка #{req['id']}</b> · {texts.KIND_TITLES[req['kind']]}",
        f"Статус: {status_label(req)}",
    ]
    if req["status"] == "rejected":
        lines.append(f"Причина отказа: {esc(req['reject_reason'])}" if req.get("reject_reason")
                     else "Причина отказа: без причины")
    lines.append("")
    lines.append(f"От: <b>{esc(label)}</b> · ID <code>{req['user_id']}</code>")
    lines.append("")

    answers = req["answers"]
    if req["kind"] == "question":
        lines.append("Вопрос:")
        lines.append(esc(str(answers.get("question", ""))))
    else:
        form = FORMS[req["kind"]]
        for i, step in enumerate(form.steps, 1):
            value = answers.get(step.key)
            if step.key == "contact" and value is None:
                shown = f"— (бот использует: {esc(label)})"
            elif value is None or value == "":
                shown = "—"
            elif step.key == "count":
                shown = f"{value} шт."
                cost = extra_cost(int(value))
                if cost:
                    shown += f" (доплата: {cost}⭐/{cost}₽)"
            else:
                shown = esc(str(value))
            lines.append(f"{i}. <b>{esc(step.label)}:</b> {shown}")
        lines.append(f"Фото: {len(req['photos'])} шт.")
    return "\n".join(lines)
