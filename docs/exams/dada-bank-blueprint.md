# DADA exam-bank blueprint

- Date: 2026-11-09
- Ticket: #188
- Subject: `dada`
- Pack: 1.0.0, fingerprint `e7139cbcc23eaa5c`
- Index text hash: `aca4c57462d449f5`
- Status: go

## Decision

Go with the published DADA 1.0.0 pack for the first bank of 25 MCQ and 25
short-answer questions. Do not top up the pack before the first authoring pass.

The pack has exactly 25 reviewed materials, so the target is one MCQ and one
short answer per material on average. The 21 concepts give about 1.2 items per
type per concept, and the four concepts with two materials can carry at most
two items per type. That is enough for 50 distinct items without stretching a
single source.

The exception is event coverage. The pack has no standalone event materials.
Events appear inside reviewed materials, for example the D.A. training, the
final battle and the Triwizard maze, but there is no event concept to carry a
dedicated event question. Event questions are therefore limited to events
already grounded in the cited material. A dedicated event top-up is a later
decision, not a blocker for this bank.

Stop and top up if more than three materials cannot support a distinct MCQ and a
distinct short answer after review. Record the failed slots and the reason.

## Current material base

- 25 materials, 21 concepts, 4 topics, 125 source refs.
- Materials range from 106 to 152 words.
- Every material is primary canon, books-scoped and reviewed.
- The pack validates with zero errors and zero warnings against the current corpus hash.

The gap analysis reads the seed queue because it is the reviewed bridge from the
Lexicon canon index (`data/lexicon/canon_index.jsonl`) to pack concepts.
`scripts/lexicon_report.py` remains the lexicon-level coverage report.

## Coverage matrix

Generated with:

```text
uv run python scripts/bank_coverage.py --subject dada
```

### Topics

| Topic | Title | Materials | Concepts | Words | Refs | Share | MCQ capacity | Short capacity |
|---|---|---|---|---|---|---|---|---|
| dark-arts | The Dark Arts | 4 | 4 | 529 | 16 | 16% | 4 | 4 |
| dark-creatures | Dark Creatures | 10 | 8 | 1291 | 51 | 40% | 10 | 10 |
| defensive-magic | Defensive Magic | 9 | 7 | 1074 | 41 | 36% | 9 | 9 |
| dueling | Dueling | 2 | 2 | 278 | 17 | 8% | 2 | 2 |

Capacity is the material count under the one-MCQ-and-one-short-per-material
rule. Seventeen of the 21 concepts have one material. Only dueling is below 20
percent of the bank, at 8 percent; it still receives two items per type.

### Concepts

| Concept | Kind | Title | Materials | Refs | Words |
|---|---|---|---|---|---|
| dada-creature-boggart | creature | Boggart | 2 | 8 | 258 |
| dada-creature-dementors | creature | Dementors | 1 | 5 | 139 |
| dada-creature-grim | creature | Grim | 1 | 2 | 117 |
| dada-creature-grindylow | creature | Grindylow | 1 | 6 | 129 |
| dada-creature-pixie | creature | Pixies | 1 | 6 | 137 |
| dada-creature-thestral | creature | Thestrals | 1 | 7 | 124 |
| dada-creature-werewolf | creature | Werewolves | 2 | 10 | 258 |
| dada-magic-boggart-banishing-spell | spell | Boggart Banishing Spell | 1 | 7 | 129 |
| dada-magic-concealment-charm | spell | Concealment Charm | 1 | 4 | 116 |
| dada-magic-corporeal-patronus | spell | Corporeal Patronus | 1 | 7 | 127 |
| dada-magic-countercurse | spell | Countercurse | 1 | 5 | 128 |
| dada-magic-cruciatus-curse | spell | Cruciatus Curse | 1 | 3 | 131 |
| dada-magic-disarming-charm | spell | Disarming Charm | 1 | 9 | 150 |
| dada-magic-fidelius-charm | spell | Fidelius Charm | 1 | 4 | 118 |
| dada-magic-hex-deflection | spell | Hex-Deflection | 1 | 4 | 124 |
| dada-magic-imperius-curse | spell | Imperius Curse | 1 | 6 | 146 |
| dada-magic-killing-curse | spell | Killing Curse | 1 | 4 | 130 |
| dada-magic-patronus | spell | Patronus | 2 | 9 | 234 |
| dada-magic-shield-charm | spell | Shield Charm | 2 | 8 | 227 |
| dada-magic-stunning-spell | spell | Stunning Spell | 1 | 8 | 128 |
| dada-magic-unforgivable-curses | spell | Unforgivable Curses | 1 | 3 | 122 |

