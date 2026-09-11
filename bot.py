"""
Pamela & Charlene task bot — a Slack-Free-plan-compatible replacement
for Slack Lists + Workflow Builder.

Runs on a schedule (see .github/workflows/run.yml). Each run:
  1. Reads new "New Task" messages from #charlene-tasks -> files them.
  2. Reads reaction emoji on task messages -> updates status, routes
     notifications to the right channel.
  3. Reads thread replies tagged [waiting]/[next]/[deliverable]/
     [summary]/[notes]/[status] -> fills in the matching field.
  4. Reads Pamela's ✅/🔁 reactions on #pamela-approval posts -> handles
     the approve / changes-requested branch.
  5. Refreshes the pinned Task Board message in #charlene-tasks.
  6. On Saturdays, posts the weekly report to #monday-email (once per day).

All task data lives in tasks.json, committed back to the repo by the
GitHub Action after this script runs. There is no external database.
"""

import json
import os
import re
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import config as cfg

TZ = ZoneInfo("America/Chicago")


# ---------------------------------------------------------------- utils --
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def today_str():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def gen_task_id(tasks):
    today = datetime.now(TZ).strftime("%Y%m%d")
    count_today = sum(1 for t in tasks if t["task_id"].startswith(f"{cfg.TASK_ID_PREFIX}-{today}"))
    return f"{cfg.TASK_ID_PREFIX}-{today}-{count_today + 1:02d}"


def find_task_by_message_ts(tasks, ts):
    for t in tasks:
        if t.get("message_ts") == ts:
            return t
    return None


def find_task_by_approval_ts(tasks, ts):
    for t in tasks:
        if t.get("approval_message_ts") == ts:
            return t
    return None


def safe_call(fn, *args, **kwargs):
    """Call a Slack API method, print+swallow errors so one bad call
    doesn't crash the whole run (GitHub Actions will just try again
    next scheduled run)."""
    try:
        return fn(*args, **kwargs)
    except SlackApiError as e:
        print(f"Slack API error calling {fn.__name__}: {e.response['error']}")
        return None


# --------------------------------------------------------- 1. intake ----
NEW_TASK_FIELD_PATTERN = re.compile(
    r"^\s*(task|instructions|date received|due date|priority|pamela approval needed|project)\s*:\s*(.*)$",
    re.IGNORECASE,
)


def parse_new_task_message(text):
    """Parse a 'New Task' formatted message into a field dict.
    Returns None if the message doesn't look like a New Task post."""
    if "task" not in text.lower() or ":" not in text:
        return None
    fields = {}
    for line in text.splitlines():
        m = NEW_TASK_FIELD_PATTERN.match(line)
        if m:
            key = m.group(1).strip().lower()
            fields[key] = m.group(2).strip()
    if "task" not in fields:
        return None  # doesn't have the one truly required field
    return fields


def intake_new_tasks(client, tasks, state):
    channel = cfg.CHANNEL_CHARLENE_TASKS
    oldest = state["last_ts"].get(channel, "0")
    resp = safe_call(client.conversations_history, channel=channel, oldest=oldest, limit=100)
    if not resp or not resp.get("ok"):
        return
    messages = sorted(resp["messages"], key=lambda m: float(m["ts"]))
    max_ts_seen = oldest
    for msg in messages:
        max_ts_seen = msg["ts"]
        if msg.get("bot_id"):
            continue  # skip our own posts
        if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]:
            continue  # this is a reply, not a new top-level message
        fields = parse_new_task_message(msg.get("text", ""))
        if not fields:
            continue

        task_id = gen_task_id(tasks)
        task = {
            "task_id": task_id,
            "task_name": fields.get("task", "").strip(),
            "instructions": fields.get("instructions", ""),
            "status": "New",
            "priority": fields.get("priority", "Normal").title(),
            "date_received": today_str(),
            "due_date": fields.get("due date", "No deadline"),
            "assigned_to": "Charlene",
            "project": fields.get("project", ""),
            "approval_needed": fields.get("pamela approval needed", "No").title(),
            "waiting_on": "",
            "next_step": "",
            "deliverable_link": "",
            "summary": "",
            "review_notes": "",
            "completion_date": "",
            "message_channel": channel,
            "message_ts": msg["ts"],
            "approval_message_ts": None,
            "last_reply_seen_ts": msg["ts"],
            "seeded": False,
        }
        tasks.append(task)

        confirmation = (
            f"*Task added*\n"
            f"Task ID: `{task_id}`\n"
            f"Status: New\n"
            f"Assigned to: Charlene\n"
            f"Priority: {task['priority']}\n"
            f"Due date: {task['due_date']}\n\n"
            f"_React on this message to change status:_ "
            f":hammer_and_wrench: In Progress · :hourglass_flowing_sand: Pending · "
            f":raising_hand: Waiting on Pamela · :eyes: For Pamela Approval · "
            f":package: Parked · :white_check_mark: Completed\n"
            f"_Or reply in this thread with `[status] Waiting on Pamela` (etc. — exact status name) "
            f"if reactions are fiddly._\n"
            f"_Reply with `[waiting] ...`, `[next] ...`, `[deliverable] ...`, "
            f"`[summary] ...`, or `[notes] ...` to fill in detail fields._"
        )
        safe_call(client.chat_postMessage, channel=channel, thread_ts=msg["ts"], text=confirmation)

    state["last_ts"][channel] = max_ts_seen


