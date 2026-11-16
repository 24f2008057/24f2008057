"""Refreshes the auto-generated sections of README.md using the GitHub API."""
import hashlib
import html
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

FEATURED_REPO = os.environ.get("FEATURED_REPO", "ostadsanjoy/quizpup")
ACTIVITY_USER = os.environ.get("ACTIVITY_USER", "24f2008057")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
STATS_SVG = "assets/quizpup-stats.svg"


# EDIT: api() can now also return response headers (needed to read the commit count from the Link header)
def api(path, want_headers=False):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
            return (data, resp.headers) if want_headers else data
    except Exception as exc:  # network error, 404, rate limit: skip instead of failing the workflow
        print(f"API call failed for {path}: {exc}")
        return (None, None) if want_headers else None


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def ago(ts):
    mins = int((datetime.now(timezone.utc) - parse(ts)).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


# EDIT: draws the stats card as a self-hosted SVG (stars, commits, release, last push, last commit message)
def render_stats_svg(stars, commits, release, pushed, message, message_ago):
    msg = message if len(message) <= 78 else message[:75] + "..."
    rel_size = 38 if len(release) <= 6 else 28
    cols = [
        (112, str(stars), "STARS", 38),
        (337, str(commits), "COMMITS", 38),
        (562, release, "LATEST RELEASE", rel_size),
        (787, pushed, "LAST PUSH", 34),
    ]
    cells = ""
    for x, value, label, size in cols:
        cells += (
            f'<text x="{x}" y="72" text-anchor="middle" font-size="{size}" font-weight="700" fill="url(#g)">{html.escape(value)}</text>'
            f'<text x="{x}" y="100" text-anchor="middle" font-size="11.5" letter-spacing="2.5" fill="#7d8da6">{label}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="176" viewBox="0 0 900 176" role="img" aria-label="QuizPup repository stats">
  <defs>
    <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="900" y2="0">
      <stop offset="0" stop-color="#6cb6ff"/><stop offset="1" stop-color="#b392f0"/>
    </linearGradient>
    <linearGradient id="e" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6cb6ff" stop-opacity="0.5"/><stop offset="0.5" stop-color="#ffffff" stop-opacity="0.06"/><stop offset="1" stop-color="#b392f0" stop-opacity="0.5"/>
    </linearGradient>
    <style>text {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}</style>
  </defs>
  <rect x="1" y="1" width="898" height="174" rx="20" fill="#0c1324"/>
  <rect x="1" y="1" width="898" height="174" rx="20" fill="none" stroke="url(#e)" stroke-width="1.5"/>
  {cells}
  <g stroke="#1f2a44" stroke-width="1">
    <line x1="225" y1="34" x2="225" y2="108"/><line x1="450" y1="34" x2="450" y2="108"/><line x1="675" y1="34" x2="675" y2="108"/>
    <line x1="36" y1="128" x2="864" y2="128"/>
  </g>
  <circle cx="44" cy="152" r="4" fill="#6cb6ff"/>
  <text x="58" y="157" font-size="11.5" font-weight="600" letter-spacing="2" fill="#6cb6ff">LATEST COMMIT</text>
  <text x="204" y="157" font-size="14" fill="#c9d1d9">{html.escape(msg)}</text>
  <text x="864" y="157" text-anchor="end" font-size="13" fill="#7d8da6">{html.escape(message_ago)}</text>
</svg>
"""


# EDIT: collects repo data (stars, commit count, latest commit message, release) and writes the stats SVG
def build_stats():
    repo = api(f"/repos/{FEATURED_REPO}")
    if not repo:
        return None
    release = api(f"/repos/{FEATURED_REPO}/releases/latest")
    tag = release["tag_name"] if release and release.get("tag_name") else "-"

    commits, headers = api(f"/repos/{FEATURED_REPO}/commits?per_page=1", True)
    if not commits:
        return None
    total = len(commits)
    link = headers.get("Link") if headers else None
    if link:
        match = re.search(r'[?&]page=(\d+)>; rel="last"', link)
        if match:
            total = int(match.group(1))
    last = commits[0]["commit"]
    message = last["message"].splitlines()[0]
    when = ago(last["committer"]["date"])

    svg = render_stats_svg(repo["stargazers_count"], total, tag, ago(repo["pushed_at"]), message, when)
    os.makedirs(os.path.dirname(STATS_SVG), exist_ok=True)
    with open(STATS_SVG, "w", encoding="utf-8") as f:
        f.write(svg)
    version = hashlib.md5(svg.encode("utf-8")).hexdigest()[:8]
    return (
        f'<a href="https://github.com/{FEATURED_REPO}/commits">'
        f'<img src="{STATS_SVG}?v={version}" width="100%" alt="QuizPup stats"/></a>'
    )


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