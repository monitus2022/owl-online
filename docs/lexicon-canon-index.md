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
- contact decision (maintainer, 2026-11-07): no courtesy note before the
  harvest. A credit-and-notification note goes to the Lexicon feedback page
  (https://www.hp-lexicon.org/feedback/) when the project ships or the pack
  work concludes. Record it here:
  - sent: (not yet, at project end)
  - reply: (none)
- does not harvest the WordPress REST `character` payload beyond what the HTML
  gives at first; it is a later, optional field-level extension (it exposes
  structured `source_text`, `related_canon` and `first_introduced` fields).

## Site anatomy (observed 2026-11-07; refined by the #126 build)

The site is WordPress with Pods. Sitemap index: /sitemap_index.xml. Public
custom types: character (~1,450), creature (~274), event (~1,495), magic
(~398), place (~700), quote, source, thing (~2,140), trivia. REST exposes only
`character` and `real_person` under `wp/v2`; `pods/v1` requires
authentication, so HTML parsing driven by the sitemaps is the primary path.
The #126 harvest scope is the five item families plus the novel chapters;
characters stay out of this pass.

Two sitemap quirks the harvester handles:

- chapter pages: two canonical chapters are absent from the source sitemap
  because the site aliased their slugs (`gf/gf12-2`, `dh/dh33-the-princes-tale`)
  behind 301s. The chapter queue is therefore generated from the corpus code
  table (198 chapters + the `dh/dhe` epilogue), the fetcher follows redirects,
  and identity comes from the generated canonical url, not the final slug;
- non-novel source pages are cited by codes the abbreviation table never saw
  (`BCE`, `PmP`, `WSch`, `FBF`, `JKRTW`); their source-page path resolves the
  bucket (`classify_source_href`), so they are recorded as excluded canon
  instead of flooding the unknown queue;
- thin entries (a sweet mentioned once) carry no Related-Entries container
  and no references section; the article region then ends at the comments
  block or the site footer marker, and a page with no marker at all still
  raises. Every citation carries its bucket from parse time: re-classifying
  the bare code later would undo the href fallback.

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

All under `data/lexicon/` (gitignored), JSONL one record per line. Shipped
shapes as of #126:

| File | Record | Contents |
|---|---|---|
| pages/ + pages/*.json | fetch cache | raw HTML by url hash plus a sidecar per page (url, access date, response hash) |
| work_queue.jsonl | QueueItem | url, kind (entry, chapter), family |
| entries.jsonl | LexiconEntry | url, slug, family, title, magic_types, incantation (local only), citations count, related_groups, has_references_section, sidebar_scanned, unknown_tokens |
| citations.jsonl | CanonCitation | entry_url, entry_title, family, code, origin (href, anchor, bare, sidebar), href, valid_chapter (books only, null elsewhere), bucket, book_num, chapter_num, medium, is_epilogue |
| chapter_index.jsonl | ChapterLink | url, code, chapter_num, is_epilogue, abbreviation, canonicity, related tabs as (group, title, href) |
| fetch_index.jsonl | FetchRecord | url, path, from_cache, fetched_at, sha256 |
| harvest_failures.jsonl | Failure | url, stage (fetch, parse), reason |
| invalid_chapters.jsonl | InvalidEdge | entry_url, code - books codes outside the corpus chapter table |
| sidebar_missing.jsonl | ReviewRow | urls whose page had no detectable Sources widget |
| canon_index.jsonl | CanonEdge | #127: entry_key, family, title, book, chapter, epilogue, agreement, sources, low_precision, total_hits, candidates (chunk id, text hash, span, phrase) |

`canon_index.jsonl` carries chunk ids, text hashes and `[start, end)` spans
only - never book text; the pack builder (#128) reconstructs a quote by
slicing the corpus, so copyrighted text stays in one gitignored place.

Committed to git: the schema (pydantic models), the code-to-book table, the
parser, synthetic fixtures, and (once built) a summary coverage report checked
into docs or the pack build record. The harvested rows themselves stay local,
same discipline as the corpus.

## Pipeline stages

| Stage | Module | Responsibility |
|---|---|---|
| Discover | app/pipeline/ingest/lexicon/discovery.py | sitemap urls to the per-family entry queue, plus 199 novel chapters generated from the corpus code table; write the work queue |
| Fetch | app/pipeline/ingest/lexicon/fetch.py | polite cached fetch (1 rps + stable jitter, project UA, one retry with backoff, resume from cache); record fetch date and response hash per page |
| Parse | app/pipeline/ingest/lexicon/harvest.py + parse.py | run the spike parsers over the queue; entry identity, citation codes (href-derived novels, anchor text, bare parenthesials, sidebar widget), Related-Entries tabs; emits entries.jsonl, citations.jsonl, chapter_index.jsonl, fetch_index.jsonl, harvest_failures.jsonl |
| Normalize | app/pipeline/ingest/lexicon/codes.py | citation grammar: code or source-page path to (bucket, book_num, chapter_num); unknown codes queue loudly |
| Resolve | app/knowledge/lexicon.py (#127) | forward/reverse join with agreement labels; map each books chapter edge to candidate chunks by metadata plus token match (title, incantation, associated terms); attach chunk ids and text hashes |
| Report | scripts/lexicon_report.py (#127) | coverage per entry type and per subject pilot area; disagreement and unresolved-code queues; spot-check sample |

CLI entry points follow the existing style: `scripts/harvest_lexicon.py`
(discover, fetch, parse; `--discover-only`, `--limit`, `--reuse-queue`) with
`scripts/lexicon_report.py` landing in #127, both thin wrappers over library
code, as with `scripts/ingest_corpus.py`.

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
| Lesson mode (#43) | per-topic evidence ranges: which chapters teach a concept; every pack-backed lesson section still cites material ids and source refs, and a labelled off-pack section cites set-text chunk ids; the index only guides authoring |
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

Decision (2026-11-08): practical-defense contexts outside a sanctioned
classroom - Dumbledore's Army chapters and dueling-club scenes - are kept in
the draft table under explicit `da-army` / `duel-club` labels and map to the
author-pick basis with the reason recorded. Dropping them was rejected: DADA
classroom evidence is scarce, and the D.A. chapters document which defensive
spells the books treat as the practical core. The labels keep the precedence
honest - practice tiers inform membership, they never define it.

Approval (2026-11-08): the maintainer reviewed the seeded, key-concepts form
and approved the full draft list at the time - 51 DADA and 11 Charms rows - on
the grounds that the per-chapter context is rich and classroom evidence is
scarce. The approved table is compiled, structure-only, to
`config/lessons/dada.jsonl` and `config/lessons/charms.jsonl` with basis,
reason, evidence chunk ids, seed counts and approval metadata per row. The
DADA table was corrected to 53 rows during the materials audit on 2026-11-08:
three non-DADA rows were struck (`b1 c8`, `b2 c12`, `b2 c13`), five DADA
rows were added (`b3 c18`, `b5 c22`, `b5 c31`, `b6 c02`, `b7 c06`), and
non-classroom rows were re-based to `author-pick` with their actual teaching
context instead of inheriting the year's DADA teacher. The Charms table was
corrected to 9 rows in the same audit: five non-lesson rows were struck and
three real Charms scenes were added (`b1 c16`, `b4 c26`, `b6 c24`). The
coverage report remains the feedback loop: an approved row that seeds
nothing when the materials are authored is struck then, with the record
updated.

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

## Resolver results (#127, 2026-11-08)

`app/knowledge/lexicon.py` + `scripts/lexicon_report.py` join the harvest to
itself and to the corpus, emitting `data/lexicon/canon_index.jsonl`:

| Measure | Value |
|---|---:|
| canon edges (entry, book, chapter, epilogue) | 19,747 |
| agreement both / forward-only / reverse-only | 5,697 / 10,834 / 3,216 |
| edges with at least one chunk candidate | 8,328 |
| candidate refs retained (cap 8) / total hits | 22,611 / 33,144 |
| integrity failures (id missing, hash mismatch, span-without-phrase) | 0 |
| unparseable entry urls skipped | 0 |
| low-precision edges (hits exceed the cap) | 760 |
| sidebar-only edges (disagreement queue) | 8,559 |

The join is keyed `family/slug`; family is the first path segment that is a
known family (so nested `place/…/the-burrow` keys correctly) and the slug the
last segment. An early version keyed the last two segments and silently
skipped 6,851 nested urls; the fix (segment scan plus an on-build skip counter
and integrity pass) surfaced the ~5,300 place/creature edges the first cut
hid, which is exactly what the "recorded, never silently dropped" rule is for.

Every build calls `verify_edges`: each candidate's chunk id must exist, its
text hash must recompute to the chunk's current text, and its `[start, end)`
span must contain the match phrase. `--check-only` summarises an existing
index; `--sample N` prints a deterministic N-per-class review list with a
per-edge hash verdict.

Spot-check (ticket Done-when, two parts): the machine-checkable part is done
and recorded - `scripts/lexicon_report.py --sample 25` printed 25
both-agreement and 25 forward-only edges from the real corpus, every
candidate-bearing edge in the sample reported `hash-ok` (for example
`creature/acromantula` b5c16 -> `b5-c16-0057`, `magic/polyjuice-potion`
b5c31 -> `b5-c31-0062`) and the rest `no-candidate` (mostly event/place
entries whose titles are chapter names or formal geography, not verbatim
phrases). The full-index `verify_edges` pass (0 problems) is the same check
over everything, not just the sample. The human part - reading the sampled
quotes against the books, per pilot subject - was not recorded before PR #159
merged, so this criterion stands as automated-met / human-pending and the read
is carried into the #128 DADA and Charms authoring review; when it happens it
will be recorded here.

Rules as planned: the incantation beats the title as match phrase (rare
tokens; plural-tolerant word-boundary spans); book-level citations scan the
whole book; `DHE` resolves to b7-c36 from chunk ordinal 103 on and stays a
distinct edge from plain `DH36`; reverse-only edges are kept as hints; nothing
dropped silently. No book text is persisted: candidates carry spans only, so
the pack builder slices the quote from the corpus at build time.

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
  region runs from the `<h1>` to the first structural stop (Related Entries,
  else the comments block, else the site footer - priority order, so a marker
  occurring in prose cannot truncate the article) and a page with no stop at
  all raises, rather than silently scanning the footer;
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
- edges dedupe per (entry, code), with the sidebar origin kept as its own
  corroboration track; the Sources sidebar sits outside the article region and
  is scanned as a separate origin, so forward-vs-sidebar agreement is
  computable in #127;
- tale-level Beedle codes (`TBB/BR`, `TBB/WHH`, pattern `TBB/<XX>`) are
  bucketed as secondary books; `FWT`, `BLC`, `TLC2` and similar remain in the
  unknown queue for a human to place.

The spike module lives in `app/pipeline/ingest/lexicon/` (codes, parse) with
synthetic-structure tests (`tests/test_lexicon_codes.py`,
`tests/test_lexicon_parse.py`) and the sample runner `scripts/lexicon_spike.py`.

## Harvest results (#126, 2026-11-07)

Run record, honestly: pass 1 crawled the queue of 5,200 urls and cached 5,197
(3 chapter fetches failed in transit); pass 2, after fixing a parser crash on
prose parenthesials, re-parsed from cache and fetched the 3 outstanding
chapter urls; pass 3 re-parsed cache-only after the fetch-metadata and hub-page
fixes. Every final artifact number comes from pass 3. "One full crawl"
therefore means one queue, fully cached, over three resumable cache-first
passes - the design intent of the cache, exercised immediately.

Failure budget (stated, so the ticket criterion is checkable): parse failures
at most 0.1% of queued urls and zero for novel chapters; every failure names
its url. Observed: 3 failures of 5,195 (0.058%), all `/event/` pages that are
the site's own announcements (podcast launch, posting permissions) with no
`<h1>` article; chapters 0.

| Measure | Value |
|---|---:|
| entry pages harvested (magic / thing / creature / place / event) | 4,993 (397 / 2,133 / 273 / 699 / 1,491) |
| novel chapters harvested | 199 / 199 (aliased `gf12`, `dh33` resolved via their 301s; `dhe` included) |
| citation rows | 29,393 |
| books-bucket edges, valid | 22,797 |
| books edges flagged out-of-range (site-broken hrefs `DH117`, `PS21`, `HBP33`) | 3 |
| excluded (film, play, other canon) | 4,733 |
| secondary-books (incl. tale-level Beedle codes) | 1,860 |
| epilogue (`DHE`) edges | 26 |
| sidebar-origin corroboration rows | 18,053 |
| fetch_index rows with access date and response hash | 5,195 / 5,195 |
| zero-citation entries (mostly film-only and trivia pages) | 673 (13.5%) |
| unknown-code queue | 139 distinct tokens, top: QWC, NSOED, BLC, MACUSA, WW, DL |

Five family hub/archive pages (`/magic/`, `/thing/`, ...) were dropped from
the queue after the first pass showed they parse as archive listings, not
entries.

Bugs the full run exposed, each fixed with a regression test: prose
parenthesials splitting to empty tokens crashed `classify`; HTML entities
(`&#8220;`) entered the token stream; cache-only re-parses lost fetch dates
(metadata now lives in a sidecar written at fetch time and backfilled from
file mtime, so `fetch_index.jsonl` keeps the access date #128 attribution
needs); cache writes are atomic and zero-byte files re-fetch; sitemap fetches
now obey the same politeness as pages.

Chapter-title cross-check (site abbreviation vs corpus `chapter_name`, all
199 chapters), reproducible via `scripts/lexicon_title_check.py`: 182 exact
matches; 17 explained deltas - 7 where our ingest stores the fallback
"Chapter N" with no title, 6 where it stored only one line of a multi-line
title (for example "…PLATFORM NINE AND" missing "THREE-QUARTERS"), 3 US/UK
spelling or wording (Dueling/Duelling, Pajamas/Pyjamas, Career/Careers), and
the intentional `dhe` -> c36 mapping. The fallback and one-line groups are
findings for the corpus ingest (#113 line of work), not for this pipeline;
#127 treats the cross-check as informational.

The unknown queue is dominated by real source abbreviations not yet tabled
(QWC, NSOED, AHD = dictionaries and companion citations; BLC, TLC, FWT,
MACUSA, ICW = web/other-canon pages) plus prose that survived the shape gate
(`O.W.L.`, `B.O.G.`). None of it entered the books bucket. #127 triages only
the codes appearing on pilot-subject entries.

Artifacts (all gitignored): `entries.jsonl`, `citations.jsonl`,
`chapter_index.jsonl`, `fetch_index.jsonl` (access date + response hash per
page, sidecar-backed), `harvest_failures.jsonl`, `invalid_chapters.jsonl`,
`sidebar_missing.jsonl`, `work_queue.jsonl`; spike artifacts moved to
`data/lexicon/spike/` so a re-run cannot clobber the harvest.

## Ticket breakdown

| Ticket | Scope | Done when |
|---|---|---|
| #125 spike | hand-pick ~25 spell and ~25 potion entries around the DADA and Charms pilot; save their HTML locally only; prototype the parse rules; settle DHE, bare parenthesials, multi-code bullets and the reverse-tab semantics; write synthetic fixtures from structure (markup skeleton, no site prose) | fixtures parse in tests; the hand sample shows a books/chapters mapping a reviewer agrees with; open questions closed in this doc |
| #126 harvester | discovery, fetch, parse modules plus scripts/harvest_lexicon.py; cache, rate limit, resume; unit tests on synthetic fixtures | full polite crawl runs in one pass; entries, citations and chapter_index written; parse failure report under a stated budget |
| #127 resolver | code grammar, buckets, forward/reverse join, chunk candidate resolution, canon_index.jsonl, coverage report | validation rules above hold; disagreement queue non-empty and human-readable; spot-checks pass |
| #128 pack wiring (depends on #87 schema landing) | pack build reads canon_index for concept seeding and reference/source-ref prefill; DADA authored and published, Charms seeded; attribution recorded | a reviewed DADA material cites both a Lexicon reference and a books-bucket source_ref that hash-validates |

#125 (PR #130), #126 (PR #148) and #127 (PR #159) are merged and closed.
#128 is open under the V3 - Product milestone. The DADA and Charms packs are
published at 1.0.0 and the seeding queues are landed; the remaining work is the
other subject content passes and the coverage report.

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