### Materials

| Material | Topic | Concept | Kind | Words | Refs |
|---|---|---|---|---|---|
| dada-countering-countercurse-doctrine | defensive-magic | dada-magic-countercurse | spell | 128 | 5 |
| dada-countering-detection-and-concealment | defensive-magic | dada-magic-concealment-charm | spell | 116 | 4 |
| dada-countering-hex-deflection | defensive-magic | dada-magic-hex-deflection | spell | 124 | 4 |
| dada-dark-arts-cruciatus-evidence | dark-arts | dada-magic-cruciatus-curse | spell | 131 | 3 |
| dada-dark-arts-imperius-demonstration | dark-arts | dada-magic-imperius-curse | spell | 146 | 6 |
| dada-dark-arts-killing-curse-limits | dark-arts | dada-magic-killing-curse | spell | 130 | 4 |
| dada-dark-arts-unforgivables-law | dark-arts | dada-magic-unforgivable-curses | spell | 122 | 3 |
| dada-dark-creatures-boggarts-counter | dark-creatures | dada-magic-boggart-banishing-spell | spell | 129 | 7 |
| dada-dark-creatures-boggarts-field | dark-creatures | dada-creature-boggart | creature | 152 | 5 |
| dada-dark-creatures-boggarts-nature | dark-creatures | dada-creature-boggart | creature | 106 | 3 |
| dada-dark-creatures-dementors-nature | dark-creatures | dada-creature-dementors | creature | 139 | 5 |
| dada-dark-creatures-fieldcraft-pixies | dark-creatures | dada-creature-pixie | creature | 137 | 6 |
| dada-dark-creatures-fieldcraft-thestrals | dark-creatures | dada-creature-thestral | creature | 124 | 7 |
| dada-dark-creatures-fieldcraft-water-and-marsh | dark-creatures | dada-creature-grindylow | creature | 129 | 6 |
| dada-dark-creatures-grim-private-fear | dark-creatures | dada-creature-grim | creature | 117 | 2 |
| dada-dark-creatures-werewolves-law-and-fear | dark-creatures | dada-creature-werewolf | creature | 130 | 4 |
| dada-dark-creatures-werewolves-recognition | dark-creatures | dada-creature-werewolf | creature | 128 | 6 |
| dada-dueling-disarming-charm | dueling | dada-magic-disarming-charm | spell | 150 | 9 |
| dada-dueling-shield-charm | defensive-magic | dada-magic-shield-charm | spell | 115 | 4 |
| dada-dueling-stunning-spell | dueling | dada-magic-stunning-spell | spell | 128 | 8 |
| dada-magic-patronus-theory | defensive-magic | dada-magic-patronus | spell | 123 | 5 |
| dada-magic-patronus-training | defensive-magic | dada-magic-corporeal-patronus | spell | 127 | 7 |
| dada-protective-fidelius-trust | defensive-magic | dada-magic-fidelius-charm | spell | 118 | 4 |
| dada-protective-patronus-field | defensive-magic | dada-magic-patronus | spell | 111 | 4 |
| dada-protective-wards-at-scale | defensive-magic | dada-magic-shield-charm | spell | 112 | 4 |

## Duplicate-risk read

Token Jaccard over material texts. This is a cheap proxy, not a question-stem
check; the authoring ticket still runs the real duplicate check.

- Maximum pairwise similarity: 0.225
- Median pairwise similarity: 0.036
- The highest pairs are same-concept or same-theme materials:
  - `dada-magic-patronus-training` and `dada-protective-patronus-field`: 0.225
  - `dada-countering-detection-and-concealment` and `dada-protective-fidelius-trust`: 0.194
  - `dada-countering-countercurse-doctrine` and `dada-dark-arts-unforgivables-law`: 0.186
  - `dada-dueling-shield-charm` and `dada-protective-wards-at-scale`: 0.158

The material set is not clone-like. The risk is asking the same facet twice on a
shared concept. The intent map below forces the MCQ and the short answer onto
different facets, and the authoring validator rejects duplicate stems.

## Practitioner context

The pack has no standalone practitioner materials, but practitioners are present
in reviewed materials. Practitioner questions can be grounded in those
materials rather than free model memory.

