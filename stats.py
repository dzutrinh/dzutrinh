"""Draws the two pictures in the profile README, as text in a terminal:

    generated/banner.svg    my name in ASCII art with colors going round, stars,
                            a typed "whoami", and my repositories scrolling by
    generated/stats.svg     numbers from the GitHub API, and languages by bytes of code

    python3 stats.py        # .github/workflows/stats.yml runs this every week

Every piece of text sits on a grid of character cells, so it lines up in
whichever monospace font the reader's computer has. Forks don't count. With
GITHUB_TOKEN set (as it is in the workflow) the stats also show the
contributions of the last year; without it, 60 requests an hour are allowed,
enough to run this once.
"""

import hashlib
import html
import json
import os
import pathlib
import random
import re
import urllib.request

USER = os.environ.get("GITHUB_REPOSITORY_OWNER")
TOKEN = os.environ.get("GITHUB_TOKEN")
CACHE = os.environ.get("STATS_CACHE")  # a folder to keep API answers in, while working on the drawing
OUT = pathlib.Path(__file__).parent / "generated"

# What "whoami" prints: a tag, then the line. Edit these and run the script.
INFO = [
    ("research", "Data Mining Researcher: high-utility itemset and pattern mining"),
    ("play", "Retro Games | Text-Mode and Terminal UIs | DOS"),
    ("code", "Pascal | C | Swift | x86 Assembly"),
    ("pixels", "Color quantization, dithering, ray casting, a NES emulator in Pascal"),
    ("mac", "Small macOS utilities in Swift"),
]

# ------------------------------------------------------------------- the grid

COLS = 90  # characters across
CW, LH = 8.4, 19  # a cell, in pixels, for 14px text
PAD, BAR = 22, 30  # space at the sides; the height of the title bar
W = round(COLS * CW + 2 * PAD)
FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', 'DejaVu Sans Mono', monospace"

# Eight hues that stay apart for color-blind readers: darker for bars, lighter for text.
MARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
TEXT = ["#6eaaf2", "#f28c5e", "#3fd09c", "#eab63e", "#ef86ae", "#58c458", "#ada3f3", "#f28585"]

STYLE = f"""
text {{ font-family: {FONT}; font-size: 14px; fill: #f0efec; }}
.screen {{ fill: #1a1a19; stroke: #383835; }}
.bar {{ fill: #26262a; }}
.dim {{ fill: #8a897f; }}
.sec {{ fill: #c3c2b7; }}
.b {{ font-weight: 700; }}
.other {{ fill: #6f6e68; }}
{" ".join(f".h{i} {{ fill: {c}; }}" for i, c in enumerate(TEXT))}
{" ".join(f".s{i} {{ fill: {c}; }}" for i, c in enumerate(MARK))}
.t {{ animation: on .01s linear backwards; }}
.fade {{ animation: on .5s ease-out backwards; }}
@keyframes on {{ from {{ opacity: 0; }} }}
@keyframes off {{ to {{ opacity: 0; }} }}
.cur {{ fill: #f0efec; animation: blink 1s steps(1) infinite; }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
.star {{ animation: twinkle 3.2s ease-in-out infinite; }}
@keyframes twinkle {{ 0%, 100% {{ opacity: .12; }} 50% {{ opacity: .95; }} }}
.logo g {{ animation: hue 8s linear infinite; }}
.logo text {{ fill: inherit; }}
@keyframes hue {{ {" ".join(f"{i * 12.5:g}% {{ fill: {c}; }}" for i, c in enumerate(TEXT + TEXT[:1]))} }}
@media (prefers-reduced-motion: reduce) {{
* {{ animation: none !important; }}
.typing {{ display: none; }}
}}
"""


def x_of(col):
    return PAD + col * CW


def y_of(row):  # the baseline of a row
    return BAR + 14 + row * LH + 14


def text(col, row, s, cls="", delay=None, step=0.0, y=None):
    """The words of s, each in its cells. With a delay they appear one after another."""
    out, y = "", y_of(row) if y is None else y
    for m in re.finditer(r"\S+", s):
        word, style = m.group(), ""
        if delay is not None:
            style = f' style="animation-delay: {delay:.2f}s"'
            delay += step
        fit = f' textLength="{len(word) * CW:.1f}"' if len(word) > 1 else ""
        out += f'<text x="{x_of(col + m.start()):.1f}" y="{y}" class="{cls}"{fit}{style}>{html.escape(word)}</text>'
    return out + "\n"


def cursor(col, row):
    return f'<rect class="cur" x="{x_of(col):.1f}" y="{y_of(row) - 13}" width="{CW - 1}" height="16"/>'


