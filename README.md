# Pamela & Charlene Task Bot — Setup Guide

This replaces Slack Lists + Workflow Builder (both paid-only) with free code:
a small Python script, a free Slack app, and GitHub's free scheduler.

**Before you start:** verify `CHARLENE_USER_ID` in `config.py` is actually
correct. In Slack, click your own name/profile photo → **⋮ More** →
**Copy member ID**, and compare it to the value already in the file
(`U0C126ZT82G`). If it's different, edit `config.py` and change it (you can
edit files directly in GitHub's web UI — no coding tools needed).

---

## Step 1 — Create a free Slack app (the bot's identity)

1. Go to **https://api.slack.com/apps** and sign in with your Slack account.
2. Click **Create New App → From scratch**.
3. Name it (e.g. "Task Bot") and pick your **thrivecollective-corp** workspace.
4. In the left sidebar, click **OAuth & Permissions**.
5. Scroll to **Scopes → Bot Token Scopes** and add each of these one at a
   time (search box, click to add):
   - `chat:write`
   - `groups:history`
   - `reactions:read`
   - `im:write`
   - `pins:write`
6. Scroll back to the top of that page and click **Install to Workspace**,
   then **Allow**.
7. Copy the **Bot User OAuth Token** — it starts with `xoxb-`. Keep this
   somewhere safe for Step 3; don't paste it into Slack itself or anywhere
   public.

## Step 2 — Invite the bot into all 7 channels

Slack bots can't see or post in private channels until invited, even with
the right permissions. In Slack, go to each of these and type
`/invite @Task Bot` (or whatever you named it) as a message:

- `#charlene-tasks`
- `#pamela-priorities`
- `#pamela-approval`
- `#completed-tasks`
- `#parking-lot`
- `#pamela-ideas` *(not used by the bot yet, but fine to include)*
- `#production-status`

## Step 3 — Put this code on GitHub (free)

1. Go to **https://github.com** and sign up if you don't have an account —
   free, no credit card.
2. Click **New repository**. Name it e.g. `pamela-charlene-task-bot`, set
   it to **Private**, click **Create repository**.
3. On the new repo's page, click **uploading an existing file** and drag
   in every file and folder here — **including the `.github` folder with
   `workflows` inside it**. GitHub's uploader preserves folder structure
   if you drag the whole folder in at once.
4. Click **Commit changes**.

## Step 4 — Give the bot its token, securely

1. In your new repo, click **Settings** (top tab) → **Secrets and
   variables → Actions** (left sidebar) → **New repository secret**.
2. Name: `SLACK_BOT_TOKEN`
3. Value: paste the `xoxb-...` token from Step 1.
4. Click **Add secret**.

This keeps the token out of the code entirely — GitHub injects it only
while the bot is running, and nobody (including you looking at the repo
later) can see it again once saved.

## Step 5 — Turn on Actions

Click the **Actions** tab in your repo. If you see a banner asking you to
enable workflows, click it. You should see two workflows listed:
**Run task bot** (the recurring one, every 15 minutes) and **Seed backlog
(run once)**.

## Step 6 — Seed the 13 real backlog tasks

1. Still in the **Actions** tab, click **Seed backlog (run once)** in the
   left list.
2. Click the **Run workflow** button (top right), then **Run workflow**
   again to confirm.
3. Wait about 30 seconds, then check `#charlene-tasks` in Slack — you
   should see 13 new "Backlog import" messages.

This step only needs to happen once. Re-running it by accident is safe —
already-seeded tasks are skipped.

## Step 7 — Confirm the recurring bot is alive

Back in the Actions tab, click **Run task bot**, then **Run workflow** to
trigger it manually the first time (don't wait 15 minutes). Watch the run;
green check = it worked. After that it runs on its own every 15 minutes,
no further action needed.

---

## How to actually use it day to day

**New task:** type it in `#charlene-tasks` exactly like before:
```
New Task
Task: [name]
Instructions: [details]
Date received: [date]
Due date: [date or No deadline]
Priority: [Urgent/High/Normal/Low]
Pamela approval needed: [Yes/No]
Project: [name]
```
Within 15 minutes, the bot replies in-thread confirming it was filed.

**Change status:** react to the task's own message with one emoji:

| Emoji | Status |
|---|---|
| 🛠️ `:hammer_and_wrench:` | In Progress |
| ⏳ `:hourglass_flowing_sand:` | Pending |
| 🙋 `:raising_hand:` | Waiting on Pamela |
| 👀 `:eyes:` | For Pamela Approval |
| 📦 `:package:` | Parked |
| ✅ `:white_check_mark:` | Completed |

Use **one at a time** — if you change your mind, remove the old reaction
before adding the new one, so the bot isn't guessing between two.

**Add detail:** reply in the task's thread starting with a tag:
```
[waiting] Need Pamela's decision on brand colors
[next] Will send draft copy Tuesday
[deliverable] https://...
[summary] All 20 sections updated, ready for review
[notes] Pamela's feedback goes here
```

**Pamela's approval decision:** she reacts ✅ or 🔁
(`:arrows_counterclockwise:`) directly on the bot's post in
`#pamela-approval`.

**Weekly report:** posts automatically to `#production-status` and DMs
Pamela every Saturday — no action needed.

---

## Known limitations, stated honestly

- **Not instant.** Every 15 minutes, not real-time. Reacting to a task
  won't post a notification the same second — it'll show up on the next
  scheduled run.
- **No hard-required fields.** Unlike a real form, nothing stops you from
  setting "Waiting on Pamela" without filling in `[waiting]` first — the
  bot will just say "not specified yet" in the notification until you add it.
- **One emoji per task at a time.** Two status emoji on the same message
  and the bot picks whichever is "furthest along" in the workflow, which
  may not be what you meant — remove the old one before adding a new one.
- **If something breaks:** check the **Actions** tab — every run's log is
  there, and a red X means it hit an error. Paste that error back to
  Claude and it can debug it with you.
