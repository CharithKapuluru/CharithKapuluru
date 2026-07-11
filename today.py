#!/usr/bin/env python3
"""
today.py — generates dark_mode.svg and light_mode.svg for the GitHub profile
README. Fetches live account statistics (repos, stars, followers, commits,
lines of code) from the GitHub GraphQL/REST API and renders a neofetch-style
terminal card with an ASCII self-portrait.

Run locally:   ACCESS_TOKEN=<pat> USER_NAME=charithkapuluru python3 today.py
On CI:          provided by .github/workflows/main.yml
"""

import os
import re
import sys
import json
import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import requests

# ---------------------------------------------------------------------------
# 1. PERSONAL CONFIG  —  edit these freely, they are the text on the right panel
# ---------------------------------------------------------------------------
BIRTHDAY = datetime.date(2002, 1, 30)          # drives the live "Uptime" line

INFO = {
    "header": "charith@kapuluru",
    "os":      "macOS Sequoia, Ubuntu, Windows 11",
    "host":    "CBRE - Digital & Technology (Incoming)",
    "kernel":  "Cloud & DevSecOps / GenAI Engineer",
    "ide":     "VS Code, Claude Code, PyCharm",

    "lang_prog":     "Python, Java, JavaScript, Bash",
    "lang_computer": "HTML, CSS, JSON, YAML, HCL, LaTeX",
    "lang_real":     "English, Telugu, Hindi",

    "hobby_software": "LLM tinkering, Homelab, Self-hosting",
    "hobby_fitness":  "Powerlifting, Bulking, Nutrition",

    "email":    "kapulurucharith@gmail.com",
    "website":  "charithkapuluru.com",
    "linkedin": "charith-kapuluru-159456329",
    "github":   "charithkapuluru",
}

# ASCII self-portrait (generated from your photo, background removed).
ASCII_ART = r"""
                     .`"``.'
               "!lrmp$B$8B$&kqj!,^^.
            . lg88#%@@@@@@@@@@W$*wtI.
           'jwW@@@@@@@@@@@@@@@@%##gj^"".
           .p@@@@@@@@@@@@@@@@@@%%@#&kqqj^
        `Irk@@@@@@@@@@@@@@@@@@@@@@@@@8hI".
      ."rB%@@@@@@@@@@@@@@@@@@@@@@@@@@%&t.
      'p%@@@@@@@@@@@@@@@@@@@%WB*$#@@@@Mw'  .
       'B@@@@@@@@@@@@@@@@%W$hj,.`d@@@@@*t;l`
       '*#@@@@@@@@@@@@@@M$$kml  .IB@@#M#hl^
       .r@@@@@@@@@@@@@@@@%WMBgdm!ld@@@@B:
        l%@@@@@@@@@@@@@@@@g8@@@#Bwj@@8*;
        .i#@@@@%%@@@@@@@@%jlg#Mmjlt#m`
         .d@@@@#MW#%@@@@@%p ':i;. ld.
         :W@@@@@W#%@@@@@@%8w!IBq,';"
         ;W@@@@@@@@@@@@@@%%%gd#Wdir.
          ;B@%@@@@@@@@@%Bkdwm$W*qh,
           ,M@@@@@@@@@@@@#Wpliqh&!
         ^tl*@@@@@@@@@@@@@Wdrrkh;
       ^jWMtid#@@@@@@@@@@@@W$m;.
    `;pW@@@gjtjg%@@@@%%%%$ptq^
':jgW@@@@@@@$wrtw*8MM88Bgr:i8!;pr;`.
M@@@@@@@@@@@@gwrrtItqhgkm!t#Br"w##8$hr,'
@@@@@@@@@@@@@%*jrtr!"lqprj#%pt:I&8W###M$drl"'
@@@@@@@@@@@@@@#dtttt!`lpk8pii!;B@BBMWMWWMMB&kr.
@@@@@@@@@@@@@@@WwiII!;"jB, `":'j@#$BWMMMMMB&&Mq.
""".strip("\n").split("\n")

# ---------------------------------------------------------------------------
# 2. GITHUB API
# ---------------------------------------------------------------------------
USER  = os.environ.get("USER_NAME", INFO["github"])
TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
API   = "https://api.github.com/graphql"
HEAD  = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}

CACHE = Path("cache")
CACHE.mkdir(exist_ok=True)


