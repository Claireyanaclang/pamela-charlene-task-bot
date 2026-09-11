"""
One-time backfill: posts the 13 real tasks already known from this
week's Pamela updates into #charlene-tasks (so they become reactable)
and adds them to tasks.json.

Run this ONCE, manually, after setup is verified working:
    python seed_tasks.py

Safe to re-run: it skips any task_id already present in tasks.json.
"""

import os
from slack_sdk import WebClient

import config as cfg
from bot import load_json, save_json, today_str

SEED_TASKS = [
    dict(task_id="CT-20260911-01", task_name="Bounce Back sales page - ClickFunnels build",
         instructions="All 20 sections updated with new Bounce Back copy in ClickFunnels. Deleted Part 9 "
                       "($608 value) and Part 10 (Fast Action Bonus). Backgrounds changed to black in Parts "
                       "3 and 5. Buttons updated to 'Get BOUNCE BACK - $[PRICE]'. Part 15 (6 customer quotes) "
                       "left untouched. Part 16 wording left unchanged. Part 19 button removed. Bold/italic/"
                       "underline applied to emotional lines. $[PRICE] placeholder kept as instructed.",
         status="For Pamela Approval", priority="High", project="Bounce Back", approval_needed="Yes",
         due_date="No deadline",
         waiting_on="Final price for the $[PRICE] placeholder; Part 7 course image still shows old Craving "
                    "Crusher branding; Part 6 duplicate text deleted, please confirm; Part 12 please confirm "
                    "the i in CRAViNG/REWiRED shows yellow live."),
    dict(task_id="CT-20260911-02", task_name="Bounce Back tracker - completed and uploaded to Drive",
         instructions="Section-by-section tracker for all 20 Bounce Back page parts filled in and uploaded "
                       "to Google Drive under 'Sales Page Updates September ClickFunnels.'",
         status="Completed", priority="Normal", project="Bounce Back", approval_needed="No",
         due_date="No deadline", completion_date=today_str()),
    dict(task_id="CT-20260911-03", task_name="Craving Crusher page - ClickFunnels updates",
         instructions="Added FAQ section; added The Movement section; updated Fast Action Bonus to 100 "
                       "buyers - 30% off Bounce Back; confirmed footer; optimized for desktop and mobile.",
         status="For Pamela Approval", priority="High", project="Craving Crusher", approval_needed="Yes",
         due_date="No deadline"),
    dict(task_id="CT-20260911-04", task_name="LinkedIn strategy and research setup",
         instructions="Reviewed Chris Donnelly's video/playbook; saved to Drive; created Chris Donnelly and "
                       "Lara Acosta folders; defined content strategy (Chris=funnel, Lara=post structure, "
                       "Pamela=voice/content); created Chris Donnelly Claude thread; reviewed and saved "
                       "Cristina Galbato content examples through Sept 7.",
         status="Completed", priority="Normal", project="LinkedIn / Content", approval_needed="No",
         due_date="No deadline", completion_date=today_str()),
    dict(task_id="CT-20260911-05", task_name="Insight Timer upload process - need Pamela's walkthrough",
         instructions="Need Pamela to record or show how she wants the Insight Timer upload process handled "
                       "so Charlene can do it independently going forward.",
         status="Waiting on Pamela", priority="Normal", project="Insight Timer", approval_needed="No",
         due_date="No deadline", waiting_on="Pamela to record/demo the preferred upload process."),
    dict(task_id="CT-20260911-06", task_name="LinkedIn Canva graphics - review needed (URGENT)",
         instructions="Canva graphics for LinkedIn ready for review for 2+ weeks - the oldest outstanding item.",
         status="Waiting on Pamela", priority="Urgent", project="LinkedIn / Content", approval_needed="No",
         due_date="No deadline", waiting_on="Pamela's review/approval of the Canva graphics.",
         deliverable_link="canva.link/f1ukiqyr9gfe678  (UNCONFIRMED - two emails gave slightly different links, verify with Pamela)"),
    dict(task_id="CT-20260911-07", task_name="YouTube video edits - Descript",
         instructions="Video edits completed in Descript, ready for Pamela's review.",
         status="For Pamela Approval", priority="Normal", project="YouTube", approval_needed="Yes",
         due_date="No deadline"),
    dict(task_id="CT-20260911-08", task_name="Insight Timer video edits - Descript",
         instructions="Video edits completed in Descript, ready for Pamela's review.",
         status="For Pamela Approval", priority="Normal", project="Insight Timer", approval_needed="Yes",
         due_date="No deadline"),
    dict(task_id="CT-20260911-09", task_name="Superhuman Mail setup - approval to proceed",
         instructions="Research completed (Split Inbox, organization, shortcuts, email tracking). Ready to "
                       "proceed pending Pamela's approval.",
         status="Waiting on Pamela", priority="Normal", project="Superhuman Mail", approval_needed="No",
         due_date="No deadline", waiting_on="Pamela's approval to proceed with setup."),
    dict(task_id="CT-20260911-10", task_name="Podcast guest-booking platform - awaiting platform choice",
         instructions="Research completed on podcast guest-booking platforms for the I DO NOT DRINK movement.",
         status="Waiting on Pamela", priority="Normal", project="I DO NOT DRINK", approval_needed="No",
         due_date="No deadline", waiting_on="Pamela's preferred platform choice."),
    dict(task_id="CT-20260911-11", task_name="AKA Monday email - confirm content",
         instructions="Setting up the AKA Monday email; need Pamela's confirmation on exactly what to include.",
         status="Waiting on Pamela", priority="Normal", project="AKA", approval_needed="No",
         due_date="No deadline", waiting_on="Confirmation of what content to include."),
    dict(task_id="CT-20260911-12", task_name="Apply Chris Donnelly framework to LinkedIn content",
         instructions="Review the Chris Donnelly Claude project and use the strategy/framework there for "
                       "LinkedIn content development.",
         status="In Progress", priority="Normal", project="LinkedIn / Content", approval_needed="No",
         due_date="No deadline"),
    dict(task_id="CT-20260911-13", task_name="Pull content ideas from Cristina Galbato project",
         instructions="Review the Cristina Galbato Claude project and continue pulling relevant content "
                       "ideas, hooks, and examples for the Instagram/LinkedIn workflow.",
         status="In Progress", priority="Normal", project="Instagram/LinkedIn", approval_needed="No",
         due_date="No deadline"),
]