# ----------------------------------------------- 2. reactions -> status --
STATUS_PRIORITY_ORDER = [
    "Completed", "Parked", "For Pamela Approval", "Waiting on Pamela", "Pending", "In Progress",
]


def resolve_status_from_reactions(reactions):
    present = {cfg.STATUS_EMOJI[r["name"]] for r in reactions if r["name"] in cfg.STATUS_EMOJI}
    for status in STATUS_PRIORITY_ORDER:
        if status in present:
            return status
    return None


def route_notification(client, tasks, task, new_status):
    tid, name, pr, due = task["task_id"], task["task_name"], task["priority"], task["due_date"]
    link_hint = f"(task `{tid}` in #charlene-tasks)"

    if new_status == "Waiting on Pamela":
        text = (
            f":raising_hand: *Pamela's attention is needed*\n"
            f"Task: {name}\n"
            f"Needed from Pamela: {task['waiting_on'] or '_not specified yet — reply `[waiting] ...` on the task thread_'}\n"
            f"Priority: {pr}\nDue date: {due}\n{link_hint}\n<@{cfg.PAMELA_USER_ID}>"
        )
        safe_call(client.chat_postMessage, channel=cfg.CHANNEL_PAMELA_PRIORITIES, text=text)

    elif new_status == "For Pamela Approval":
        text = (
            f":eyes: *Ready for Pamela's approval*\n"
            f"Task: {name}\nCompleted by: Charlene\n"
            f"Completion summary: {task['summary'] or '_not specified yet — reply `[summary] ...`_'}\n"
            f"Deliverable: {task['deliverable_link'] or '_not specified yet — reply `[deliverable] ...`_'}\n"
            f"Due date: {due}\n{link_hint}\n<@{cfg.PAMELA_USER_ID}>\n\n"
            f"React :white_check_mark: to *approve*, or :arrows_counterclockwise: for *changes requested*."
        )
        resp = safe_call(client.chat_postMessage, channel=cfg.CHANNEL_PAMELA_APPROVAL, text=text)
        if resp:
            task["approval_message_ts"] = resp["ts"]

    elif new_status == "Parked":
        text = f":package: *Task parked*\nTask: {name}\nNotes: {task['waiting_on'] or task['next_step'] or '-'}\n{link_hint}"
        safe_call(client.chat_postMessage, channel=cfg.CHANNEL_PARKING_LOT, text=text)

    elif new_status == "Completed":
        task["completion_date"] = today_str()
        text = (
            f":white_check_mark: *Task completed*\nTask: {name}\nCompleted by: Charlene\n"
            f"Completion date: {task['completion_date']}\n"
            f"Deliverable: {task['deliverable_link'] or '-'}\n{link_hint}"
        )
        safe_call(client.chat_postMessage, channel=cfg.CHANNEL_COMPLETED_TASKS, text=text)

    # In Progress / Pending: no notification by design.


def process_reactions(client, tasks, state):
    for task in tasks:
        if task["status"] == "Completed" or not task.get("message_ts"):
            continue
        resp = safe_call(
            client.reactions_get,
            channel=cfg.CHANNEL_CHARLENE_TASKS,
            timestamp=task["message_ts"],
        )
        if not resp or not resp.get("ok"):
            print(f"[{task['task_id']}] reactions_get did not return ok: {resp}")
            continue
        reactions = resp.get("message", {}).get("reactions", [])
        print(f"[{task['task_id']}] current reactions on file: {[r['name'] for r in reactions]}")
        new_status = resolve_status_from_reactions(reactions)
        if new_status and new_status != task["status"]:
            print(f"[{task['task_id']}] STATUS CHANGE: {task['status']} -> {new_status}")
            task["status"] = new_status
            route_notification(client, tasks, task, new_status)
        elif new_status:
            print(f"[{task['task_id']}] resolved status '{new_status}' matches current status, no change")
        else:
            print(f"[{task['task_id']}] no recognized status emoji found")


