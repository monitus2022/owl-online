# DADA materials list - authored status

Titles are the examinable units of Ashcombe's Defense Against the Dark Arts
pack. Each unit becomes a reviewed Material citing verified book source refs.
Counts are from the #128 seed build (1,402 DADA concept drafts, 684 with
hash-verified evidence). Every chapter cited below is an approved row in
config/lessons/dada.jsonl.

## Authoring status (2026-11-08)

Pack 0.3.0 in `data/subjects/dada/` now holds Units 1-8 as three materials
each (Unit 5 has four): 25 materials, 21 concepts, 4 topics. All validate
`ok=True`; the only warnings are `review_status=draft`, which the maintainer
clears by prose review. The full review sheets are `UNIT1_REVIEW.md` and
`UNITS_REVIEW.md` in the pack directory (gitignored, included in the data
backup).

| Unit | Materials | Concepts |
|---|---|---|
| 1 | 3 (nature / counter / field) | Boggart, Boggart Banishing Spell |
| 2 | 3 (nature / theory / training) | Dementors, Patronus, Corporeal Patronus |
| 3 | 3 (pixies / water and marsh / thestrals) | Pixie, Grindylow, Thestral |
| 4 | 3 (recognition / law and fear / the Grim) | Werewolf, Grim |
| 5 | 4 (law / Imperius / Cruciatus / Killing Curse) | Unforgivable Curses, Imperius, Cruciatus, Killing Curse |
| 6 | 3 (Disarming / Stunning / Shield) | Disarming Charm, Stunning Spell, Shield Charm |
| 7 | 3 (doctrine / hex-deflection / detection) | Countercurse, Hex-Deflection, Concealment Charm |
| 8 | 3 (Fidelius / wards / Patronus in the field) | Fidelius Charm, Shield Charm, Patronus |

Corrections made during the evidence pass (no claim without eyes on the
chunk):

- Unit 3's pixie lesson is `b2 c06`, not `b2 c10`; `b2 c10` is Lockhart's
  werewolf theatre and belongs to Unit 4.
- Unit 4 covers recognition, law and fear. Restraint needs `b3 c18`
  (Wolfsbane, full moon) and `b5 c22` (the bite has no cure); neither is an
  approved row, so no containment claim is made.
- Unit 5 does not use `b6 c15` for the Unbreakable Vow: the explanation is in
  `b6 c02`, which is not an approved row.
- The `b6 c09` strike candidate is overturned: `b6-c09-0029` is Snape's
  defence doctrine and `b6-c09-0036` is a Shield Charm, both DADA.
- The b6 rows' shared reason ("Dumbledore's Army practical chapters") is
  wrong for book 6 and should be relabelled when the table is next touched.

The original proposal follows for the audit trail.

## Original proposal

