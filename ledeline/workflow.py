"""The workflow under test: source article -> spec -> model -> Blurb.

The spec file IS the prompt. Editors change specs/blurb.md; nobody edits a prompt string in
code. The evals read the same file, so a rule added to the spec without a check that enforces
it shows up as a gap in the report rather than silently doing nothing.
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "specs" / "blurb.md"


@dataclass
class Blurb:
    headline: str
    blurb: str
    claims: list[str]
    raw: str = ""

    def to_dict(self):
        return asdict(self)


def load_spec(path: Path = SPEC) -> str:
    return path.read_text()


def build_prompt(spec: str, title: str, url: str, text: str, max_chars: int = 12000) -> tuple[str, str]:
    system = ("You write newsletter blurbs. Follow the spec exactly. The spec is the whole contract; "
              "when in doubt, leave a fact out rather than guess.\n\n" + spec)
    user = f"SOURCE TITLE: {title}\nSOURCE URL: {url}\n\nSOURCE TEXT:\n{text[:max_chars]}\n\nReturn the JSON now."
    return system, user


def parse(text: str) -> Blurb:
    """Tolerate a fenced code block or leading prose; refuse anything that is not one object."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    obj = json.loads(m.group(0))
    claims = obj.get("claims") or []
    if isinstance(claims, str):
        claims = [claims]
    return Blurb(str(obj.get("headline", "")).strip(), str(obj.get("blurb", "")).strip(),
                 [str(c).strip() for c in claims], raw=text)


def run(provider, title: str, url: str, text: str, spec: str | None = None) -> tuple[Blurb, object]:
    system, user = build_prompt(spec or load_spec(), title, url, text)
    comp = provider.complete(system, user, json_mode=True)
    return parse(comp.text), comp