# ------------------------------------------- 3. thread replies -> fields --
def process_thread_replies(client, tasks, state):
    for task in tasks:
        if not task.get("message_ts"):
            continue
        resp = safe_call(
            client.conversations_replies,
            channel=cfg.CHANNEL_CHARLENE_TASKS,
            ts=task["message_ts"],
            oldest=task.get("last_reply_seen_ts", task["message_ts"]),
            limit=50,
        )
        if not resp or not resp.get("ok"):
            continue
        replies = [m for m in resp["messages"] if m["ts"] != task["message_ts"]]
        for msg in replies:
            if msg.get("bot_id"):
                continue
            if float(msg["ts"]) <= float(task.get("last_reply_seen_ts", task["message_ts"])):
                continue
            text = msg.get("text", "").strip()
            lower = text.lower()
            if lower.startswith(cfg.TAG_STATUS):
                requested = text[len(cfg.TAG_STATUS):].strip()
                match = next((s for s in cfg.VALID_STATUSES if s.lower() == requested.lower()), None)
                if match and match != task["status"]:
                    print(f"[{task['task_id']}] [status] reply: {task['status']} -> {match}")
                    task["status"] = match
                    route_notification(client, tasks, task, match)
                elif not match:
                    safe_call(
                        client.chat_postMessage,
                        channel=cfg.CHANNEL_CHARLENE_TASKS,
                        thread_ts=task["message_ts"],
                        text=(
                            f"Didn't recognize status '{requested}'. Valid options: "
                            + ", ".join(cfg.VALID_STATUSES)
                        ),
                    )
            elif lower.startswith(cfg.TAG_WAITING_ON):
                task["waiting_on"] = text[len(cfg.TAG_WAITING_ON):].strip()
            elif lower.startswith(cfg.TAG_NEXT_STEP):
                task["next_step"] = text[len(cfg.TAG_NEXT_STEP):].strip()
            elif lower.startswith(cfg.TAG_DELIVERABLE):
                task["deliverable_link"] = text[len(cfg.TAG_DELIVERABLE):].strip()
            elif lower.startswith(cfg.TAG_SUMMARY):
                task["summary"] = text[len(cfg.TAG_SUMMARY):].strip()
            elif lower.startswith(cfg.TAG_NOTES):
                task["review_notes"] = text[len(cfg.TAG_NOTES):].strip()
            task["last_reply_seen_ts"] = msg["ts"]


# ------------------------------------------------ 4. approval decision --
def process_approval_reactions(client, tasks, state):
    for task in tasks:
        if task["status"] != "For Pamela Approval" or not task.get("approval_message_ts"):
            continue
        resp = safe_call(
            client.reactions_get,
            channel=cfg.CHANNEL_PAMELA_APPROVAL,
            timestamp=task["approval_message_ts"],
        )
        if not resp or not resp.get("ok"):
            continue
        reactions = resp.get("message", {}).get("reactions", [])
        names = {r["name"] for r in reactions}

        if "white_check_mark" in names:
            task["status"] = "Completed"
            task["completion_date"] = today_str()
            text = (
                f":white_check_mark: *Task completed (approved by Pamela)*\n"
                f"Task: {task['task_name']}\nCompleted by: Charlene\n"
                f"Completion date: {task['completion_date']}\n"
                f"Deliverable: {task['deliverable_link'] or '-'}"
            )
            safe_call(client.chat_postMessage, channel=cfg.CHANNEL_COMPLETED_TASKS, text=text)

        elif "arrows_counterclockwise" in names:
            feedback = task.get("review_notes", "")
            replies = safe_call(
                client.conversations_replies,
                channel=cfg.CHANNEL_PAMELA_APPROVAL,
                ts=task["approval_message_ts"],
                limit=20,
            )
            if replies and replies.get("ok"):
                non_bot = [m for m in replies["messages"] if not m.get("bot_id") and m["ts"] != task["approval_message_ts"]]
                if non_bot:
                    feedback = non_bot[-1].get("text", feedback)

            task["status"] = "Changes Requested"
            task["review_notes"] = feedback
            task["assigned_to"] = "Charlene"
            text = (
                f":arrows_counterclockwise: *Changes requested*\n"
                f"Task: {task['task_name']}\n"
                f"Pamela's feedback: {feedback or '_see approval thread_'}\n"
                f"(task `{task['task_id']}`)"
            )
            safe_call(client.chat_postMessage, channel=cfg.CHANNEL_CHARLENE_TASKS, text=text)


