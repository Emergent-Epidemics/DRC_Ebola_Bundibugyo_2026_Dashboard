"""Static guards for the harmonised zone-state styling tokens.

The brand theme layer (Data/Branding/dashboard-theme.css) is optional --
build_dashboard.py appends it only when non-empty -- so engine.js must carry
every token's value as its themeVar() fallback. A fallback that drifts from the
CSS produces a dashboard that renders differently with and without branding,
silently. These tests make that drift a build failure.

See docs/superpowers/specs/2026-08-14-map-zone-state-styling-design.md.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "Scripts" / "assets" / "engine.js"
THEME = REPO / "Data" / "Branding" / "dashboard-theme.css"

# themeVar("--token", "fallback") / zoneNum("--token", "fallback") -- both are
# token readers; zoneNum() is the numeric wrapper around themeVar(). Either
# quote style, since nothing in this repo enforces one. Groups: 1 and 3 are the
# quote characters (needed for the backreferences), so the token is group 2 and
# the fallback is group 4. A match's .start()/.end() still span the whole call.
THEMEVAR = re.compile(
    r"""(?:themeVar|zoneNum)\(\s*(["'])(--[a-z0-9-]+)\1\s*,\s*(["'])([^"']*)\3\s*\)"""
)
# --token: value;
CSS_DECL = re.compile(r'(--[a-z0-9-]+)\s*:\s*([^;]+);')

# Only the families this spec owns. Other theme tokens are consumed by CSS
# rules rather than by themeVar(), so they are out of scope here.
OWNED_PREFIXES = ("--zone-", "--province-")


def _engine_source():
    return ENGINE.read_text(encoding="utf-8")


def _css_tokens():
    text = THEME.read_text(encoding="utf-8")
    # A commented-out declaration must not look like a live one: last-match-wins
    # would otherwise let a stale "/* was --x: 1.5; */" shadow the real value, or
    # make a deleted token look defined -- a silent false pass in exactly the
    # drift these tests exist to catch.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return {m.group(1): m.group(2).strip() for m in CSS_DECL.finditer(text)}


def _owned_css_tokens():
    return {k: v for k, v in _css_tokens().items() if k.startswith(OWNED_PREFIXES)}


def _fallbacks():
    """token -> set of distinct fallback strings used in engine.js."""
    out = {}
    for m in THEMEVAR.finditer(_engine_source()):
        # Groups 1 and 3 are the quote characters; see THEMEVAR above.
        out.setdefault(m.group(2), set()).add(m.group(4).strip())
    return out


def _equivalent(a, b):
    """Compare as numbers when both parse as numbers, else case-insensitively.

    Lets the CSS say `0.1` where the JS fallback says `0.10` without a spurious
    failure, while still catching a genuine value change.
    """
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return a.strip().lower() == b.strip().lower()


def test_every_owned_css_token_is_read_by_engine():
    missing = sorted(set(_owned_css_tokens()) - set(_fallbacks()))
    assert not missing, f"tokens defined in the theme but never read by engine.js: {missing}"


def test_every_token_engine_reads_exists_in_css():
    css = _css_tokens()
    referenced = {t for t in _fallbacks() if t.startswith(OWNED_PREFIXES)}
    missing = sorted(referenced - set(css))
    assert not missing, f"engine.js reads tokens that the theme does not define: {missing}"


def test_fallbacks_match_the_css_values():
    css = _owned_css_tokens()
    problems = []
    for token, fallbacks in sorted(_fallbacks().items()):
        if token not in css:
            continue
        if len(fallbacks) > 1:
            problems.append(f"{token}: engine.js uses inconsistent fallbacks {sorted(fallbacks)}")
            continue
        (fallback,) = tuple(fallbacks)
        if not _equivalent(fallback, css[token]):
            problems.append(f"{token}: fallback {fallback!r} != css {css[token]!r}")
    assert not problems, "theme/fallback drift:\n" + "\n".join(problems)


def test_ramp_produces_the_documented_weights():
    """The ramp is the one number the whole visual system hangs off.

    A slope edit that silently changes the national view is exactly the kind of
    regression nobody notices in a local z9 screenshot.
    """
    css = _css_tokens()
    base = float(css["--zone-stroke-weight-base"])
    lo = float(css["--zone-stroke-ramp-min"])
    hi = float(css["--zone-stroke-ramp-max"])
    slope = float(css["--zone-stroke-ramp-slope"])

    def weight(zoom):
        return base * max(lo, min(hi, lo + (zoom - 5) * slope))

    assert round(weight(5), 2) == 1.02, "national z5 resting weight changed"
    assert round(weight(8), 2) == 1.53, "default-view z8 resting weight changed"
    assert round(weight(9), 2) == 1.70, "z9 resting weight changed"
    assert round(weight(12), 3) == 1.955, "ramp ceiling changed"
    assert weight(3) == weight(5), "ramp must not keep thinning below z5"
