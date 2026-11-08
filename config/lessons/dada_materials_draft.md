# DADA materials list - draft for maintainer review

Titles are the examinable units of Ashcombe's Defense Against the Dark Arts
pack. Each unit becomes a reviewed Material citing verified book source refs.
Counts are from the #128 seed build (1,402 DADA concept drafts, 684 with
hash-verified evidence). Every chapter cited below is an approved row in
config/lessons/dada.jsonl; a final section lists strong candidates that are
not yet in the table for a maintainer decision.

| # | Title | One-line scope | Anchors (verified seeds) | Approved chapters cited |
|---|---|---|---|---|
| 1 | Boggarts and the Banishing Spell | Recognizing a boggart, Riddikulus mechanics, classroom protocol | Boggart, Boggart Banishing Spell | b3 c07 (Lupin, taught) |
| 2 | Dementors and the Patronus Charm | Dementor behaviour, the Patronus precondition, why fifth years only theorise it | Dementors, Patronus Charm, Corporeal Patronus | b3 c10, c12 (taught; verified chunks b3-c10-0016, b3-c12-0025), b5 c18 (taught, D.A. year) |
| 3 | Dark-Creature Fieldcraft | Lake and corridor hazards, thestrals, pixie-and-basilisk classroom failures; Ministry classification | Grindylow, Pixies, Thestrals, Murtlap, Basilisk | b3 c16 (exam), b2 c10 (taught), b5 c21, c28 (taught) |
| 4 | Werewolves: Lore, Restraint and Prejudice | Wolfsbane, the Grim, containment, and how the wizarding world treats werewolves | Werewolves, Grim | b3 c09 (taught, Snape note), b3 c12 (taught), b2 c10 (werewolf-boggart class) |
| 5 | The Unforgivable Curses | Legal status, documented effects, defense doctrine; the debate over school demonstration | Imperius Curse, Killing Curse, Cruciatus Curse | b4 c14-c15 (taught; demonstration chunks b4-c15-0008/0009, Crucio b4-c14-0020), b6 c15 (author-pick, Unbreakable Vow) |
| 6 | Dueling Discipline: Shielding and Disarming | Disarming, Stunning, shielding, footwork - the practical core the D.A. supplied | Disarming Charm, Stunning Spell, Shield Charm | b5 c18 (taught; Disarming b5-c18-0081, Protego b5-c26-0094), b4 c31, c34 (author-pick dueling), b2 c11-c13 (counter-example) |
| 7 | Countering Curses, Detection and Concealment | Hex and curse recognition, counter-enchantment, detecting concealed creatures | Anti-Curses, Hexes, Curses | b4 c14, c20, c22, c28 (Moody-year defense, taught) |
| 8 | Protective Magic Under Pressure | Personal and household defence, secrecy, anti-tracking in wartime | Shield Charm, Patronus | b5 c27, c30, c33 (author-pick), b7 c29, c30, c32, c36 (author-pick; shielding b7-c32-0001) |

Candidate chapters NOT yet in the approved table (add via a follow-up draft
run or manual rows; content notes only where a quote verified it this session):

- b2 c04 - "The Cornish Pixies" lesson
- b3 c08, b3 c13-c15 - Lupin-year classroom chapters the cue extractor missed
- b4 c10, b4 c13 - Mad-Eye's early lessons
- b5 c31 - the O.W.L. papers chapter: the DADA practical exam itself (boggart
  at bay, concealed creature, jinx reversal) - the single strongest missing
  row for Unit 7
- b7 c06-c08, b7 c12 - wartime chapters (Seven Potters era and aftermath)
- b6 c17-c18 - hex-adjacent chapters beyond the already-approved b6 c19

Strike candidates found by this audit (the approved-row feedback loop, first
exercise):

- b6 c09 - cue quotes are DADA-classroom *passing mentions*; the chapter's
  verified seeds are Potions content (Felix Felicis, Amortentia). Recommend
  striking from dada; likely a Potions-table row.
- b5 c26 - cue quotes are Umbridge detention talk; classroom-adjacent, keep
  only if the Umbridge-theory framing is wanted for Unit 6's counter-example.
- b6 rows labelled da-army (c07, c15, c19...) - the D.A. does not meet in
  book 6; these are author-pick on cue noise. Re-basis them or strike before
  the table is used for materials.

Alternatives considered and their evidence status:

- Mind arts (Legilimency/Occlumency): strong b6 anchors, but private
  Newt-level tuition in the books, not a classroom OWL unit; deferred, or
  folded into Unit 5's defense doctrine.
- Quirrell-era standalone unit (b1, 53 verified concepts): the books present
  his teaching as failure; the chapters stay in the table for coverage, no
  standalone unit. The troll incident supports Unit 3.

Maintainer action: keep/rename/merge the eight titles, rule on the gap
chapters, then each unit is authored as a Material draft prefilled with its
seeded source refs.
