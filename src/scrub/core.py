"""Find personal details in text and replace them with labels such as [EMAIL] and [PHONE].

Two rules shape everything here:

1. A number is only called a card, an ID or an IBAN when its check digit is right. A sixteen-digit
   order number is not a card, and treating it as one would destroy data for no reason.
2. Text is never rewritten except where something was found. The rest comes back character for
   character.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

KINDS = ("email", "card", "emirates_id", "iban", "phone", "ip", "name")

# Digits written in Arabic-Indic or Persian script are read as 0-9. The swap is one character
# for one character, so positions found in the cleaned text are valid in the original.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


@dataclass(frozen=True)
class Finding:
    kind: str
    start: int
    end: int
    text: str


@dataclass
class Result:
    text: str
    findings: list[Finding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for finding in self.findings:
            totals[finding.kind] = totals.get(finding.kind, 0) + 1
        return totals


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def luhn_ok(number: str) -> bool:
    """The check used by payment cards and by Emirates IDs."""
    digits = [int(d) for d in _digits(number)]
    if len(digits) < 2:
        return False
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def iban_ok(value: str) -> bool:
    """The international check for bank account numbers: move four characters, then mod 97."""
    compact = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        return False
    moved = compact[4:] + compact[:4]
    as_number = "".join(str(int(ch, 36)) for ch in moved)
    return int(as_number) % 97 == 1


def _ip_ok(value: str) -> bool:
    return all(part.isdigit() and int(part) <= 255 and (part == "0" or not part.startswith("0")) for part in value.split("."))


# Every part has a length limit and the match cannot start in the middle of a longer run, so a
# hostile input such as a megabyte of "a" cannot make the search slow.
_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}")
_IBAN = re.compile(r"\b[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{4}){2,7}(?: ?[A-Za-z0-9]{1,4})?\b")
_EMIRATES_ID = re.compile(r"(?<!\d)784[- ]?\d{4}[- ]?\d{7}[- ]?\d(?!\d)")
_CARD = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
_IP = re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])")
# A phone number starts with + and a country code, or with 00, or with a single 0 (a local number).
_PHONE = re.compile(r"(?<![\w+])(?:\+|00)[1-9]\d{0,2}[ -]?(?:\(?\d{1,4}\)?[ -]?){2,5}\d(?!\d)|(?<![\w.,])0\d{1,2}[ -]?\d{3}[ -]?\d{4}(?!\d)")
# A name is only taken when the sentence says it is one. Guessing names from capital letters
# alone removes product names, cities and the first word of every sentence.
_NAME = re.compile(
    r"(?:\b(?:[Mm]y name is|[Mm]y name's|[Ii] am|[Ii]'m|[Tt]his is|[Cc]all me|[Nn]ame:)\s+|\b(?:Mr|Mrs|Ms|Miss|Dr|Eng|Prof)\.?\s+)"
    r"([A-Z][a-z]+(?:[ -][A-Z][a-z]+){0,2})"
)
# Words that follow "I'm" or "this is" far more often than a name does.
_NOT_NAMES = {"Sorry", "Looking", "Here", "Fine", "Good", "Not", "Just", "Going", "Calling", "Interested", "Sure", "Happy", "The", "A", "An", "My", "Your", "Our", "It", "That", "This"}


def _find(kind: str, text: str) -> list[Finding]:
    found: list[Finding] = []

    def add(match: re.Match[str], group: int = 0) -> None:
        found.append(Finding(kind, match.start(group), match.end(group), match.group(group)))

    if kind == "email":
        for match in _EMAIL.finditer(text):
            add(match)
    elif kind == "iban":
        for match in _IBAN.finditer(text):
            if iban_ok(match.group()):
                add(match)
    elif kind == "emirates_id":
        for match in _EMIRATES_ID.finditer(text):
            if luhn_ok(match.group()):
                add(match)
    elif kind == "card":
        for match in _CARD.finditer(text):
            if 13 <= len(_digits(match.group())) <= 19 and luhn_ok(match.group()):
                add(match)
    elif kind == "ip":
        for match in _IP.finditer(text):
            if _ip_ok(match.group()):
                add(match)
    elif kind == "phone":
        for match in _PHONE.finditer(text):
            if 8 <= len(_digits(match.group())) <= 15:
                add(match)
    elif kind == "name":
        for match in _NAME.finditer(text):
            if match.group(1).split()[0] not in _NOT_NAMES:
                add(match, 1)
    else:
        raise ValueError(f"unknown kind {kind!r}. Choose from: {', '.join(KINDS)}")
    return found


def redact(text: str, kinds: tuple[str, ...] | list[str] | None = None, names: list[str] | None = None) -> Result:
    """Replace personal details in `text` with labels.

    `kinds` limits what is looked for (default: everything in KINDS).
    `names` is an optional list of names to remove wherever they appear, for when you already
    know who is in the conversation.
    """
    wanted = tuple(kinds) if kinds else KINDS
    unknown = [kind for kind in wanted if kind not in KINDS]
    if unknown:
        raise ValueError(f"unknown kind {unknown[0]!r}. Choose from: {', '.join(KINDS)}")
    readable = text.translate(_DIGITS)

    candidates: list[Finding] = []
    # The order of KINDS is the order of trust: when two findings overlap, the earlier kind wins.
    # An Emirates ID also passes the card check, and it is the more precise answer.
    for kind in KINDS:
        if kind in wanted:
            candidates.extend(_find(kind, readable))
    for name in names or []:
        if name.strip():
            for match in re.finditer(rf"\b{re.escape(name.strip())}\b", readable, flags=re.IGNORECASE):
                candidates.append(Finding("name", match.start(), match.end(), match.group()))

    rank = {kind: position for position, kind in enumerate(("email", "iban", "emirates_id", "card", "phone", "ip", "name"))}
    candidates.sort(key=lambda f: (rank[f.kind], f.start))
    kept: list[Finding] = []
    for candidate in candidates:
        if all(candidate.end <= other.start or candidate.start >= other.end for other in kept):
            kept.append(candidate)
    kept.sort(key=lambda f: f.start)

    pieces: list[str] = []
    cursor = 0
    findings: list[Finding] = []
    for finding in kept:
        pieces.append(text[cursor:finding.start])
        pieces.append(f"[{finding.kind.upper()}]")
        findings.append(Finding(finding.kind, finding.start, finding.end, text[finding.start:finding.end]))
        cursor = finding.end
    pieces.append(text[cursor:])
    return Result("".join(pieces), findings)