# ---------------------------------------------------------- 5. board ----
def render_task_board(tasks):
    active = [t for t in tasks if t["status"] != "Completed"]
    lines = [cfg.TASK_BOARD_HEADER, ""]
    for status in ["New", "In Progress", "Pending", "Waiting on Pamela", "For Pamela Approval", "Changes Requested", "Parked"]:
        group = [t for t in active if t["status"] == status]
        if not group:
            continue
        lines.append(f"*{status}*")
        for t in group:
            lines.append(f"  • `{t['task_id']}` {t['task_name']} — {t['priority']} — due {t['due_date']}")
        lines.append("")
    if len(lines) == 2:
        lines.append("_Nothing active right now._")
    return "\n".join(lines)


def update_task_board(client, tasks, state):
    text = render_task_board(tasks)
    ts = state.get("task_board_ts")
    if ts:
        resp = safe_call(client.chat_update, channel=cfg.CHANNEL_CHARLENE_TASKS, ts=ts, text=text)
        if resp and resp.get("ok"):
            return
    resp = safe_call(client.chat_postMessage, channel=cfg.CHANNEL_CHARLENE_TASKS, text=text)
    if resp and resp.get("ok"):
        state["task_board_ts"] = resp["ts"]
        safe_call(client.pins_add, channel=cfg.CHANNEL_CHARLENE_TASKS, timestamp=resp["ts"])


# ---------------------------------------------------- 6. weekly report --
def build_weekly_report(tasks):
    today = datetime.now(TZ).date()
    weekday = today.weekday()  # Monday=0 ... Saturday=5 ... Sunday=6
    monday = today - timedelta(days=weekday)
    friday = monday + timedelta(days=4)
    next_monday = monday + timedelta(days=7)

    def sec(status):
        return [t for t in tasks if t["status"] == status]

    completed = sec("Completed")
    waiting = sec("Waiting on Pamela")
    approval = sec("For Pamela Approval")
    in_progress = sec("In Progress")
    pending = sec("Pending")
    parked = sec("Parked")
    overdue = [
        t for t in tasks
        if t["status"] not in ("Completed", "Parked")
        and t["due_date"] not in ("", "No deadline")
        and _is_past_or_today(t["due_date"], today)
    ]

    def fmt(t, extra=""):
        return f"• `{t['task_id']}` {t['task_name']}{extra}"

    def section(items, formatter=fmt):
        return [formatter(t) for t in items] if items else ["_None_"]

    lines = [
        "*Weekly Production Status*",
        f"*Reporting period:* {monday.strftime('%b %d')}–{friday.strftime('%b %d')}",
        f"*Prepared for:* Monday, {next_monday.strftime('%b %d')}",
        "",
        "*Completed this week*",
        *section(completed),
        "",
        "*Waiting on Pamela*",
        *section(waiting, lambda t: fmt(t, f" — needs: {t['waiting_on'] or 'see task'}")),
        "",
        "*Ready for Pamela's approval*",
        *section(approval),
        "",
        "*In progress*",
        *section(in_progress, lambda t: fmt(t, f" — next: {t['next_step'] or 'n/a'}")),
        "",
        "*Pending*",
        *section(pending, lambda t: fmt(t, f" — {t['waiting_on'] or 'reason not logged'}")),
        "",
        "*Overdue or at risk*",
        *section(overdue, lambda t: fmt(t, f" — due {t['due_date']}")),
        "",
        "*Parked*",
        *section(parked),
        "",
        "_Recommended Monday priorities and coming-week deadlines: review the above with Pamela "
        "live — this bot doesn't guess at priority calls._",
    ]
    return "\n".join(lines)


def _is_past_or_today(due_date_str, today):
    try:
        d = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        return d <= today
    except ValueError:
        return False


def maybe_send_weekly_report(client, tasks, state):
    now = datetime.now(TZ)
    if now.weekday() != 5:  # 5 = Saturday
        return
    today = now.strftime("%Y-%m-%d")
    if state.get("last_weekly_report_date") == today:
        return  # already sent today

    report = build_weekly_report(tasks)
    safe_call(client.chat_postMessage, channel=cfg.CHANNEL_MONDAY_EMAIL, text=report)

    state["last_weekly_report_date"] = today


# --------------------------------------------------------------- main ---
def main():
    token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=token)

    tasks = load_json(cfg.TASKS_FILE, [])
    state = load_json(cfg.STATE_FILE, {"last_ts": {}, "task_board_ts": None, "last_weekly_report_date": None})

    intake_new_tasks(client, tasks, state)
    process_reactions(client, tasks, state)
    process_thread_replies(client, tasks, state)
    process_approval_reactions(client, tasks, state)
    update_task_board(client, tasks, state)
    maybe_send_weekly_report(client, tasks, state)

    save_json(cfg.TASKS_FILE, tasks)
    save_json(cfg.STATE_FILE, state)
    print(f"Run complete. {len(tasks)} tasks on file.")


if __name__ == "__main__":
    main()
