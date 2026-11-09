"""Deterministic content terms for lesson scope and lexical pack matching.

The coverage check and the curated concept matcher must agree on what a word
means. This module owns that decision: lowercase tokens, a small stopword list,
and a plural fold that keeps werewolf/werewolves, pixie/pixies and
curse/curses on the same side of the comparison.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "against",
        "all",
        "also",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "between",
        "book",
        "books",
        "both",
        "but",
        "by",
        "call",
        "called",
        "charm",
        "charms",
        "can",
        "case",
        "cases",
        "chapter",
        "chapters",
        "compare",
        "comparison",
        "could",
        "creature",
        "creatures",
        "curse",
        "curses",
        "dangerous",
        "dark",
        "defence",
        "defend",
        "defends",
        "defense",
        "department",
        "describe",
        "did",
        "difference",
        "do",
        "does",
        "doing",
        "done",
        "each",
        "eighth",
        "event",
        "events",
        "example",
        "examples",
        "explain",
        "favourite",
        "favorite",
        "fifth",
        "first",
        "for",
        "fourth",
        "from",
        "give",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "kind",
        "kinds",
        "know",
        "known",
        "lesson",
        "lessons",
        "like",
        "look",
        "looking",
        "looks",
        "magic",
        "magical",
        "may",
        "me",
        "mean",
        "meaning",
        "means",
        "might",
        "more",
        "most",
        "must",
        "my",
        "name",
        "names",
        "ninth",
        "no",
        "not",
        "note",
        "notes",
        "number",
        "numbers",
        "of",
        "on",
        "once",
        "one",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "out",
        "over",
        "page",
        "pages",
        "part",
        "parts",
        "please",
        "prof",
        "protect",
        "protects",
        "protection",
        "professor",
        "really",
        "same",
        "say",
        "says",
        "said",
        "school",
        "second",
        "section",
        "sections",
        "seventh",
        "she",
        "should",
        "similar",
        "sixth",
        "spell",
        "spells",
        "so",
        "some",
        "student",
        "students",
        "such",
        "teacher",
        "tell",
        "tenth",
        "text",
        "texts",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "then",
        "there",
        "these",
        "they",
        "third",
        "this",
        "three",
        "two",
        "those",
        "through",
        "to",
        "too",
        "type",
        "types",
        "ten",
        "thousand",
        "under",
        "until",
        "up",
        "us",
        "use",
        "used",
        "using",
        "versus",
        "very",
        "vs",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "whose",
        "why",
        "will",
        "with",
        "without",
        "wizard",
        "wizards",
        "wizarding",
        "work",
        "worked",
        "working",
        "works",
        "world",
        "would",
        "hundred",
        "year",
        "years",
        "you",
        "your",
        "yours",
    }
)


def variants(word: str) -> set[str]:
    """The forms a plural may take, without a full stemmer.

    Keeping the original and the plausible singular forms on both sides of the
    comparison avoids the werewolf/werewolves and pixie/pixies mismatches that a
    single naive suffix rule creates.
    """
    forms = {word}
    if len(word) > 4 and word.endswith("ies"):
        forms.add(word[:-3] + "y")
        forms.add(word[:-3] + "ie")
    if len(word) > 4 and word.endswith("ves"):
        forms.add(word[:-3] + "f")
        forms.add(word[:-3] + "fe")
    if len(word) > 3 and word.endswith("es"):
        forms.add(word[:-1])
        forms.add(word[:-2])
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        forms.add(word[:-1])
    if len(word) > 5 and word.endswith("ing"):
        forms.add(word[:-3])
        forms.add(word[:-3] + "e")
    if len(word) > 5 and word.endswith("tion"):
        forms.add(word[:-4] + "t")
    return forms


def content_terms(text: str) -> set[str]:
    """The meaningful words in a question or a passage, with plural variants."""
    terms: set[str] = set()
    for word in _WORD.findall(text.lower()):
        if len(word) >= 3 and word not in _STOPWORDS:
            terms.update(variants(word))
    return terms


def missing_terms(text: str, coverage: str) -> set[str]:
    """Words in `text` with no variant in `coverage`."""
    coverage_terms = content_terms(coverage)
    missing: set[str] = set()
    for word in _WORD.findall(text.lower()):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        forms = variants(word)
        if not (forms & coverage_terms):
            missing.update(forms)
    return missing


def phrase_match_score(phrase: str, question_terms: set[str]) -> int:
    """How many words of a concept title or alias the question contains.

    Zero means the phrase is not present as a whole. Matching is per word and
    plural-aware, so "Werewolves" matches "What is a werewolf?" but "Disarming
    Charm" does not match "What is a charm spell?".
    """
    words = [
        word
        for word in _WORD.findall(phrase.lower())
        if len(word) >= 3 and word not in _STOPWORDS
    ]
    if not words:
        return 0
    matched = sum(1 for word in words if variants(word) & question_terms)
    return matched if matched == len(words) else 0
