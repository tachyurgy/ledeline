"""Deterministic checks. Each one maps to a numbered rule in specs/blurb.md and returns a
Finding with the rule id, so the report can show which rules a model breaks, not just a score.

The grounding check (rule 1) is the one that matters. A blurb is only allowed to contain
numbers, years, money, percentages and capitalised names that appear in the source text. It is
a proxy, not a proof: it cannot catch a wrong verb between two real names. But it catches the
failure that actually costs a newsletter its credibility, which is a number or a company that
was never in the article, and it costs zero tokens.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

HYPE = ["game-changer", "game changer", "revolutionary", "groundbreaking", "cutting-edge", "cutting edge",
        "seamless", "unlock", "supercharge", "next-level", "next level", "disrupt", "incredible",
        "must-read", "must read", "excited", "thrilled"]
FIRST_PERSON = re.compile(r"\b(we|i|our|you should|you'll|you will)\b", re.I)
META = re.compile(r"\b(this (post|article|piece|blog)|the (post|article|author) (explains|describes|walks|discusses))\b", re.I)
NUM = re.compile(r"(?<![\w.])(\$?\d[\d,]*(?:\.\d+)?%?[kKmMbB]?)(?![\w.])")
CAPS = re.compile(r"\b([A-Z][A-Za-z0-9+.#-]{2,}(?:\s+[A-Z][A-Za-z0-9+.#-]{2,})*)\b")
STOP = {"The", "This", "That", "These", "Those", "A", "An", "In", "On", "At", "For", "With", "And", "But", "Or",
        "It", "Its", "As", "By", "From", "To", "Of", "If", "When", "While", "After", "Before", "Some", "Most",
        "Many", "New", "Now", "Here", "There", "They", "Their", "He", "She", "His", "Her", "We", "Our", "You",
        "Why", "How", "What", "Which", "Who", "Instead", "Because", "Unlike", "Like", "Both", "Each", "Every",
        "Still", "Yet", "So", "Then", "Also", "Meanwhile", "However", "Since", "Until", "Over", "Under"}


@dataclass
class Finding:
    rule: str
    ok: bool
    detail: str = ""


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(f.ok for f in self.findings)

    @property
    def failed_rules(self) -> list[str]:
        return [f.rule for f in self.findings if not f.ok]

    def to_dict(self):
        return {"passed": self.passed, "findings": [f.__dict__ for f in self.findings]}


def _norm(s: str) -> str:
    return re.sub(r"[\s,]+", "", s.lower())


def word_count(s: str) -> int:
    return len(re.findall(r"\b\w[\w'-]*\b", s))


def sentence_count(s: str) -> int:
    return len([x for x in re.split(r"(?<=[.!?])\s+", s.strip()) if x])


def ungrounded_numbers(blurb: str, source: str) -> list[str]:
    src = _norm(source)
    out = []
    for n in NUM.findall(blurb):
        key = _norm(n).lstrip("$").rstrip("%kmb")
        if key and key not in src:
            out.append(n)
    return out


def ungrounded_names(blurb: str, source: str, headline: str = "") -> list[str]:
    """Capitalised runs in the blurb that never appear in the source (case-insensitive,
    whitespace-insensitive). Sentence-initial stopwords are ignored. A multi-word run is
    accepted if the whole run appears OR every word of it appears somewhere in the source."""
    src = _norm(source)
    text = blurb + " " + headline
    # single capitalised words that open a sentence are capitalised by grammar, not by being
    # a name ("Teams get faster responses"); multi-word runs at a sentence start still count.
    sentence_initial = set()
    for m in re.finditer(r"(?:^|[.!?]\s+)([A-Z][A-Za-z0-9+.#-]{2,})(?!\s+[A-Z])", text):
        sentence_initial.add((m.start(1), m.group(1)))
    out = []
    for m in CAPS.finditer(text):
        run = m.group(1)
        if (m.start(1), run) in sentence_initial:
            continue
        words = [w for w in run.split() if w not in STOP]
        if not words:
            continue
        run2 = " ".join(words)
        if _norm(run2) in src or all(_norm(w) in src for w in words):
            continue
        out.append(run2)
    return sorted(set(out))


def check(headline: str, blurb: str, claims: list[str], source: str) -> CheckResult:
    r = CheckResult()
    hw = word_count(headline)
    r.findings.append(Finding("headline.length", 0 < hw <= 12, f"{hw} words"))
    r.findings.append(Finding("headline.no_trailing_period", not headline.rstrip().endswith("."), headline[-1:] if headline else ""))
    wc = word_count(blurb); sc = sentence_count(blurb)
    r.findings.append(Finding("blurb.words", 45 <= wc <= 90, f"{wc} words"))
    r.findings.append(Finding("blurb.sentences", 2 <= sc <= 4, f"{sc} sentences"))
    r.findings.append(Finding("claims.count", 2 <= len(claims) <= 5, f"{len(claims)} claims"))
    hype = [h for h in HYPE if re.search(r"\b" + re.escape(h) + r"\b", (blurb + " " + headline).lower())]
    r.findings.append(Finding("rule2.no_hype", not hype, ", ".join(hype)))
    fp = FIRST_PERSON.findall(blurb)
    r.findings.append(Finding("rule3.third_person", not fp, ", ".join(sorted(set(x.lower() for x in fp)))))
    r.findings.append(Finding("rule4.no_meta", not META.search(blurb), (META.search(blurb) or [""])[0] if META.search(blurb) else ""))
    bad = ("http://" in blurb or "https://" in blurb or "!" in blurb or re.search(r"[\U0001F300-\U0001FAFF☀-➿]", blurb) is not None)
    r.findings.append(Finding("rule5.no_urls_emoji_bang", not bad))
    un = ungrounded_numbers(blurb, source)
    r.findings.append(Finding("rule1.numbers_grounded", not un, ", ".join(un)))
    nn = ungrounded_names(blurb, source, headline)
    r.findings.append(Finding("rule1.names_grounded", not nn, ", ".join(nn)))
    return r
