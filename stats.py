"""Draws the two cards in the profile README from the GitHub API:

    generated/overview.svg     stars, forks, repositories, followers, contributions
    generated/languages.svg    languages by bytes of code, across my own repositories

    python3 stats.py           # .github/workflows/stats.yml runs this every week

Forks don't count. With GITHUB_TOKEN set (as it is in the workflow) it also
shows the contributions of the last year; without it, 60 requests an hour are
allowed, enough to run this once.
"""

import hashlib
import html
import json
import os
import pathlib
import urllib.request

USER = os.environ.get("GITHUB_REPOSITORY_OWNER") or "dzutrinh"
TOKEN = os.environ.get("GITHUB_TOKEN")
CACHE = os.environ.get("STATS_CACHE")  # a folder to keep API answers in, while working on the drawing
OUT = pathlib.Path(__file__).parent / "generated"

W, H, PAD = 400, 170, 20
TOP = 7  # languages shown by name; the rest are "Other"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

# Eight series colors that stay apart for color-blind readers, for a light and
# a dark card. A language keeps the slot it first got (generated/languages.json).
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]

STYLE = f"""
text {{ font-family: {FONT}; }}
.card {{ fill: #fcfcfb; stroke: #e3e2de; }}
.title {{ font-size: 15px; font-weight: 600; fill: #0b0b0b; }}
.label {{ font-size: 13px; fill: #52514e; }}
.value {{ font-size: 13px; font-weight: 600; fill: #0b0b0b; }}
.gap {{ fill: #fcfcfb; }}
.other {{ fill: #a3a29b; }}
{" ".join(f".s{i} {{ fill: {c}; }}" for i, c in enumerate(LIGHT))}
@media (prefers-color-scheme: dark) {{
.card {{ fill: #1a1a19; stroke: #383835; }}
.title, .value {{ fill: #f0efec; }}
.label {{ fill: #c3c2b7; }}
.gap {{ fill: #1a1a19; }}
.other {{ fill: #6f6e68; }}
{" ".join(f".s{i} {{ fill: {c}; }}" for i, c in enumerate(DARK))}
}}
"""


def api(path, query=None):
    """GET https://api.github.com/PATH, or POST a GraphQL query."""
    key = hashlib.sha1((path + (query or "")).encode()).hexdigest()[:16]
    cached = pathlib.Path(CACHE) / f"{key}.json" if CACHE else None
    if cached and cached.exists():
        return json.loads(cached.read_text())
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps({"query": query}).encode() if query else None
    with urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/{path}", data, headers)) as r:
        answer = json.load(r)
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(answer))
    return answer


def card(title, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="{html.escape(label, quote=True)}">\n<style>{STYLE}</style>\n'
        f'<rect class="card" x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="8"/>\n'
        f'<text class="title" x="{PAD}" y="33">{html.escape(title)}</text>\n{body}</svg>\n'
    )


def overview(name, rows):
    body = ""
    for i, (label, value) in enumerate(rows):
        y = 62 + i * 23
        body += f'<text class="label" x="{PAD}" y="{y}">{label}</text>'
        body += f'<text class="value" x="{W - PAD}" y="{y}" text-anchor="end">{value:,}</text>\n'
    return card(f"{name}'s GitHub", body, "; ".join(f"{label}: {value:,}" for label, value in rows))


def languages(shares, slots):
    """shares: (language, fraction) from the largest, "Other" last."""
    width, x, body = W - 2 * PAD, 0.0, '<clipPath id="bar"><rect x="%d" y="50" width="%d" height="10" rx="4"/></clipPath>\n' % (PAD, W - 2 * PAD)
    body += '<g clip-path="url(#bar)">\n'
    for i, (lang, share) in enumerate(shares):
        w = share * width
        body += f'<rect class="{slots[lang]}" x="{PAD + x:.1f}" y="50" width="{w:.1f}" height="10"/>'
        if i:  # two pixels of the card between neighbors
            body += f'<rect class="gap" x="{PAD + x - 1:.1f}" y="50" width="2" height="10"/>'
        body += "\n"
        x += w
    body += "</g>\n"
    for i, (lang, share) in enumerate(shares):  # the legend: two columns, each name with its share
        lx, ly = PAD + (i % 2) * (width / 2 + 6), 86 + (i // 2) * 21
        percent = f"{share:.1%}" if share >= 0.001 else "&lt;0.1%"
        body += f'<rect class="{slots[lang]}" x="{lx:.0f}" y="{ly - 10}" width="10" height="10" rx="2"/>'
        body += f'<text class="label" x="{lx + 17:.0f}" y="{ly}">{html.escape(lang)}</text>'
        body += f'<text class="value" x="{lx + width / 2 - 14:.0f}" y="{ly}" text-anchor="end">{percent}</text>\n'
    return card("Languages, by bytes of code", body, "; ".join(f"{lang}: {share:.1%}" for lang, share in shares))


def main():
    user = api(f"users/{USER}")
    repos, page = [], 1
    while True:
        batch = api(f"users/{USER}/repos?type=owner&per_page=100&page={page}")
        repos += [r for r in batch if not r["fork"]]
        if len(batch) < 100:
            break
        page += 1

    rows = [
        ("Stars earned", sum(r["stargazers_count"] for r in repos)),
        ("Forks of my repositories", sum(r["forks_count"] for r in repos)),
        ("Public repositories", len(repos)),
        ("Followers", user["followers"]),
    ]
    if TOKEN:
        try:
            q = '{ user(login: "%s") { contributionsCollection { contributionCalendar { totalContributions } } } }' % USER
            total = api("graphql", q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
            rows.append(("Contributions in the last year", total))
        except Exception as e:  # the card is still worth drawing without it
            print("no contributions:", e)

    size = {}
    for r in repos:
        for lang, n in api(f"repos/{r['full_name']}/languages").items():
            size[lang] = size.get(lang, 0) + n
    total = sum(size.values()) or 1
    ranked = sorted(size.items(), key=lambda kv: -kv[1])

    OUT.mkdir(exist_ok=True)
    memory = OUT / "languages.json"  # which slot each language has, so its color doesn't change from week to week
    slots = json.loads(memory.read_text()) if memory.exists() else {}
    slots = {lang: s for lang, s in slots.items() if lang in size}
    shown = []
    for lang, n in ranked:
        free = [f"s{i}" for i in range(len(LIGHT)) if f"s{i}" not in slots.values()]
        if len(shown) < TOP and n / total >= 0.005 and (lang in slots or free):
            slots.setdefault(lang, free[0] if free else None)
            shown.append((lang, n / total))
    slots = {lang: slots[lang] for lang, _ in shown}
    rest = 1 - sum(share for _, share in shown)
    if rest > 0.0005:
        shown.append(("Other", rest))

    memory.write_text(json.dumps(slots, indent=1) + "\n")
    (OUT / "overview.svg").write_text(overview(user.get("name") or USER, rows), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages(shown, {**slots, "Other": "other"}), encoding="utf-8")
    for label, value in rows:
        print(f"{value:>8,}  {label}")
    for lang, share in shown:
        print(f"{share:>8.1%}  {lang}")


main()