| Practitioner | Materials that mention the name |
|---|---|
| Moody | 6 materials across the dark-arts and countercurse units |
| Lupin | 7 materials across boggarts, the marsh practical, werewolves, duelling and Patronus training |
| Snape | 5 materials across countercurse doctrine, the marsh practical, werewolves, duelling and the Shield Charm |
| Dumbledore | 3 materials across the Imperius demonstration, Unforgivables law and Fidelius |
| Harry | 11 materials across duelling, Patronus, thestrals, the Grim and the final battle |
| Hermione | 5 materials across Cruciatus, Imperius, pixies, the Grim and the Shield Charm |
| Neville | 5 materials across Cruciatus, boggarts, pixies and the Shield Charm |
| Sirius | 2 materials on werewolf law and Fidelius |
| Umbridge | 2 materials on countercurse doctrine and werewolf law |
| Lockhart | 3 materials on pixies, werewolves and the duelling club |
| Hagrid | 1 material on thestrals |
| Flitwick | 1 material on wards at scale |
| McGonagall | no material; no DADA teaching decision to ground |

This is enough for practitioner questions that ask about a teaching decision or
a demonstrated principle. It is not enough for biographical questions about a
practitioner with no material of their own. The blueprint excludes those.

## Event coverage

There are no standalone event concepts in the pack. Events are mentioned inside
materials, for example:

- the D.A. as the training context for boggarts, Patronus work and the Shield Charm;
- the final battle as the field context for the Shield Charm, thestrals and wards at scale;
- the Triwizard maze as the context for the Stunning Spell's limits;
- the third-year practical as the context for the marsh hazards and boggarts.

Event-specific questions are allowed only when the cited material carries the
event fact. A question that needs a separate event chronology is out of scope
for this bank. A future top-up can add event materials if the bank needs them.
The strongest unused event seed is the Triwizard Tournament
(`dada-thing-triwizard-tournament`, definition, 16 refs); it is not a DADA
concept record today. The Battle of Hogwarts and D.A. seeds have zero refs and
need resolver work.

## Gap candidates with book source refs

These are candidates for a later top-up, not approved material. Every row has
at least one book source-ref candidate. A title already named inside a reviewed
material is still a candidate for a dedicated material, but it is not an
uncovered fact.

| Concept id | Candidate | Kind | Refs | Note |
|---|---|---|---:|---|
| `dada-creature-centaur` | Centaurs | creature | 33 | strong future candidate |
| `dada-creature-trolls` | Trolls | creature | 15 | strong future candidate |
| `dada-creature-vampire` | Vampire | creature | 13 | strong future candidate |
| `dada-magic-legilimency` | Legilimency | spell | 12 | supports mental defence |
| `dada-magic-summoning-charm` | Summoning Charm | spell | 12 | optional; not a defensive core |
| `dada-creature-dragon` | Dragons | creature | 9 | strong future candidate |
| `dada-creature-giant` | Giants | creature | 9 | named in the thestral material; no concept record |
| `dada-creature-spiders` | Spiders | creature | 9 | named in the Stunning Spell material; no concept record |
| `dada-creature-hinkypunk` | Hinkypunk | creature | 7 | already inside the marsh material; not a true gap |
| `dada-magic-impediment-curse-jinx` | Impediment Curse | spell | 7 | supports duelling |
| `dada-creature-inferi` | Inferi | creature | 5 | strong future candidate |
| `dada-magic-silencing-charm` | Silencing Charm | spell | 5 | supports concealment and duelling |
| `dada-creature-banshee` | Banshee | creature | 4 | supports the boggart counterexamples |
| `dada-magic-sectumsempra` | Sectumsempra | spell | 4 | dark-arts counterexample; review carefully |
| `dada-creature-basilisk` | Basilisk | creature | 3 | needs a reviewed source-ref pass |

## Needs resolver work

These candidates have no book source-ref candidate yet. They cannot enter a
material without resolver work and normal review.

| Concept id | Candidate | Kind | Refs | Note |
|---|---|---|---:|---|
| `dada-creature-acromantula` | Acromantula | creature | 0 | resolver needed |
| `dada-event-battle-of-hogwarts` | Battle of Hogwarts | event | 0 | resolver needed |
| `dada-thing-dumbledores-army-d-a` | Dumbledore's Army (The D.A.) | definition | 0 | resolver needed |
| `dada-event-harry-takes-his-owls` | Students in Harry's year start their O.W.L.s | event | 0 | exam-format evidence, not a DADA question |

Do not add these to the pack without the normal material review. The first bank
does not depend on them.

## Excluded candidates

The gap scan excludes generic school places and things, other-subject topics and
non-DADA creatures and spells. Examples include the Great Hall, Quidditch,
Muggles, Transfiguration, Divination, Charms, House-elves, Beetles, Frogs and
Toads. The Cornish pixie is the same creature as the reviewed Pixies material;
Hinkypunk is named inside the marsh material. Neither is an unused fact.

## Bank blueprint