def screen(title, rows, body, label, css=""):
    """A terminal window of this many rows of text."""
    h = BAR + 14 + rows * LH + 14
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
        f'aria-label="{html.escape(label, quote=True)}">\n<style>{STYLE}{css}</style>\n'
        f'<defs><clipPath id="window"><rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="9"/></clipPath>'
        f'<clipPath id="inside"><rect x="{PAD}" y="{BAR}" width="{W - 2 * PAD}" height="{h - BAR}"/></clipPath>'
        f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".16"/></pattern>'
        f'<filter id="glow" x="-5%" y="-40%" width="110%" height="180%"><feGaussianBlur stdDeviation="2" result="blur"/>'
        f'<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>\n'
        f'<rect class="screen" x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="9"/>\n'
        f'<g clip-path="url(#window)"><rect class="bar" width="{W}" height="{BAR}"/></g>\n'
        + "".join(f'<circle cx="{20 + 18 * i}" cy="{BAR / 2}" r="5.5" fill="{c}"/>' for i, c in enumerate(["#e66767", "#c98500", "#199e70"]))
        + f'\n<text class="dim" x="{W / 2}" y="{BAR / 2 + 5}" text-anchor="middle">{html.escape(title)}</text>\n'
        f'{body}<rect x="0" y="{BAR}" width="{W}" height="{h - BAR}" fill="url(#scan)" clip-path="url(#window)"/>\n</svg>\n'
    )


# ----------------------------------------------------------------- the banner

# Capital letters, five dots by seven.
LETTERS = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
}


def logo(name):
    """The name in letters made of "#", as big as fits in rows 1 to 6. A dot of
    a letter is "##" when the name is short enough for that, "#" when it's long."""
    chars = [c for c in name.upper() if c in LETTERS or c == " "]
    dots = sum(3 if c == " " else 6 for c in chars) - 1  # across, with one between letters
    k = 2 if 2 * dots <= COLS else 1  # characters to a dot
    pitch = 16 if k == 2 else 10  # pixels from one row of dots to the next: about what a dot is wide
    wide, tall = k * dots * CW, 6 * pitch + 11
    scale = min(COLS * CW / wide, 6 * LH / tall)
    x0, y0 = PAD + (COLS * CW - wide * scale) / 2, y_of(1) - 13 + (6 * LH - tall * scale) / 2
    out = f'<g class="logo" filter="url(#glow)" transform="translate({x0:.1f} {y0:.1f}) scale({scale:.3f})">'
    dot = n = 0
    for c in chars:
        if c == " ":
            dot += 3
            continue
        out += f'\n<g style="animation-delay: {-n:g}s">'  # each letter a step further round the colors: a wave
        for j, line in enumerate(LETTERS[c]):
            for m in re.finditer("#+", line):
                size = k * len(m.group())
                fit = f' textLength="{size * CW:.1f}"' if size > 1 else ""
                out += f'<text x="{k * (dot + m.start()) * CW:.1f}" y="{11 + j * pitch}"{fit}>{"#" * size}</text>'
        out += "</g>"
        dot, n = dot + 6, n + 1
    return out + "\n</g>\n"