def format_seed_message(t):
    return (
        f":inbox_tray: *Backlog import — {t['task_id']}*\n"
        f"Task: {t['task_name']}\n"
        f"Instructions: {t['instructions']}\n"
        f"Status: {t['status']}\nPriority: {t['priority']}\nProject: {t['project']}\n"
        f"Pamela approval needed: {t['approval_needed']}\n\n"
        f"_This task existed before the bot went live and was backfilled from this week's emails. "
        f"React to change status, reply with `[waiting]`/`[next]`/`[deliverable]`/`[summary]`/`[notes]` to add detail._"
    )


def main():
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    tasks = load_json(cfg.TASKS_FILE, [])
    existing_ids = {t["task_id"] for t in tasks}

    for seed in SEED_TASKS:
        if seed["task_id"] in existing_ids:
            print(f"Skipping {seed['task_id']} - already in tasks.json")
            continue

        resp = client.chat_postMessage(channel=cfg.CHANNEL_CHARLENE_TASKS, text=format_seed_message(seed))
        ts = resp["ts"]

        task = {
            "task_id": seed["task_id"],
            "task_name": seed["task_name"],
            "instructions": seed["instructions"],
            "status": seed["status"],
            "priority": seed["priority"],
            "date_received": today_str(),
            "due_date": seed.get("due_date", "No deadline"),
            "assigned_to": "Charlene",
            "project": seed["project"],
            "approval_needed": seed["approval_needed"],
            "waiting_on": seed.get("waiting_on", ""),
            "next_step": seed.get("next_step", ""),
            "deliverable_link": seed.get("deliverable_link", ""),
            "summary": seed.get("summary", ""),
            "review_notes": "",
            "completion_date": seed.get("completion_date", ""),
            "message_channel": cfg.CHANNEL_CHARLENE_TASKS,
            "message_ts": ts,
            "approval_message_ts": None,
            "last_reply_seen_ts": ts,
            "seeded": True,
        }
        tasks.append(task)
        print(f"Seeded {seed['task_id']}")

    save_json(cfg.TASKS_FILE, tasks)
    print(f"Done. {len(tasks)} tasks now on file.")


if __name__ == "__main__":
    main()