| # | Title | One-line scope | Anchors (verified seeds) | Approved chapters cited |
|---|---|---|---|---|
| 1 | Boggarts and the Banishing Spell | Recognizing a boggart, Riddikulus mechanics, classroom protocol | Boggart, Boggart Banishing Spell | b3 c07 (Lupin, taught) |
| 2 | Dementors and the Patronus Charm | Dementor behaviour, the Patronus precondition, why fifth years only theorise it | Dementors, Patronus Charm, Corporeal Patronus | b3 c10, c12 (taught; verified chunks b3-c10-0016, b3-c12-0025), b5 c18, c27 (D.A. year) |
| 3 | Dark-Creature Fieldcraft | Lake and corridor hazards, thestrals, pixie-and-basilisk classroom failures; Ministry classification | Grindylow, Pixies, Thestrals, Murtlap, Basilisk | b3 c09, c16 (taught), b2 c06 (pixie lesson), b5 c21 (thestrals) |
| 4 | Werewolves: Recognition, Law and Fear | Recognition, anti-werewolf law, the Greyback exception; containment needs a gap row | Werewolves, Grim | b3 c09 (taught), b2 c10 (Lockhart theatre), b5 c14, b6 c27 |
| 5 | The Unforgivable Curses | Legal status, documented effects, defense doctrine; the debate over school demonstration | Imperius Curse, Killing Curse, Cruciatus Curse | b4 c14-c15 (taught; demonstration chunks b4-c15-0008/0009, Crucio b4-c14-0020) |
| 6 | Dueling Discipline: Shielding and Disarming | Disarming, Stunning, shielding, footwork - the practical core the D.A. supplied | Disarming Charm, Stunning Spell, Shield Charm | b5 c18 (taught; Disarming b5-c18-0081, Protego b5-c26-0094), b4 c31, c34, b2 c11-c13 (dueling club), b7 c05, c32, c36 |
| 7 | Countering Curses, Detection and Concealment | Hex and curse recognition, counter-enchantment, detecting concealed creatures | Anti-Curses, Hexes, Curses | b4 c14, c20, c28 (Moody-year defense, taught), b6 c09 (Snape doctrine), b5 c12 (Umbridge theory) |
| 8 | Protective Magic Under Pressure | Personal and household defence, secrecy, anti-tracking in wartime | Shield Charm, Patronus, Fidelius Charm | b3 c10 (Fidelius), b7 c06, c30, c36 (author-pick; wards and battle) |

Candidate chapters NOT yet in the approved table (add via a follow-up draft
run or manual rows; content notes only where a quote verified it this session):

- b2 c04 - not the pixie lesson: the Cornish pixies are in b2 c06, which is
  already approved. Strike this candidate.
- b3 c08, b3 c13-c15 - Lupin-year classroom chapters the cue extractor missed
- b3 c18 - Lupin explains Wolfsbane and the full moon; the missing restraint
  row for Unit 4
- b4 c10, b4 c13 - Mad-Eye's early lessons
- b5 c22 - the St Mungo's ward: a werewolf bite has no cure; the other missing
  restraint row for Unit 4
- b5 c31 - the O.W.L. papers chapter: the DADA practical exam itself (boggart
  at bay, concealed creature, jinx reversal) - the single strongest missing
  row for Unit 7
- b6 c02 - the Unbreakable Vow is explained here, not in the approved b6 c15
- b6 c16 - Lupin on Fenrir Greyback; Unit 4 used b6 c27 instead
- b7 c06-c08, b7 c12 - wartime chapters (Seven Potters era and aftermath)
- b6 c17-c18 - hex-adjacent chapters beyond the already-approved b6 c19

Strike and relabel outcomes from the authoring pass:

- b6 c09 - strike overturned. The chapter is a DADA lesson: `b6-c09-0029`
  is Snape's "as flexible and inventive as the arts you seek to undo" and
  `b6-c09-0036` is a Shield Charm. Keep as taught-in-class.
- b5 c26 - kept but not used by the materials; the Umbridge theory argument
  is carried by b5 c12 instead. Strike or keep on maintainer preference.
- b6 rows labelled da-army (c07, c15, c19...) - the label is confirmed
  wrong; the D.A. does not meet in book 6. Re-basis them as author-pick or
  strike before the next authoring pass. The materials cite b6 c15 and b6
  c27, both approved rows.

Alternatives considered and their evidence status:

- Mind arts (Legilimency/Occlumency): strong b6 anchors, but private
  Newt-level tuition in the books, not a classroom OWL unit; deferred, or
  folded into Unit 5's defense doctrine.
- Quirrell-era standalone unit (b1, 53 verified concepts): the books present
  his teaching as failure; the chapters stay in the table for coverage, no
  standalone unit. The troll incident supports Unit 3.

Maintainer action: review the prose in `UNITS_REVIEW.md`, rule on the gap
rows (b3 c18 and b5 c22 unlock Unit 4's containment material; b5 c31
unlocks Unit 7's exam practical; b6 c02 unlocks the Unbreakable Vow), then
flip the materials to `reviewed` and publish the pack.
