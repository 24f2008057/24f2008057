"""Refreshes the auto-generated sections of README.md using the GitHub API."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

# EDIT: repo and user are configurable via env vars (set in the workflow)
FEATURED_REPO = os.environ.get("FEATURED_REPO", "ostadsanjoy/quizpup")
ACTIVITY_USER = os.environ.get("ACTIVITY_USER", "24f2008057")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except Exception as exc:  # network error, 404, rate limit: skip instead of failing the workflow
        print(f"API call failed for {path}: {exc}")
        return None


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def ago(ts):
    secs = (datetime.now(timezone.utc) - parse(ts)).total_seconds()
    mins = int(secs // 60)
    if mins < 60:
        return f"{max(mins, 1)}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


# EDIT: builds the QuizPup stats table (stars, forks, issues, latest release, last push)
def build_stats():
    repo = api(f"/repos/{FEATURED_REPO}")
    if not repo:
        return None
    release = api(f"/repos/{FEATURED_REPO}/releases/latest")
    if release and release.get("tag_name"):
        rel = f"[{release['tag_name']}]({release['html_url']})"
    else:
        rel = "-"
    return (
        "| ⭐ Stars | 🍴 Forks | 🐞 Open issues | 🚀 Latest release | 🕒 Last push |\n"
        "|:-:|:-:|:-:|:-:|:-:|\n"
        f"| **{repo['stargazers_count']}** | **{repo['forks_count']}** | "
        f"**{repo['open_issues_count']}** | {rel} | {ago(repo['pushed_at'])} |"
    )


# EDIT: builds the recent-activity list from the user's public push events
def build_activity():
    events = api(f"/users/{ACTIVITY_USER}/events/public?per_page=100")
    if events is None:
        return None
    lines, seen = [], set()
    for ev in events:
        if ev.get("type") != "PushEvent":
            continue
        name = ev["repo"]["name"]
        if name in seen:
            continue
        seen.add(name)
        commits = ev.get("payload", {}).get("commits") or []
        msg = commits[-1]["message"].splitlines()[0] if commits else "pushed new commits"
        msg = msg.replace("|", "/")[:70]
        lines.append(f"- 🔨 [`{name}`](https://github.com/{name}): {msg} · _{ago(ev['created_at'])}_")
        if len(lines) == 5:
            break
    return "\n".join(lines) if lines else "_No recent public activity._"


# EDIT: swaps the text between a pair of START/END marker comments
def replace_block(text, tag, content):
    pattern = re.compile(rf"(<!--{tag}:START-->)(.*?)(<!--{tag}:END-->)", re.DOTALL)
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    stats = build_stats()
    if stats:
        text = replace_block(text, "QUIZPUP_STATS", stats)
    activity = build_activity()
    if activity:
        text = replace_block(text, "ACTIVITY", activity)
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()