### Composition and marks

| Item | Count | Marks each | Marks in paper |
|---|---:|---:|---:|
| MCQ | 25 | 3 | 18 |
| Short answer | 25 | 8 | 32 |
| Bank total | 50 | - | - |

A paper samples 6 MCQ and 4 short answers, for 10 questions and 50 marks.

Band thresholds stay percentage-based:

| Band | Paper score |
|---|---:|
| O | 45-50 |
| E | 40-44 |
| A | 35-39 |
| P | 25-34 |
| D | 15-24 |
| T | 0-14 |

### Topic quotas

The quotas are proportional to reviewed material, not equal per topic. Every
topic gets at least two items per type.

| Topic | MCQ target | Short target | Basis |
|---|---:|---:|---|
| dark-creatures | 10 | 10 | 10 materials |
| defensive-magic | 9 | 9 | 9 materials |
| dark-arts | 4 | 4 | 4 materials |
| dueling | 2 | 2 | 2 materials |
| Total | 25 | 25 | 25 materials |

### Item quotas

| Rule | Limit |
|---|---|
| Items per material | Exactly 1 MCQ and 1 short answer, unless the review records a slot swap |
| Items per concept per type | At most 2; a slot swap needs a recorded reason |
| Items per topic per type | Within 1 of the target table |
| Difficulty mix | 30 percent recall, 50 percent explanation or application, 20 percent comparison or scenario |
| Difficulty rounding | 8 recall, 12 explanation or application, 5 comparison or scenario |
| Correct-option positions in the bank | Key hygiene: no stored index above 40 percent of MCQs; served order is shuffled per attempt |
| Short-answer length | 2-3 sentences, 25-80 words |
| Short-answer required points | 2-3 points, all supported by the cited material |

### Question scope

Every item tests the subject, not the plot. The focus is the spell, creature,
defence, mechanism, limit or comparison: what it does, when it works, what it
cannot do, and what danger it answers. Plot events, character biography and
classroom anecdotes are not examinable on their own. A scene may supply the
evidence for a concept question, but the question must stand without story
knowledge.

### MCQ rules

- Exactly 6 options: 1 correct and 5 plausible distractors from the same DADA family.
- Distractors must be false against the cited evidence, not merely less good.
- No all-of-the-above, none-of-the-above or negative stem unless the review records why.
- The correct option must not be identifiable from length alone.
- The served paper gets 4 options: the correct option plus 3 random distractors, shuffled by the server.
- The client never receives the correct option id or the other two options.
- The independent solver must select the stored key on the evidence.

### Short-answer rules

- Ask for explanation, mechanism, comparison, application or a defensive judgement.
- No yes or no, no one-word answer and no question that only asks for an incantation.
- Golden answer is 2-3 sentences and contains the required points.
- Rubric is 8 marks: 4 for correctness and 4 for completeness, or an item-specific split that still sums to 8.
- The judge compares the student answer with the golden answer and the rubric; it does not require exact wording.
- A concise answer that covers the points is not penalised for brevity.

### Duplicate and review gates

- Exact normalized prompt duplicates: 0.
- Token Jaccard above 0.75 or embedding cosine above 0.90: reject or review.
- Same material and same facet: at most one item per type.
- Same concept and same facet across different materials: also a duplicate; the intent map must assign distinct facets.
- Independent solver on MCQs: 100 percent agreement with the stored key, or the item is fixed.
- Distractor verifier: no second defensible answer.
- Short-answer verifier: the golden answer is complete and supported by the evidence.
- Human review: 100 percent of MCQ keys and short-answer golden answers and rubrics; sampled distractors and evidence.

## Material intent map

Each row is a planned facet, not a finished question. The authoring ticket turns
the facet into a question and options.

