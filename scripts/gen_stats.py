"""Generate languages.svg from the real byte counts of my public repositories.

Why this exists rather than one of the off-the-shelf top-languages cards:

  * Those cards render whatever GitHub Linguist reports, and Linguist counts
    vendored and generated files as code. Unfiltered, the top language on this
    account is **Roff** at 36% - man page markup, from one 2022 repo that
    carries a few megabytes of generated content. That is not a useful fact
    about anyone.
  * They also count CSS, HTML and Makefiles as "languages", which inflates
    whichever framework you happened to scaffold with.

So: markup and config are excluded, and EXCLUDE_REPOS drops repositories whose
byte counts are dominated by generated or vendored content. Everything else is
the honest total, in bytes, straight from the API.

Run: python scripts/gen_stats.py   (GITHUB_TOKEN optional but avoids rate limits)
"""
import json, os, urllib.request

USER = "Shiroko7"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "languages.svg")

# Dominated by generated/vendored content; including it makes Roff the headline.
EXCLUDE_REPOS = {"evotoon"}

# Markup, styling and build config. Real files, but not what the chart is about.
EXCLUDE_LANGS = {"Roff", "HTML", "CSS", "SCSS", "Makefile", "Shell", "Batchfile",
                 "Dockerfile", "mdsvex", "TeX", "Vim Script"}

# A violet-to-fuchsia ramp, so it sits beside the d20 instead of fighting it.
RAMP = ["#8b5cf6", "#a78bfa", "#c084fc", "#e879f9", "#f0abfc", "#f5d0fe"]

W, BAR_H, R = 480, 10, 5

# The chart is a statement about tools, so the caption gets to answer it.
# One string per rendered line.
#
# NOTE: ("x") is a string, not a tuple - a 1-line quip needs the trailing
# comma, or the renderer below iterates it character by character and emits one
# <text> element per letter. _quip_lines() normalises either form so editing
# this by hand cannot produce 42 stacked letters.
QUIP = ("I don't actually like TypeScript that much",)


def _quip_lines():
    """Accept a bare string or any iterable of strings."""
    return (QUIP,) if isinstance(QUIP, str) else tuple(QUIP)


def api(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    return json.load(urllib.request.urlopen(req))


def collect():
    repos = api(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    totals = {}
    for r in repos:
        if r["fork"] or r["private"] or r["name"] in EXCLUDE_REPOS:
            continue
        for lang, n in api(r["languages_url"]).items():
            if lang in EXCLUDE_LANGS:
                continue
            totals[lang] = totals.get(lang, 0) + n
    return totals


def build(totals):
    total = sum(totals.values())
    rows = sorted(totals.items(), key=lambda kv: -kv[1])

    # Anything under 1% joins "other" so the legend stays readable.
    major = [(k, v) for k, v in rows if v / total >= 0.01]
    rest = sum(v for k, v in rows if v / total < 0.01)
    if rest:
        major.append(("Other", rest))

    segs, x = [], 0.0
    for i, (name, n) in enumerate(major):
        w = W * n / total
        segs.append((name, 100 * n / total, x, w, RAMP[i % len(RAMP)]))
        x += w

    legend_rows = (len(segs) + 2) // 3
    quip = _quip_lines()
    qy = 30 + legend_rows * 19 + 14
    cap_y = qy + len(quip) * 16 + 8
    H = cap_y + 6

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-label="Language split across my public repositories">',
        "<title>Languages</title>",
        "<style>"
        ".lbl{font:500 11px ui-sans-serif,-apple-system,'Segoe UI',Roboto,sans-serif;fill:#8b5cf6}"
        ".pct{font:400 11px ui-sans-serif,-apple-system,'Segoe UI',Roboto,sans-serif;fill:#a78bfa}"
        ".quip{font:italic 400 11.5px ui-serif,Georgia,'Times New Roman',serif;fill:#a78bfa;opacity:.92}"
        ".cap{font:400 9.5px ui-sans-serif,-apple-system,'Segoe UI',Roboto,sans-serif;fill:#a78bfa;opacity:.6}"
        f".seg{{animation:grow 1.1s cubic-bezier(.22,1,.36,1) both}}"
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        "@media (prefers-reduced-motion:reduce){.seg{animation:none}}"
        "</style>",
        # rounded window so the segments read as one bar
        f'<clipPath id="r"><rect x="0" y="0" width="{W}" height="{BAR_H}" rx="{R}"/></clipPath>',
        '<g clip-path="url(#r)">',
    ]
    for i, (name, pct, sx, sw, col) in enumerate(segs):
        parts.append(
            f'<rect class="seg" x="{sx:.2f}" y="0" width="{sw:.2f}" height="{BAR_H}" fill="{col}" '
            f'style="transform-box:fill-box;transform-origin:left;animation-delay:{i*90}ms"/>'
        )
    parts.append("</g>")

    # legend: two rows of up to three, left aligned
    for i, (name, pct, *_rest) in enumerate(segs):
        col = RAMP[i % len(RAMP)]
        cx = (i % 3) * 160 + 5
        cy = 30 + (i // 3) * 19
        parts.append(f'<circle cx="{cx}" cy="{cy-3.5}" r="3.5" fill="{col}"/>')
        parts.append(f'<text class="lbl" x="{cx+11}" y="{cy}">{name}</text>')
        parts.append(f'<text class="pct" x="{cx+11+len(name)*6.3+6}" y="{cy}">{pct:.1f}%</text>')

    mb = total / 1048576
    for i, line in enumerate(quip):
        parts.append(f'<text class="quip" x="0" y="{qy + i*16}">{line}</text>')
    parts.append(
        f'<text class="cap" x="0" y="{cap_y}">by bytes across {len(rows)} languages · '
        f'{mb:.1f} MB · vendored and markup excluded</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    t = collect()
    svg = build(t)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg + "\n")
    s = sum(t.values())
    for k, v in sorted(t.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<14} {100*v/s:5.1f}%")
    print(f"\nwrote {OUT}")