def gql(query, variables):
    r = requests.post(API, json={"query": query, "variables": variables},
                      headers=HEAD, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def account_created_year():
    q = "query($login:String!){user(login:$login){createdAt}}"
    d = gql(q, {"login": USER})
    return int(d["user"]["createdAt"][:4])


def basic_stats():
    """repos owned, followers, and total stars across owned repos."""
    q = """query($login:String!,$after:String){
      user(login:$login){
        followers{totalCount}
        repositories(first:100,ownerAffiliations:OWNER,after:$after){
          totalCount
          pageInfo{hasNextPage endCursor}
          nodes{ stargazerCount nameWithOwner defaultBranchRef{name} }
        }
      }}"""
    followers = stars = repos = 0
    all_repos = []
    after = None
    while True:
        d = gql(q, {"login": USER, "after": after})["user"]
        followers = d["followers"]["totalCount"]
        repos = d["repositories"]["totalCount"]
        for n in d["repositories"]["nodes"]:
            stars += n["stargazerCount"]
            all_repos.append(n)
        if d["repositories"]["pageInfo"]["hasNextPage"]:
            after = d["repositories"]["pageInfo"]["endCursor"]
        else:
            break
    return followers, stars, repos, all_repos


def total_commits(start_year):
    """Sum commit contributions across every year since the account was made."""
    q = """query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from,to:$to){ totalCommitContributions }
      }}"""
    total = 0
    this_year = datetime.date.today().year
    for yr in range(start_year, this_year + 1):
        frm = f"{yr}-01-01T00:00:00Z"
        to  = f"{yr}-12-31T23:59:59Z"
        d = gql(q, {"login": USER, "from": frm, "to": to})
        total += d["user"]["contributionsCollection"]["totalCommitContributions"]
    return total


def lines_of_code(repos):
    """Best-effort additions/deletions authored by USER, cached per repo."""
    cache_file = CACHE / "loc.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    added = deleted = 0

    q = """query($owner:String!,$name:String!,$branch:String!,$id:ID!,$after:String){
      repository(owner:$owner,name:$name){
        ref(qualifiedName:$branch){ target{ ... on Commit{
          history(first:100,author:{id:$id},after:$after){
            totalCount pageInfo{hasNextPage endCursor}
            nodes{ additions deletions }
          }}}}}}"""

    # get the viewer/user node id once
    uid = gql("query($login:String!){user(login:$login){id}}",
              {"login": USER})["user"]["id"]

    for repo in repos:
        name = repo["nameWithOwner"]
        if not repo.get("defaultBranchRef"):
            continue
        branch = "refs/heads/" + repo["defaultBranchRef"]["name"]
        owner, rname = name.split("/", 1)
        a = d = 0
        after = None
        try:
            while True:
                res = gql(q, {"owner": owner, "name": rname,
                              "branch": branch, "id": uid, "after": after})
                hist = res["repository"]["ref"]["target"]["history"]
                for c in hist["nodes"]:
                    a += c["additions"]
                    d += c["deletions"]
                if hist["pageInfo"]["hasNextPage"]:
                    after = hist["pageInfo"]["endCursor"]
                else:
                    break
            cache[name] = {"a": a, "d": d}
        except Exception:
            # keep any previously cached value on transient failure
            if name in cache:
                a, d = cache[name]["a"], cache[name]["d"]
        added += a
        deleted += d

    cache_file.write_text(json.dumps(cache, indent=2))
    return added, deleted


def uptime():
    today = datetime.date.today()
    y = today.year - BIRTHDAY.year
    anniv = BIRTHDAY.replace(year=today.year)
    if today < anniv:
        y -= 1
        anniv = BIRTHDAY.replace(year=today.year - 1)
    days = (today - anniv).days
    return f"{y} years, {days} days"


# ---------------------------------------------------------------------------
# 3. SVG BUILDER
# ---------------------------------------------------------------------------
THEMES = {
    "dark":  dict(bg="#0d1117", border="#30363d",
                  ascii1="#d2a8ff", ascii2="#79c0ff", text="#c9d1d9",
                  key="#ffa657", sect="#79c0ff", dim="#484f58",
                  add="#3fb950", rem="#f85149", name="#7ee787",
                  host="#a5d6ff", cursor="#7ee787"),
    "light": dict(bg="#ffffff", border="#d0d7de",
                  ascii1="#8250df", ascii2="#0969da", text="#1f2328",
                  key="#bc4c00", sect="#0969da", dim="#afb8c1",
                  add="#1a7f37", rem="#cf222e", name="#116329",
                  host="#0550ae", cursor="#1a7f37"),
}

FS = 13.0                 # panel font size (px)
CW = FS * 0.6             # monospace char width
AFS = 10.0                # ascii font size
ALINE = AFS * 1.30        # ascii line height
PLINE = FS * 1.55         # panel line height
LINE_CHARS = 56           # panel width in characters (key + dots + value)


def dot_line(key, val):
    """key .......... value  padded to LINE_CHARS with dot leaders."""
    room = LINE_CHARS - len(key) - len(val) - 2
    room = max(room, 1)
    return key, "." * room, val


def build_svg(theme, stats):
    c = THEMES[theme]
    followers, stars, repos, commits, loc_add, loc_del = stats
    loc_total = loc_add - loc_del

    # ---- assemble the panel rows first so we can size the card exactly ----
    rows = []
    rows.append(("raw", f'<tspan fill="{c["name"]}">{INFO["header"].split("@")[0]}</tspan>'
                        f'<tspan fill="{c["text"]}">@</tspan>'
                        f'<tspan fill="{c["host"]}">{INFO["header"].split("@")[1]}</tspan>'
                        f'<tspan fill="{c["dim"]}"> {"-"*(LINE_CHARS-len(INFO["header"])-1)}</tspan>'))
    rows.append(("kv", "OS:", INFO["os"]))
    rows.append(("kv", "Uptime:", uptime()))
    rows.append(("kv", "Host:", INFO["host"]))
    rows.append(("kv", "Kernel:", INFO["kernel"]))
    rows.append(("kv", "IDE:", INFO["ide"]))
    rows.append(("gap",))
    rows.append(("kv", "Languages.Programming:", INFO["lang_prog"]))
    rows.append(("kv", "Languages.Computer:", INFO["lang_computer"]))
    rows.append(("kv", "Languages.Real:", INFO["lang_real"]))
    rows.append(("gap",))
    rows.append(("kv", "Hobbies.Software:", INFO["hobby_software"]))
    rows.append(("kv", "Hobbies.Fitness:", INFO["hobby_fitness"]))
    rows.append(("gap",))
    rows.append(("sect", "Contact"))
    rows.append(("kv", "Email:", INFO["email"]))
    rows.append(("kv", "Website:", INFO["website"]))
    rows.append(("kv", "LinkedIn:", INFO["linkedin"]))
    rows.append(("kv", "GitHub:", INFO["github"]))
    rows.append(("gap",))
    rows.append(("sect", "GitHub Stats"))
    rows.append(("kv", "Repos:", f"{repos:,}"))
    rows.append(("kv", "Stars:", f"{stars:,}"))
    rows.append(("kv", "Followers:", f"{followers:,}"))
    rows.append(("kv", "Commits:", f"{commits:,}"))
    rows.append(("loc", "Lines of Code:", loc_total, loc_add, loc_del))
    rows.append(("gap",))
    rows.append(("prompt",))            # final blinking-cursor prompt line

    n_panel = len(rows)
    panel_h = n_panel * PLINE
    ascii_h = len(ASCII_ART) * ALINE

    pad_x, pad_top, pad_bot = 22, 30, 26
    ax = 20                              # ascii left origin
    px = 372                             # panel left origin
    content_h = max(ascii_h, panel_h)
    H = int(content_h + pad_top + pad_bot)
    W = 900

    # vertically center each column against the taller one
    ay = pad_top + (content_h - ascii_h) / 2
    py = pad_top + (content_h - panel_h) / 2

    # ---- animation timings ----
    a_step = 0.035                       # delay between ascii lines
    a_dur  = 0.30
    p_start = len(ASCII_ART) * a_step * 0.5 + 0.15
    p_step = 0.085
    p_dur  = 0.32
    total_intro = p_start + n_panel * p_step

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" '
        f'font-family="\'JetBrains Mono\',\'Cascadia Code\',\'Courier New\',monospace">')

    out.append(f"""<defs>
    <linearGradient id="ag_{theme}" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="{c['ascii1']}"/>
      <stop offset="1" stop-color="{c['ascii2']}"/>
    </linearGradient>
    </defs>""")

    out.append(f"""<style>
    text {{ white-space: pre; dominant-baseline: middle; }}
    .ln {{ clip-path: inset(0 0 0 0); }}                 /* safe visible default */
    .w  {{ animation: wipe var(--d,.32s) linear both; }}
    @keyframes wipe {{ from {{ clip-path: inset(0 100% 0 0); }}
                       to   {{ clip-path: inset(0 0 0 0); }} }}
    .cur {{ animation: blink 1.05s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    </style>""")

    # card
    out.append(f'<rect x="4" y="4" width="{W-8}" height="{H-8}" rx="14" '
               f'fill="{c["bg"]}" stroke="{c["border"]}" stroke-width="1.5"/>')

    def wipe(delay, dur):
        return f'class="ln w" style="--d:{dur}s;animation-delay:{delay:.2f}s"'

    # ---- ASCII art (left, gradient fill, cascade wipe) ----
    for i, row in enumerate(ASCII_ART):
        y = ay + i * ALINE + ALINE / 2
        out.append(f'<text x="{ax}" y="{y:.1f}" font-size="{AFS}" '
                   f'fill="url(#ag_{theme})" {wipe(i*a_step, a_dur)}>{escape(row)}</text>')

    # ---- info panel (right, typed line by line) ----
    j = 0
    for row in rows:
        y = py + j * PLINE + PLINE / 2
        d = p_start + j * p_step
        kind = row[0]
        if kind == "gap":
            j += 1
            continue
        if kind == "raw":
            out.append(f'<text x="{px}" y="{y:.1f}" font-size="{FS}" {wipe(d,p_dur)}>{row[1]}</text>')
        elif kind == "sect":
            title = row[1]
            dashes = "-" * (LINE_CHARS - len(title) - 3)
            out.append(f'<text x="{px}" y="{y:.1f}" font-size="{FS}" {wipe(d,p_dur)}>'
                       f'<tspan fill="{c["sect"]}">- {title} -</tspan>'
                       f'<tspan fill="{c["dim"]}">{dashes}</tspan></text>')
        elif kind == "kv":
            key, dots, val = dot_line(row[1], str(row[2]))
            out.append(f'<text x="{px}" y="{y:.1f}" font-size="{FS}" {wipe(d,p_dur)}>'
                       f'<tspan fill="{c["key"]}">{escape(key)}</tspan>'
                       f'<tspan fill="{c["dim"]}"> {dots} </tspan>'
                       f'<tspan fill="{c["text"]}">{escape(val)}</tspan></text>')
        elif kind == "loc":
            key, total, a, dd = row[1], row[2], row[3], row[4]
            valstr = f"{total:,}"
            extra = f" ( {a:,}++,  {dd:,}-- )"
            key_p, dots, _ = dot_line(key, valstr + extra)
            out.append(f'<text x="{px}" y="{y:.1f}" font-size="{FS}" {wipe(d,p_dur)}>'
                       f'<tspan fill="{c["key"]}">{escape(key_p)}</tspan>'
                       f'<tspan fill="{c["dim"]}"> {dots} </tspan>'
                       f'<tspan fill="{c["text"]}">{valstr}</tspan>'
                       f'<tspan fill="{c["text"]}"> ( </tspan>'
                       f'<tspan fill="{c["add"]}">{a:,}++</tspan>'
                       f'<tspan fill="{c["text"]}">,  </tspan>'
                       f'<tspan fill="{c["rem"]}">{dd:,}--</tspan>'
                       f'<tspan fill="{c["text"]}"> )</tspan></text>')
        elif kind == "prompt":
            user, host = INFO["header"].split("@")
            prompttxt = f'{user}@{host}:~$ '
            out.append(f'<text x="{px}" y="{y:.1f}" font-size="{FS}" {wipe(d,p_dur)}>'
                       f'<tspan fill="{c["name"]}">{escape(user)}</tspan>'
                       f'<tspan fill="{c["text"]}">@</tspan>'
                       f'<tspan fill="{c["host"]}">{escape(host)}</tspan>'
                       f'<tspan fill="{c["text"]}">:~$ </tspan></text>')
            cx = px + len(prompttxt) * CW
            out.append(f'<rect class="cur" x="{cx:.1f}" y="{y-FS*0.55:.1f}" '
                       f'width="{CW*0.9:.1f}" height="{FS:.1f}" fill="{c["cursor"]}" '
                       f'style="animation-delay:{total_intro:.2f}s"/>')
        j += 1

    out.append("</svg>")
    return "\n".join(out)


# 4. MAIN
# ---------------------------------------------------------------------------
def gather_stats():
    if not TOKEN:
        print("No ACCESS_TOKEN set -> using placeholder stats (preview only).")
        return (0, 0, 0, 0, 0, 0)
    start = account_created_year()
    followers, stars, repos, all_repos = basic_stats()
    commits = total_commits(start)
    add, dele = lines_of_code(all_repos)
    return (followers, stars, repos, commits, add, dele)


def main():
    stats = gather_stats()
    for theme in ("dark", "light"):
        Path(f"{theme}_mode.svg").write_text(build_svg(theme, stats))
        print(f"wrote {theme}_mode.svg")


if __name__ == "__main__":
    main()