| Material | MCQ focus | Short-answer focus |
|---|---|---|
| `dada-countering-countercurse-doctrine` | Which principle matches Moody's countercurse doctrine | Explain the recognition-before-response doctrine and Snape's supporting view |
| `dada-countering-detection-and-concealment` | What makes a Secrecy Sensor useful against Dark objects | Compare a Secrecy Sensor and the Fidelius Charm as concealment approaches |
| `dada-countering-hex-deflection` | Why Moody's hex-deflection lesson caused injuries | Explain why hex-deflection is trained physically, using Moody and the D.A. |
| `dada-dark-arts-cruciatus-evidence` | Which detail shows the Cruciatus demonstration is torture | Explain what Neville's and Hermione's reactions add to the lesson |
| `dada-dark-arts-imperius-demonstration` | How Harry describes the Imperius sensation | Explain how Harry resisted and why the method matters |
| `dada-dark-arts-killing-curse-limits` | What limit Moody stresses about Avada Kedavra | Distinguish knowing the words, casting the curse and being willing to cast it |
| `dada-dark-arts-unforgivables-law` | The legal penalty for using an Unforgivable on a human | Explain why Dumbledore overrode the syllabus and why Moody teaches recognition |
| `dada-dark-creatures-boggarts-counter` | The mental step that makes Riddikulus work | Explain Riddikulus and the required mental image |
| `dada-dark-creatures-boggarts-field` | The common failure when facing a boggart | Explain why a boggart tests recognition, nerve and a clear image |
| `dada-dark-creatures-boggarts-nature` | What is known about a boggart's solitary form | Explain how a boggart chooses a form and what that reveals |
| `dada-dark-creatures-dementors-nature` | What the Dementor's Kiss is | Explain why resisting a dementor is not enough and why the Patronus is separate |
| `dada-dark-creatures-fieldcraft-pixies` | Which spell immobilised the pixies | Explain why Lockhart's lesson failed and what a working counter needs |
| `dada-dark-creatures-fieldcraft-thestrals` | Who can see a thestral | Explain the gap between thestrals' reputation and their danger |
| `dada-dark-creatures-fieldcraft-water-and-marsh` | How a hinkypunk lures travellers | Explain the order of Lupin's practical and what the hazards test |
| `dada-dark-creatures-grim-private-fear` | The counter to a Grim | Explain why the Grim episode warns about private fear |
| `dada-dark-creatures-werewolves-law-and-fear` | What Umbridge's legislation did to Lupin | Explain how defence teaching should hold ordinary werewolves and Greyback together |
| `dada-dark-creatures-werewolves-recognition` | How Snape's werewolf lesson differed from Lockhart's | Explain what the two lessons show about classroom limits |
| `dada-dueling-disarming-charm` | Why Disarming is both a first and a last spell | Explain why Disarming is not weak, using the duelling club and final battle |
| `dada-dueling-shield-charm` | The Shield Charm's ceiling | Explain why Protego cannot stop Avada Kedavra even though it deflects minor jinxes |
| `dada-dueling-stunning-spell` | Why Stupefy failed against the maze spider | Explain why a duellist must match Stupefy to the target |
| `dada-magic-patronus-theory` | What a Patronus is made of | Explain why an indistinct shadow is not a true Patronus |
| `dada-magic-patronus-training` | Why Lupin used a boggart for Patronus training | Explain what the training method teaches about failure and fear |
| `dada-protective-fidelius-trust` | What the Fidelius Charm hides | Explain why Fidelius is a study of trust as much as magic |
| `dada-protective-patronus-field` | What Harry's first field Patronus accomplished | Explain why a classroom Patronus is different from one under threat |
| `dada-protective-wards-at-scale` | What Protego Horribilis at the window shows | Explain the lesson of proportion across classroom, hall and castle |

## Validation gates for the bank tickets

- Every item has a known material id and at least one current book source ref.
- Every MCQ stores at least 6 options with exactly one correct option.
- The independent solver selects the stored key on 100 percent of reviewed MCQs.
- The distractor verifier finds no second defensible answer.
- Every short answer golden answer is 2-3 sentences and 25-80 words.
- Every short-answer rubric sums to 8 marks.
- The duplicate checks pass the thresholds above.
- The topic quotas are within one item of the target.
- The structure-only bank record is committed; no corpus prose is committed.
- The chat and lesson eval gates do not regress.

## Risks

| Risk | Mitigation |
|---|---|
| One material yields two overlapping questions | Intent map forces different facets; duplicate check rejects the overlap |
| A distractor is arguably correct | Independent distractor verifier plus human review |
| A short-answer rubric is too vague to mark | Required points and 4 plus 4 rubric template |
| Dueling is underrepresented at 8 percent | It still gets 2 MCQ and 2 short answers, enough for the scope |
| Event coverage is thin | Event questions only where the material carries the event; top-up later |
| 25 materials cannot support 25 distinct shorts | Stop after three failed slots and open a reviewed top-up |

## Out of scope

- Generating questions or options in this ticket.
- Expanding the pack without a reviewed top-up.
- Charms and the other subjects.
- Long-answer questions.
- Auth, attempt storage and serving.

## Reproduce

```text
uv run python scripts/bank_coverage.py --subject dada
```

The command reads the published pack and the local seed queue. It prints counts,
ids, titles and word counts only; material prose and book text stay in `/data`.

## Refs

#188, #187, #189, #190, #191, #192, #193, #178, #87, #128.