def banner(name, repos):
    body = logo(name)

    rng = random.Random(1986)  # the same sky every time
    taken = set()
    for _ in range(40):
        c, r = rng.randrange(COLS), rng.choice([0, 7])
        if (c, r) not in taken:
            taken |= {(c - 1, r), (c, r), (c + 1, r)}
            body += (
                f'<text class="star h{rng.choice([0, 0, 3, 4, 6])}" x="{x_of(c):.1f}" y="{y_of(r)}" '
                f'style="animation-delay: {-rng.uniform(0, 3.2):.2f}s">{rng.choice(".+*.\'")}</text>\n'
            )

    # C:\> whoami, typed, and what it prints, a word at a time.
    row, t, command = 8, 0.9, "whoami"
    body += text(0, row, "C:\\>", "h2 b")
    for i, ch in enumerate(command):
        body += text(5 + i, row, ch, "t", t + 0.11 * i)
    typed = t + 0.11 * len(command)
    body += (
        f'<g class="typing" style="animation: off .01s linear {typed + 0.45:.2f}s forwards">'
        f'<g style="animation: type {typed - t:.2f}s steps({len(command)}) {t:.2f}s forwards">{cursor(5, row)}</g></g>\n'
    )
    t = typed + 0.55
    for i, (tag, line) in enumerate(INFO):
        row += 1
        body += text(2, row, f"[{tag}]", f"t b h{(i * 3 + 1) % 8}", t)
        t += 0.05
        for m in re.finditer(r"\S+", line):
            body += text(14 + m.start(), row, m.group(), "t dim" if m.group() == "|" else "t", t)
            t += 0.035
        t += 0.1
    row += 1
    body += f'<g class="t" style="animation-delay: {t + 0.2:.2f}s">' + text(0, row, "C:\\>", "h2 b") + cursor(5, row) + "</g>\n"

    # The repositories with the most stars, going by along the bottom.
    row += 2
    tape = " +++ ".join(f"{r['name']} *{r['stargazers_count']}" for r in repos[:10]) + " +++ "
    body += '<g clip-path="url(#inside)"><g style="animation: tape %ds linear infinite">\n' % round(len(tape) / 3.2)
    for k in range(-(-COLS // len(tape)) + 1):
        for m in re.finditer(r"\S+", tape):
            cls = "dim" if m.group() == "+++" else "h3 b" if m.group().startswith("*") else "sec"
            body += text(k * len(tape) + m.start(), row, m.group(), cls)
    body += "</g></g>\n"

    css = (
        f"@keyframes type {{ to {{ transform: translateX({len(command) * CW:.1f}px); }} }}\n"
        f"@keyframes tape {{ to {{ transform: translateX({-len(tape) * CW:.1f}px); }} }}\n"
    )
    label = f"{name}. " + ". ".join(line for _, line in INFO) + "."
    return screen(f"{USER} : README.EXE", row + 1, body, label, css)


# ------------------------------------------------------------------ the stats


def stats(name, rows, shares, slots):
    """rows: (label, number). shares: (language, fraction) from the largest, "Other" last."""
    body = text(0, 0, "C:\\>", "h2 b") + text(5, 0, "stats")
    body += text(2, 2, "-- overview --", "h0 b") + text(44, 2, "-- languages, by bytes of code --", "h0 b")
    for i, (label, value) in enumerate(rows):  # a label, dots, and its number at the right
        number = f"{value:,}"
        dots = "." * (38 - len(label) - len(number) - 2)
        body += f'<g class="fade" style="animation-delay: {0.15 * i:.2f}s">'
        body += text(2, 3 + i, label, "sec") + text(2 + len(label) + 1, 3 + i, dots, "dim")
        body += text(40 - len(number), 3 + i, number, "b") + "</g>\n"
    longest = max(share for _, share in shares)
    for i, (lang, share) in enumerate(shares):  # a bar of #, to the scale of the longest
        n = max(1, round(share / longest * 24))
        percent = f"{share:.1%}" if share >= 0.001 else "<0.1%"
        body += f'<g class="fade" style="animation-delay: {0.1 * i:.2f}s">'
        body += text(44, 3 + i, lang[:12], "sec") + text(57, 3 + i, "#" * n, slots[lang])
        body += text(57 + n, 3 + i, "." * (24 - n), "dim") + text(88 - len(percent), 3 + i, percent, "b") + "</g>\n"
    label = "; ".join(f"{label}: {value:,}" for label, value in rows) + ". Languages: " + "; ".join(f"{lang} {share:.1%}" for lang, share in shares)
    return screen(f"{name} : STATS.EXE", 3 + max(len(rows), len(shares)), body, label)


# ------------------------------------------------------------------- the data


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


def main():
    user = api(f"users/{USER}")
    repos, page = [], 1
    while True:
        batch = api(f"users/{USER}/repos?type=owner&per_page=100&page={page}")
        repos += [r for r in batch if not r["fork"]]
        if len(batch) < 100:
            break
        page += 1
    repos.sort(key=lambda r: (-r["stargazers_count"], r["name"].lower()))

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
        except Exception as e:  # the picture is still worth drawing without it
            print("no contributions:", e)

    size = {}
    for r in repos:
        for lang, n in api(f"repos/{r['full_name']}/languages").items():
            size[lang] = size.get(lang, 0) + n
    total = sum(size.values()) or 1
    ranked = sorted(size.items(), key=lambda kv: -kv[1])

    OUT.mkdir(exist_ok=True)
    memory = OUT / "languages.json"  # which color each language has, so it doesn't change from week to week
    slots = json.loads(memory.read_text()) if memory.exists() else {}
    slots = {lang: s for lang, s in slots.items() if lang in size}
    shown = []
    for lang, n in ranked:
        free = [f"s{i}" for i in range(len(MARK)) if f"s{i}" not in slots.values()]
        if len(shown) < 7 and n / total >= 0.005 and (lang in slots or free):
            slots.setdefault(lang, free[0] if free else None)
            shown.append((lang, n / total))
    slots = {lang: slots[lang] for lang, _ in shown}
    rest = 1 - sum(share for _, share in shown)
    if rest > 0.0005:
        shown.append(("Other", rest))

    memory.write_text(json.dumps(slots, indent=1) + "\n")
    (OUT / "banner.svg").write_text(banner(user.get("name") or USER, [r for r in repos if r["stargazers_count"]]), encoding="utf-8")
    (OUT / "stats.svg").write_text(stats(USER, rows, shown, {**slots, "Other": "other"}), encoding="utf-8")
    for label, value in rows:
        print(f"{value:>8,}  {label}")
    for lang, share in shown:
        print(f"{share:>8.1%}  {lang}")


if __name__ == "__main__":
    main()
