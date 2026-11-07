# Lexicon canon index

Last updated: 2026-11-07.

Plan for a pipeline that builds an item/concept-to-book index from The Harry
Potter Lexicon (https://www.hp-lexicon.org/). The product is a local mapping
table: every indexed entry (spell, potion, creature, object, place, character,
event) to the book chapters the site cites for it, split by canon scope, then
resolved to chunk ids in our own corpus. It feeds the subject packs (#87),
lesson and exam evidence targeting, and coverage reports. It is not corpus and
it is not a second RAG index.

## Goals

- a validated map from Lexicon entries to (book, chapter) pairs for the seven
  novels, with the secondary canon books (QA, FB, TBB, BoS, BoP) recorded as a
  separate bucket;
- film, game and tertiary citations (WFT, CG, SD, CC, /f, /g, PM, JKR, DP, FW)
  recorded and tagged out of scope, never silently dropped, so a reviewer can
  see what was excluded and why;
- resolution of each (entry, book, chapter) pair to candidate chunk ids and
  text hashes in our own index, so a pack material can carry them as
  `source_refs` after human review;
- a coverage report per subject: which concepts have book evidence, in which
  chapters, and which are thin or absent. Thin coverage is reported, not padded.

## Non-goals

- storing Lexicon prose in the pack, in git, or in the vector index;
- ingesting Lexicon pages as retrievable documents (the books are the corpus);
- generating material text from the Lexicon (source text stays books-only);
- using film or game canon at this stage;
- any model call. Harvest, parse and resolve are deterministic.

## Source policy and etiquette

The Lexicon terms of use (https://www.hp-lexicon.org/terms-of-service/) allow
research and fan-project use, require attribution with a link, forbid verbatim
copying outside fair use, and forbid republishing the site. robots.txt carries
no disallow rules and no content-signal values. The pipeline therefore:

- takes structure only: entry titles, entry urls, entry types, citation codes,
  related-entry links, and our own access dates;
- derives quotes from our own corpus (chapter chunks matched by entry tokens),
  never from Lexicon prose;
- keeps every fetched page and derived artifact under `data/lexicon/`, which is
  gitignored; only schema code, synthetic test fixtures and aggregate reports
  land in git;
- attributes every `references` entry with title, url, publisher and accessed
  date, matching the `ReferenceLink` record in `docs/workplan.md`;
- crawls once, politely: identify the client in the User-Agent, one request per
  second with jitter, cache by url with the response hash, and re-fetch only on
  a deliberate rebuild. A full crawl is under 10k pages;
  roughly two hours at that rate;
- does not harvest the WordPress REST `character` payload beyond what the HTML
  gives at first; it is a later, optional field-level extension (it exposes
  structured `source_text`, `related_canon` and `first_introduced` fields).

## Site anatomy (observed 2026-11-07)

The site is WordPress with Pods. Sitemap index: /sitemap_index.xml. Public
custom types: character (~1,450), creature, event, magic (~398), place, quote,
source, thing (~2,140), trivia. REST exposes only `character` and `real_person`
under `wp/v2`; `pods/v1` requires authentication, so HTML parsing driven by the
sitemaps is the primary path.

Anatomy that matters for parsing, from the observed pages:

| Page | Structure we harvest |
|---|---|
| Concept entry (e.g. /magic/summoning-charm/) | title; entry type; info lines (magic type, incantation, associated terms); References from the canon list: prose bullets with citation codes, book codes hyperlinked to /source/the-harry-potter-novels/gf/gf6/ style urls; Sources sidebar: per-source chapter links; Related Entries tabs |
| Chapter page (e.g. /source/.../gf/gf6/) | book and chapter identity in the url and the metadata block (Abbreviation, Canonicity: Primary Canon); chapter title; Related Entries tabs: Characters, Locations, Magic, Things, Creatures - a reverse chapter-to-entry index |

Both directions exist independently, so each edge can be corroborated:
forward (entry cites chapter) and reverse (chapter lists entry). Agreement
between them is the confidence signal.

## Citation grammar

Novel codes (in scope, primary): `PS`, `CS`, `PA`, `GF`, `OP`, `HBP`, `DH`
plus a chapter number, and `DHE` for the Deathly Hallows epilogue. Codes appear
as link anchors or bare parenthesials. A trailing `/f` means the film, `/g` the
game: record under excluded, not books.

Secondary canon books (recorded, not exam-gradable in v1): `QA`, `FB`, `TBB`,
`BoS`, `BoP`.

Other sources seen on entry pages (recorded, out of scope now): `WFT`, `CG`,
`SD`, `CC`, `PM`, `JKR`, `JKR:Tw`, `DP`, `FW`, `BFT`, `Pre`, `HPM`, `MagSp`.

Bucketing table:

| Bucket | Codes | Pack use |
|---|---|---|
| books | PS1-17, CS1-18, PA1-22, GF1-37, OP1-38, HBP1-30, DH1-36, DHE | source_refs (primary tier) |
| secondary-books | QA, FB, TBB, BoS, BoP | references (secondary tier) |
| excluded | WFT, CG, SD, CC, any /f or /g, PM, JKR, DP, FW, interviews | recorded, review-only, never source_refs |

Book code to corpus mapping:

| Code | book_num | Corpus chapters |
|---|---|---|
| PS | 1 | 1-17 |
| CS | 2 | 1-18 |
| PA | 3 | 1-22 |
| GF | 4 | 1-37 |
| OP | 5 | 1-38 |
| HBP | 6 | 1-30 |
| DH | 7 | 1-36 |

The counts above match `data/chunks.jsonl` exactly (verified 2026-11-07). Two
known deltas, both settled by the spike (see Spike findings):

- `DHE`: the epilogue text lives at the tail of book 7 chapter 36, from the
  marker inside chunk `b7-c36-0103`; `DHE` resolves to that slice;
- The Lexicon cites the UK Bloomsbury text; our corpus is the US edition.
  Chapter titles and numbering are identical across the seven books; book 1
  differs only in title (Philosopher's vs Sorcerer's Stone). Record both titles.

## Artifacts

All under `data/lexicon/` (gitignored), JSONL one record per line:

| File | Record | Contents |
|---|---|---|
| pages/ | fetch cache | raw HTML by url hash, fetch date, response hash |
| entries.jsonl | LexiconEntry | url, slug, title, entry_type, magic_types, incantation, canonicity note |
| citations.jsonl | CanonCitation | entry_url, code, bucket, book_num, chapter_num, origin (href, anchor, bare), parse confidence |
| chapter_index.jsonl | ChapterLink | book_num, chapter_num, entry_urls with their Related-Entries tab |
| canon_index.jsonl | CanonEdge | entry_id, book_num, chapter_num, agreement (forward, reverse, both), candidate chunk ids, text hashes |

This is the target contract. The #125 spike emits a subset: the cache stores
raw HTML only (fetch date and response hash land with #126), `entries.jsonl`
has no `slug`/`entry_type`/`canonicity` yet (the entry type comes from the URL
path and the sitemap split in #126), and `citations.jsonl` carries no parse
confidence (the origin plus the unknown queue play that role until #127 needs
a score). The `incantation` field holds site sentence text and stays local:
it must never be echoed into a committed report.

Committed to git: the schema (pydantic models), the code-to-book table, the
parser, synthetic fixtures, and (once built) a summary coverage report checked
into docs or the pack build record. The harvested rows themselves stay local,
same discipline as the corpus.

## Pipeline stages

| Stage | Module | Responsibility |
|---|---|---|
| Discover | app/pipeline/ingest/lexicon/discovery.py | sitemap index to per-type url lists; write a work queue |
| Fetch | app/pipeline/ingest/lexicon/fetch.py | polite cached fetch (1 rps, UA, retry, resume); never refetch on cache hit |
| Parse | app/pipeline/ingest/lexicon/parse.py | entry identity, citation codes from anchor text and bare parenthesials, Related Entries tabs; emits entries.jsonl, citations.jsonl, chapter_index.jsonl |
| Normalize | app/knowledge/lexicon.py | code grammar: bucket, book_num, chapter_num; reject unknown codes loudly |
| Resolve | app/knowledge/lexicon.py | forward/reverse join with agreement labels; map each book chapter edge to candidate chunks by metadata plus token match (title, incantation, associated terms); attach chunk ids and text hashes |
| Report | scripts/lexicon_report.py | coverage per entry type and per subject pilot area; disagreement and unresolved-code queues; spot-check sample |

CLI entry points follow the existing style: `scripts/harvest_lexicon.py`
(discover, fetch, parse) and `scripts/lexicon_report.py` (resolve, report), both
thin wrappers over library code, as with `scripts/ingest_corpus.py`.

Parsing notes, settled by the spike (see Spike findings above):

- codes arrive as hyperlinks or bare parenthesials; novel codes derive from the
  href, non-novel ones from the anchor text or the parens;
- one sentence can cite several chapters; edges are per code, split on comma,
  `&` and `and`;
- the spike dedupes to one edge per (entry, code) and scans only the article
  region, so the Sources sidebar (a separate `col-md-4` list below the region)
  is not yet cross-checked against the forward codes; that disagreement
  signal is deferred to #126/#127, not implemented here;
- Related Entries tabs are editor-curated and broader than literal mentions:
  they corroborate but never create source refs on their own.

## Consumers

| Consumer | How it uses the index |
|---|---|
| #87 subject packs | seeds the Concept list per subject from entry type and magic type (for example Charms: every Summoning-type spell with books citations); pre-fills references entries with title, url, publisher, accessed; pre-fills candidate source_refs (chunk ids and hashes) so an author writes grounded text against known evidence instead of hunting chapters by hand |
| Lesson mode (#43) | per-topic evidence ranges: which chapters teach a concept; every lesson section still cites material ids and source refs, the index only guides authoring |
| Exam bank (#39) | question targeting: pick concepts whose primary coverage lands in the books/tiers the paper scopes to; coverage report gates publishing a thin subject |
| Retrieval (later, optional) | chapter-level concept lists as a side table for scoped retrieval or filter hints; measured retrieval-only first under the #96/#105 discipline before anything is wired; the flag stays off until it passes |
| Eval | gold-set authors can cite chapters with the same code grammar (OP29, GF6) and the resolver checks that the quoted passage exists in those chapters |

## Subject assignment

The Lexicon does not decide what belongs to a subject. Its `magictype` tags
(charms, defensive magic, transfiguration, movement, transportation...) answer
what kind of magic an item is. That is not the same question as which Hogwarts
class teaches it, and the tags are a fan taxonomy, not the curriculum. Subject
membership is a canon fact, and the books carry the evidence directly: a
classroom scene names the teacher, the class and the spell or material.

Assignment rule, in order of authority:

| Basis | Signal | Authority |
|---|---|---|
| taught-in-class | the item is cited in a chapter flagged as a lesson scene for the subject (Wingardium Leviosa in the PS6 charms lesson; the Boggart Jinx in the PA8 Lupin Defence class; Mandrake in the CS10 Sprout lesson) | decisive |
| used-in-exam-context | the item appears in a described O.W.L. or N.E.W.T. or lesson-adjacent exam scene for the subject | strong, still needs a books citation |
| taxonomy-prior | the Lexicon magictype and the related entries of the subject's lesson chapters | discovery and ranking only; never publishes membership on its own |
| author-pick | a human reviewer assigns the item to a topic with reasons recorded | allowed, must carry reviewed status and a books-bucket source ref |

The missing artifact is small and human-authored: a chapter-to-subject table.
Of the roughly 198 novel chapters, only a few dozen contain classroom teaching
scenes; each flagged chapter records subject and teacher. DADA makes this
per-book rather than per-series - the post is held by a different teacher each
year, so the same topic (for example shield charms) may be taught in one book
and only practised in another. The table is validated against our own corpus: a
lesson chapter must show teacher-plus-classroom cues in the chunk text. Lexicon
chapter pages help find the scenes; the book text is the proof.

Scope-first keeps the problem tractable. A pack declares its topics (the workplan
already fixes the DADA scope list), so we only ever assign items relevant to
those topics. We never classify all ~400 magic and ~2,000 thing entries into
twelve subjects; the join is topic-relevant-items intersected with the subject's
lesson-chapter citations, not a global partition.

Consequences to accept:

- multi-subject items are normal (a vanishing spell can be taught in
  Transfiguration and used under DADA pressure); each membership record stands
  on its own evidence;
- items with no lesson-scene evidence sit in an unassigned bucket, which is the
  correct canon answer, not a failure: being real in the world is not being on
  the syllabus (the Summoning Charm is cited in many chapters and taught in
  none);
- the coverage report counts assigned and unassigned per topic, and the
  generator reads only assigned, reviewed materials with books-bucket source
  refs.

Each assignment is recorded as: concept id, subject, tier, basis, source refs,
references, review status. The workplan publication rule carries over: no
material publishes without a reviewed basis and at least one books-bucket
source ref.

## Validation

- every books-bucket citation resolves to a (book, chapter) inside the table
  above; unknown codes fail loudly, never drop;
- every chapter title from the Lexicon matches the ingested chapter_name for
  that (book, chapter) case-insensitively, modulo known punctuation; this is
  the drift detector if the corpus is ever re-ingested;
- agreement split is reported: forward-only, reverse-only, both; a spot-check
  of 25 both-agreement and 25 forward-only edges per pilot subject is read by a
  human against the book text;
- every canon_index edge with candidate chunks carries a chunk id that exists
  in the current index and a matching text hash;
- counts sanity: the seven novels produce roughly 198 chapter pages; all are
  fetched and parsed, zero parse failures on the References section presence.

## Spike findings (#125, 2026-11-07)

The spike crawled 55 hand-picked spell/potion entries around the DADA and
Charms pilot plus 14 chapter pages (gitignored cache under `data/lexicon/`).
Final parsed result: 343 citations; 274 books-bucket edges, 54 excluded
(film/play/screenplay/other canon), 15 secondary-books; 0 out-of-range chapter
codes; 0 fetch or parse failures; 7 unknown tokens queued (SDNY, FWT, BCE,
BLC, TLC2 and the tale-level `TBB/BR`, `TBB/WHH`); 1 legitimate zero-citation
page (Wideye Potion, whose references say only "brewable on Pottermore").
Reverse-tab corroboration over the 14 sampled chapters: 40 magic-family tab
edges, 24 agreeing with forward edges, 16 reverse-only (entries outside the
hand-picked 55, as expected). Spot checks agree with the book text: Summoning
Charm cites GF6 and `Accio!` appears in chunk `b4-c06-0011` of our corpus. The
parse rules were rebuilt on these observations:

- citations live anywhere in the article, not only the references list; prose
  outside the section still carries real citations (Corporeal Patronus carries
  `(Pm)` and `(JKR:Tw)` in narrative with no references heading at all);
- the references block is a `<ul>` on most pages but plain `<p>` blocks on
  some, and the heading is "References from the canon" or "Canon references";
- every page's footer nav links every chapter of every book: the article
  region runs from the `<h1>` to the first `related_container` and a page
  without that boundary raises, rather than scanning the footer silently;
- the sidebar fact box sits inside that region on many pages; it contains no
  `/source/` links, so it is harmless to the citation scan, but its free text
  (`incantation`, pronunciation sentences) must never be echoed into a
  committed report;
- novel codes are derived from the href (`/gf/gf6` -> `GF6`), which also picks
  up anchors whose text is not the code; non-novel codes stay bare parenthesials;
- capitalisation drift is real: `Pm` (Pottermore) beside `PM`; both are table
  entries, kept case-distinct deliberately;
- decimal scene codes exist for the play (`CC2.13`, `CC3.9`): bucket from the
  prefix, chapter left unset;
- whole-book citations occur (no chapter number): the edge is book-scoped,
  `chapter_num` null;
- the Deathly Hallows epilogue settles: the site page is `/dh/dhe/`
  (abbreviation `DH/e`, 55 related entries); the forward code `DHE` resolves
  to book 7 chapter 36 with an `is_epilogue` flag that keeps it distinct from a
  plain `DH36` citation; in our corpus the epilogue begins inside chunk
  `b7-c36-0103` (its heading block sits at the chapter 36 tail), and #127 pins
  the exact slice boundary as a resolver constant, not a prose string copied
  into this doc;
- chapter reverse tabs use mixed group names (plural `characters`/`things`,
  singular `magic`): the parser normalises them; reverse edges corroborate,
  never create refs;
- parenthesised tokens are queue-gated by shape (digit-bearing or all-caps):
  prose like `(Molly)` is not mistaken for a source code, while `SDNY` and
  `MACUSA`-style news abbreviations surface for review;
- multi-code lists split on comma, `&` and `and` (`(PS1 and PS2)` -> two edges);
- edges dedupe per (entry, code) per page; the Sources sidebar sits outside
  the region and its cross-check with the references list is scoped to #126,
  where a real DOM boundary replaces the substring rule;
- #126 must extend the table with the tale-level Beedle codes (`TBB/BR`,
  `TBB/WHH`, `TBB/FFF`, `TBB/WHP` pattern) and the companion-book prefixes
  behind `FWT`, `BLC`, `TLC2` after a human confirms what they cite.

The spike module lives in `app/pipeline/ingest/lexicon/` (codes, parse) with
synthetic-structure tests (`tests/test_lexicon_codes.py`,
`tests/test_lexicon_parse.py`) and the sample runner `scripts/lexicon_spike.py`.

## Ticket breakdown

| Ticket | Scope | Done when |
|---|---|---|
| #125 spike | hand-pick ~25 spell and ~25 potion entries around the DADA and Charms pilot; save their HTML locally only; prototype the parse rules; settle DHE, bare parenthesials, multi-code bullets and the reverse-tab semantics; write synthetic fixtures from structure (markup skeleton, no site prose) | fixtures parse in tests; the hand sample shows a books/chapters mapping a reviewer agrees with; open questions closed in this doc |
| #126 harvester | discovery, fetch, parse modules plus scripts/harvest_lexicon.py; cache, rate limit, resume; unit tests on synthetic fixtures | full polite crawl runs in one pass; entries, citations and chapter_index written; parse failure report under a stated budget |
| #127 resolver | code grammar, buckets, forward/reverse join, chunk candidate resolution, canon_index.jsonl, coverage report | validation rules above hold; disagreement queue non-empty and human-readable; spot-checks pass |
| #128 pack wiring (depends on #87 schema landing) | pack build reads canon_index for concept seeding and reference/source-ref prefill; DADA and Charms pilots authored from it; attribution recorded | a reviewed DADA material cites both a Lexicon reference and a books-bucket source_ref that hash-validates |

Tickets #125-#128 are open on GitHub under the V3 - Product milestone.

## Risks

| Risk | Mitigation |
|---|---|
| Site markup drift breaks parsing silently | structure-anchored selectors, loud failure on a page with no References section, re-run cost is one crawl |
| Terms-of-use drift or objection from the site | structure-only artifacts, attribution on every reference, low volume, honest UA; be ready to pause and ask via their feedback page |
| Film citations pollute the mapping | bucket is explicit in every record; packs validator refuses a source_ref whose citation bucket is not books |
| Editor curation (Related Entries) is broader than book fact | reverse-only edges are hints, never evidence; token match against our own chunks is mandatory |
| US/UK edition deltas | chapter identity is edition-independent; the chapter-title cross-check catches anything else |
| DH epilogue mis-resolves | spike settles it; DHE gets its own rule instead of a silent c36 assumption |
| One-off crawl goes stale as we rebuild the pack | accessed date per record plus a manual rebuild command; no scheduled scrape |

## Keeping this current

- update the site anatomy section when a parser change learns something new;
- record the crawl date and entry counts in the pack build manifest;
- when retrieval-side use (#96-style measurement) is proposed, write it here as
  a numbered step with its own measurement plan before code.
