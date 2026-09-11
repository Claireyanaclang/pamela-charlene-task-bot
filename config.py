"""
Central configuration for the Pamela & Charlene task bot.

Everything workspace-specific lives here so bot.py never has magic
strings scattered through it. Edit this file (not bot.py) if a
channel ID, user ID, or emoji mapping ever needs to change.
"""

# --- Channel IDs (already created in Slack) ---------------------------
CHANNEL_CHARLENE_TASKS = "C0C16B1FMK3"
CHANNEL_PAMELA_PRIORITIES = "C0C14B0F7J6"
CHANNEL_PAMELA_APPROVAL = "C0C0P25SJFR"
CHANNEL_COMPLETED_TASKS = "C0C12EXU6TY"
CHANNEL_PARKING_LOT = "C0C0KNUTVP1"
CHANNEL_PAMELA_IDEAS = "C0C0JU3BX0F"
CHANNEL_PRODUCTION_STATUS = "C0C12EHLKKK"

# --- People -------------------------------------------------------------
PAMELA_USER_ID = "U0C123A3U68"
# NOTE: verify this is actually Charlene's ID before relying on it —
# it was the "current logged in user" at build time, confirm in Slack
# (click your own profile -> "Copy member ID").
CHARLENE_USER_ID = "U0C126ZT82G"

# --- Status <-> emoji reaction mapping -----------------------------------
# Charlene sets these by reacting on the task's own message in
# #charlene-tasks. Reacting with a NEW emoji from this list overwrites
# the task's status (the bot always looks at the most recent one added).
STATUS_EMOJI = {
    "hammer_and_wrench": "In Progress",         # 🛠️
    "hourglass_flowing_sand": "Pending",        # ⏳
    "raising_hand": "Waiting on Pamela",        # 🙋
    "eyes": "For Pamela Approval",              # 👀
    "package": "Parked",                        # 📦
    "white_check_mark": "Completed",            # ✅
}
# Reverse lookup, used when the bot posts "react with X" instructions.
EMOJI_FOR_STATUS = {v: k for k, v in STATUS_EMOJI.items()}

# Reactions Pamela adds on the bot's post inside #pamela-approval.
APPROVAL_EMOJI = {
    "white_check_mark": "approved",
    "arrows_counterclockwise": "changes_requested",
}

# --- Thread-reply tags ---------------------------------------------------
# Charlene supplies extra detail by replying in a task's thread with a
# message that STARTS with one of these tags (case-insensitive).
TAG_WAITING_ON = "[waiting]"
TAG_NEXT_STEP = "[next]"
TAG_DELIVERABLE = "[deliverable]"
TAG_SUMMARY = "[summary]"
TAG_NOTES = "[notes]"

ALL_TAGS = [TAG_WAITING_ON, TAG_NEXT_STEP, TAG_DELIVERABLE, TAG_SUMMARY, TAG_NOTES]

# --- Files used as the "database" ----------------------------------------
TASKS_FILE = "tasks.json"
STATE_FILE = "state.json"

# --- Misc -----------------------------------------------------------------
TASK_ID_PREFIX = "CT"
TASK_BOARD_HEADER = ":clipboard: *Task Board — live snapshot*\n_Updated automatically. Do not edit this message._"
