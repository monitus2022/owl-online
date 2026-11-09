"""Author the Charms exam bank on the published Charms 1.0.0 pack (#213).

The bank prose lives here rather than in the pack: each item cites one reviewed
material, reuses that material's books-bucket source refs, and is validated by
`app.exam.bank.validate_bank` against the current corpus index hash. Evidence
quotes are never invented; they come from the pack's hash-checked refs.

    uv run python scripts/author_charms_bank.py                    # draft rebuild
    uv run python scripts/author_charms_bank.py --mark-reviewed    # record approval
    uv run python scripts/author_charms_bank.py --publish          # publish reviewed
    uv run python scripts/author_charms_bank.py --mark-reviewed --publish --force
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.exam.bank import (  # noqa: E402
    BankItem,
    BankManifest,
    EvidenceSnapshot,
    ExamBank,
    McqOption,
    RubricCriterion,
    validate_bank,
    write_exam_bank,
)
from app.knowledge.packs import load_subject_pack, pack_fingerprint  # noqa: E402
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402

SUBJECT = "charms"
DRAFT_VERSION = "0.1.0"
PUBLISH_VERSION = "1.0.0"
OUT = REPO / "data" / "exams" / SUBJECT
PROMPT_VERSION = "charms-bank-v1"
GENERATOR_MODEL = "deepseek/deepseek-v4.1-flash"
JUDGE_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
JUDGE_PROMPT_VERSION = "dada-bank-judge-v2"

ITEMS: list[dict] = [
    # foundations
    {
        "item_id": "charms-mcq-001",
        "kind": "mcq",
        "material_id": "charms-foundation-charm-definition",
        "prompt": "Which description best defines a charm?",
        "difficulty": "recall",
        "options": [
            "It permanently changes what an object is.",
            "It gives an object or creature a new action or quality without changing what it is.",
            "It removes a creature's memory of a recent event.",
            "It protects the caster from all physical harm.",
            "It creates a copy of an object from nothing.",
            "It forces a creature to obey the caster's spoken commands.",
        ],
        "correct": 1,
        "rationale": "The material defines a charm as adding behaviour or quality, not replacing identity.",
    },
    {
        "item_id": "charms-mcq-002",
        "kind": "mcq",
        "material_id": "charms-foundation-charm-vs-transfiguration",
        "prompt": "Which statement best distinguishes Charms from Transfiguration?",
        "difficulty": "comparison",
        "options": [
            "Charms changes what a thing is; Transfiguration changes what it does.",
            "Charms changes what a thing does; Transfiguration changes what it is.",
            "Charms is practical; Transfiguration is only written theory.",
            "Charms needs no wand; Transfiguration needs a wand.",
            "Charms works only on creatures; Transfiguration works only on objects.",
            "Charms is examined at OWL level; Transfiguration is not examined.",
        ],
        "correct": 1,
        "rationale": "The subject boundary is behaviour versus identity, not practical versus theoretical.",
    },
    {
        "item_id": "charms-mcq-003",
        "kind": "mcq",
        "material_id": "charms-foundation-incantation",
        "prompt": "Why does Hermione correct Ron's pronunciation of Wingardium Leviosa?",
        "difficulty": "explanation",
        "options": [
            "The spell only works if the wizard holds the wand in the left hand.",
            "The 'gar' must be long and the syllables precise for the charm to work.",
            "The spell must be whispered so the feather does not hear it.",
            "The spell requires the caster to say it twice in a row.",
            "The spell only works on feathers that have already been charmed.",
            "The caster must shout the final syllable as loudly as possible.",
        ],
        "correct": 1,
        "rationale": "Exact wording and emphasis are treated as part of charm technique.",
    },
    {
        "item_id": "charms-mcq-004",
        "kind": "mcq",
        "material_id": "charms-foundation-wand-movement",
        "prompt": "What wand movement does Flitwick drill before the class attempts the Levitation Charm?",
        "difficulty": "recall",
        "options": [
            "A slow circle over the target.",
            "A sharp downward stab.",
            "A swish and flick.",
            "A figure of eight.",
            "A single tap on the target.",
            "A backward wave over the shoulder.",
        ],
        "correct": 2,
        "rationale": "The swish-and-flick wrist movement is drilled before the first attempt.",
    },
    {
        "item_id": "charms-mcq-005",
        "kind": "mcq",
        "material_id": "charms-finite-incantatem",
        "prompt": "What does Finite Incantatem do?",
        "difficulty": "explanation",
        "options": [
            "It reverses one specific charm and nothing else.",
            "It ends active spells and cancels ongoing magic.",
            "It creates a shield that blocks new spells.",
            "It restores an object to its original shape.",
            "It removes a curse from a person permanently.",
            "It silences every spell in the room.",
        ],
        "correct": 1,
        "rationale": "It is a general counter-spell that cancels ongoing magic, not a narrow reversal.",
    },
    # movement
    {
        "item_id": "charms-mcq-006",
        "kind": "mcq",
        "material_id": "charms-levitation-theory",
        "prompt": "Which result shows Hermione's Wingardium Leviosa working correctly in the first lesson?",
        "difficulty": "recall",
        "options": [
            "The feather turns into a small bird.",
            "The feather rises four feet above the desk.",
            "The feather catches fire and burns away.",
            "The feather tap-dances across the desk.",
            "The feather swells to the size of a badger.",
            "The feather splits into two identical feathers.",
        ],
        "correct": 1,
        "rationale": "The material records the feather lifting four feet above the desk.",
    },
    {
        "item_id": "charms-mcq-007",
        "kind": "mcq",
        "material_id": "charms-banishing",
        "prompt": "Why does Flitwick give the class a stack of cushions for the Banishing Charm?",
        "difficulty": "explanation",
        "options": [
            "The cushions are the only objects the charm works on.",
            "A miss can send heavy objects flying, so cushions make practice safer.",
            "The cushions are used to muffle the sound of the incantation.",
            "The charm turns cushions into birds when it succeeds.",
            "The cushions mark the boundary of the practice area.",
            "The cushions are needed to wipe the wands between attempts.",
        ],
        "correct": 1,
        "rationale": "The cushion stack exists because a missed Banishing Charm has consequences.",
    },
    {
        "item_id": "charms-mcq-008",
        "kind": "mcq",
        "material_id": "charms-summoning",
        "prompt": "What does the Summoning Charm do?",
        "difficulty": "recall",
        "options": [
            "It sends an object away from the caster.",
            "It calls an object to the caster.",
            "It makes an object hover in place indefinitely.",
            "It changes an object into a different material.",
            "It locks an object so it cannot be moved.",
            "It makes an object invisible to others.",
        ],
        "correct": 1,
        "rationale": "The Summoning Charm calls an object to the caster; Banishing sends it away.",
    },
    {
        "item_id": "charms-mcq-009",
        "kind": "mcq",
        "material_id": "charms-locomotor",
        "prompt": "What is the effect of Locomotor when cast on a trunk?",
        "difficulty": "application",
        "options": [
            "It shrinks the trunk to fit in a pocket.",
            "It moves the trunk through the air under the caster's direction.",
            "It locks the trunk so only the caster can open it.",
            "It turns the trunk into a bed.",
            "It summons the trunk from another room.",
            "It makes the trunk invisible for an hour.",
        ],
        "correct": 1,
        "rationale": "Locomotor directs an object through the air rather than summoning or banishing it.",
    },
    {
        "item_id": "charms-mcq-010",
        "kind": "mcq",
        "material_id": "charms-unlocking",
        "prompt": "What does the failure of Alohomora on the third-floor door show about the spell?",
        "difficulty": "explanation",
        "options": [
            "It only works on doors made of wood.",
            "It is real but not universal, because some locks resist it.",
            "It works only when the caster knows the password.",
            "It opens any door once per day.",
            "It must be cast by two wizards together.",
            "It only works on doors that are already unlocked.",
        ],
        "correct": 1,
        "rationale": "The scene presents Alohomora as a practical tool with limits.",
    },
    # elements
    {
        "item_id": "charms-mcq-011",
        "kind": "mcq",
        "material_id": "charms-lumos",
        "prompt": "Which pair correctly matches a charm to its effect?",
        "difficulty": "recall",
        "options": [
            "Lumos extinguishes wandlight; Nox produces light.",
            "Lumos produces light at the wand tip; Nox extinguishes it.",
            "Lumos summons a light source; Nox banishes it.",
            "Lumos creates fire; Nox creates water.",
            "Lumos makes the wand invisible; Nox makes it glow.",
            "Lumos amplifies the voice; Nox silences it.",
        ],
        "correct": 1,
        "rationale": "Lumos and Nox are a matched pair: light on, light off.",
    },
    {
        "item_id": "charms-mcq-012",
        "kind": "mcq",
        "material_id": "charms-aguamenti",
        "prompt": "What does Aguamenti produce?",
        "difficulty": "recall",
        "options": [
            "A jet of water from the wand.",
            "A jet of fire from the wand.",
            "A cloud of smoke around the caster.",
            "A shield of invisible air.",
            "A stream of small birds.",
            "A fountain of wine.",
        ],
        "correct": 0,
        "rationale": "Aguamenti creates water at the wand tip and directs it at a target.",
    },
    {
        "item_id": "charms-mcq-013",
        "kind": "mcq",
        "material_id": "charms-incendio",
        "prompt": "What is the immediate effect of Incendio?",
        "difficulty": "recall",
        "options": [
            "It produces fire.",
            "It produces water.",
            "It extinguishes existing fire.",
            "It turns an object to stone.",
            "It creates a bubble of air.",
            "It silences nearby sound.",
        ],
        "correct": 0,
        "rationale": "Incendio is controlled fire production, dangerous in an enclosed space.",
    },
    {
        "item_id": "charms-mcq-014",
        "kind": "mcq",
        "material_id": "charms-bubble-head",
        "prompt": "What does the Bubble-Head Charm do?",
        "difficulty": "recall",
        "options": [
            "It creates a bubble of breathable air around the caster's head.",
            "It surrounds the caster in a shield that blocks spells.",
            "It fills the caster's ears with buzzing.",
            "It makes the caster's head invisible.",
            "It turns the caster's head into an animal's head.",
            "It amplifies the caster's voice.",
        ],
        "correct": 0,
        "rationale": "The charm solves an environmental problem without changing the body.",
    },
    {
        "item_id": "charms-mcq-015",
        "kind": "mcq",
        "material_id": "charms-drought",
        "prompt": "Why can the Drought Charm not solve the problem of breathing underwater in the lake?",
        "difficulty": "application",
        "options": [
            "It only works on salt water.",
            "It dries puddles and ponds but cannot drain a body of water as large as the lake.",
            "It only works on living plants.",
            "It requires the caster to stand on dry land.",
            "It creates water instead of removing it.",
            "It can only be cast once in a lifetime.",
        ],
        "correct": 1,
        "rationale": "The material states the limit as the volume of water the charm can affect.",
    },
    # sound
    {
        "item_id": "charms-mcq-016",
        "kind": "mcq",
        "material_id": "charms-silencio",
        "prompt": "What does Silencio do to a target?",
        "difficulty": "recall",
        "options": [
            "It stops the target from moving.",
            "It suppresses the target's voice while leaving movement possible.",
            "It makes the target's legs dance.",
            "It fills the target's ears with buzzing.",
            "It amplifies the target's voice.",
            "It makes the target tell the truth.",
        ],
        "correct": 1,
        "rationale": "Silencio suppresses sound precisely; it is not a general paralysis.",
    },
    {
        "item_id": "charms-mcq-017",
        "kind": "mcq",
        "material_id": "charms-sonorus",
        "prompt": "What does Sonorus do?",
        "difficulty": "recall",
        "options": [
            "It silences the caster.",
            "It amplifies the caster's voice.",
            "It lets the caster hear distant conversations.",
            "It changes the caster's voice to another person's.",
            "It fills nearby ears with buzzing.",
            "It makes the caster's voice impossible to record.",
        ],
        "correct": 1,
        "rationale": "Sonorus makes the voice carry without creating speech.",
    },
    {
        "item_id": "charms-mcq-018",
        "kind": "mcq",
        "material_id": "charms-muffliato",
        "prompt": "How does Muffliato protect a private conversation?",
        "difficulty": "explanation",
        "options": [
            "It silences the speaker so no one can hear.",
            "It fills nearby listeners' ears with buzzing while the caster can still talk.",
            "It makes the speakers invisible to everyone nearby.",
            "It creates a wall of sound around the speakers.",
            "It changes the speakers' voices beyond recognition.",
            "It removes the memory of the conversation from listeners.",
        ],
        "correct": 1,
        "rationale": "Muffliato affects the listeners, not the speaker.",
    },
    # jinxes
    {
        "item_id": "charms-mcq-019",
        "kind": "mcq",
        "material_id": "charms-full-body-bind",
        "prompt": "What does Petrificus Totalus do?",
        "difficulty": "recall",
        "options": [
            "It knocks the target unconscious.",
            "It locks the target's limbs and body without knocking them out.",
            "It forces the target's legs into a dance.",
            "It enlarges the target's front teeth.",
            "It covers the target in boils.",
            "It hoists the target into the air by the ankle.",
        ],
        "correct": 1,
        "rationale": "The Full Body-Bind is a restraint, not a blast or a knockout.",
    },
    {
        "item_id": "charms-mcq-020",
        "kind": "mcq",
        "material_id": "charms-jelly-legs",
        "prompt": "What is the effect of the Jelly-Legs Jinx?",
        "difficulty": "recall",
        "options": [
            "The target's legs wobble uncontrollably.",
            "The target's legs lock together.",
            "The target's legs dance a frantic quickstep.",
            "The target's legs swell to twice their size.",
            "The target's legs turn to jelly and dissolve.",
            "The target's legs become invisible.",
        ],
        "correct": 0,
        "rationale": "The jinx disrupts movement without lasting injury and has a counter-jinx.",
    },
    {
        "item_id": "charms-mcq-021",
        "kind": "mcq",
        "material_id": "charms-levicorpus",
        "prompt": "What does Levicorpus do?",
        "difficulty": "recall",
        "options": [
            "It hoists a person into the air by the ankle.",
            "It throws a person backwards across the room.",
            "It locks a person's arms to their sides.",
            "It makes a person's teeth grow rapidly.",
            "It forces a person to speak only in rhymes.",
            "It makes a person's legs wobble.",
        ],
        "correct": 0,
        "rationale": "Levicorpus is the ankle-hoisting jinx, marked non-verbal in the notes.",
    },
    {
        "item_id": "charms-mcq-022",
        "kind": "mcq",
        "material_id": "charms-impediment",
        "prompt": "How does the Impediment Curse help against an attacker?",
        "difficulty": "application",
        "options": [
            "It stops the attacker completely.",
            "It slows the attacker and disrupts their momentum.",
            "It knocks the attacker unconscious.",
            "It turns the attacker's legs to jelly.",
            "It disarms the attacker.",
            "It makes the attacker unable to speak.",
        ],
        "correct": 1,
        "rationale": "The curse buys time by slowing and disrupting rather than binding.",
    },
    # utility
    {
        "item_id": "charms-mcq-023",
        "kind": "mcq",
        "material_id": "charms-reparo",
        "prompt": "What does Reparo do?",
        "difficulty": "recall",
        "options": [
            "It cleans a dirty surface.",
            "It mends a broken object by rejoining its pieces.",
            "It cuts an object along a line.",
            "It repels water from a surface.",
            "It lifts an object and holds it in the air.",
            "It makes a broken object disappear.",
        ],
        "correct": 1,
        "rationale": "Reparo reverses a break rather than hiding it.",
    },
    {
        "item_id": "charms-mcq-024",
        "kind": "mcq",
        "material_id": "charms-diffindo",
        "prompt": "What kind of effect does Diffindo have?",
        "difficulty": "recall",
        "options": [
            "It mends a broken object.",
            "It cuts or splits an object along a line.",
            "It repels water from a surface.",
            "It lifts an object into the air.",
            "It cleans dirt from a surface.",
            "It makes an object grow larger.",
        ],
        "correct": 1,
        "rationale": "Diffindo separates material precisely rather than blasting it apart.",
    },
    # practice
    {
        "item_id": "charms-mcq-025",
        "kind": "mcq",
        "material_id": "charms-anti-cheating",
        "prompt": "What is the Anti-Cheating Spell used for?",
        "difficulty": "recall",
        "options": [
            "It stops students from entering the exam hall.",
            "It is cast on exam papers and quills to stop candidates cheating.",
            "It erases a candidate's memory after the exam.",
            "It times the written paper automatically.",
            "It marks the answers without an examiner.",
            "It prevents candidates from speaking during the exam.",
        ],
        "correct": 1,
        "rationale": "The spell is an institutional security measure on papers and quills.",
    },
    # foundations, short answer
    {
        "item_id": "charms-short-001",
        "kind": "short_answer",
        "material_id": "charms-foundation-concentration",
        "prompt": "Explain why concentration is treated as part of charm technique, and what the vinegar-to-wine lesson shows about it.",
        "difficulty": "explanation",
        "model_answer": "Concentration is the inward half of charm work, coordinating the incantation and the wand movement. In the vinegar-to-wine lesson Harry and Ron raise their wands and concentrate with all their might, but Harry's vinegar turns to ice and Ron's flask explodes. The result shows that reciting a word loudly is not the same as holding the spell clearly in mind.",
        "required_points": ["concentration", "vinegar"],
        "rubric": [
            ("correctness", "Explains concentration as the coordinating intention behind word and movement.", 4),
            ("completeness", "Uses the vinegar-to-wine outcome to show that intention alone is not enough.", 4),
        ],
    },
    {
        "item_id": "charms-short-002",
        "kind": "short_answer",
        "material_id": "charms-foundation-practice",
        "prompt": "Explain why the school treats repetition as part of learning a charm, using two examples from the books.",
        "difficulty": "explanation",
        "model_answer": "Charms is learned by repetition, and the school treats practice as the route to control. Flitwick puts the class in pairs to practise the Levitation Charm, and after Ron's flask explodes he sends the boys away with the single word practice. McGonagall tells the OWL year that no one passes without serious application and practice.",
        "required_points": ["repetition", "practice"],
        "rubric": [
            ("correctness", "States that control comes from repeated practice, not a single success.", 4),
            ("completeness", "Gives two book examples of enforced or expected practice.", 4),
        ],
    },
    # movement, short answer
    {
        "item_id": "charms-short-003",
        "kind": "short_answer",
        "material_id": "charms-levitation-practice",
        "prompt": "Explain what the Levitation Charm lesson shows about why charm failure is usually a problem of technique.",
        "difficulty": "explanation",
        "model_answer": "In the Levitation Charm lesson Harry and Seamus swish and flick, but the feather stays on the desk and Seamus sets it alight by prodding it. Ron shouts the incantation and waves his arms like a windmill, and Hermione tells him he is saying it wrong. The scene shows that failure comes from the movement, the wording or the emphasis rather than from a lack of power.",
        "required_points": ["feather", "windmill"],
        "rubric": [
            ("correctness", "Identifies technique, not raw power, as the cause of the failures.", 4),
            ("completeness", "Uses both the feather and Ron's mistake as evidence.", 4),
        ],
    },
    {
        "item_id": "charms-short-004",
        "kind": "short_answer",
        "material_id": "charms-growth",
        "prompt": "Describe the Growth Charm and explain what Harry's mistake in the Charms practical shows about it.",
        "difficulty": "application",
        "model_answer": "The Growth Charm makes an object or creature larger, and it has its own incantation. In the Charms practical Harry is supposed to turn a rat orange but mixes up Color-Change and Growth, so the rat swells to the size of a badger. The mistake shows that Growth is a distinct charm, not a generic intention to make something bigger.",
        "required_points": ["larger", "badger"],
        "rubric": [
            ("correctness", "States the effect of the Growth Charm and that it has its own incantation.", 4),
            ("completeness", "Explains the mix-up with Color-Change and the resulting oversized rat.", 4),
        ],
    },
    # elements, short answer
    {
        "item_id": "charms-short-005",
        "kind": "short_answer",
        "material_id": "charms-nox",
        "prompt": "Explain what Nox does and why it is described as the counterpart of Lumos.",
        "difficulty": "explanation",
        "model_answer": "Nox extinguishes wandlight, ending the illumination created by Lumos. Harry and Hermione whisper it together on a dark landing, and the lights at the ends of their wands go out. It is the counterpart of Lumos because it removes a previous charm precisely without creating a new object or force.",
        "required_points": ["extinguishes", "lumos"],
        "rubric": [
            ("correctness", "States that Nox ends wandlight and names its relation to Lumos.", 4),
            ("completeness", "Explains that it removes an earlier effect without creating anything new.", 4),
        ],
    },
    {
        "item_id": "charms-short-006",
        "kind": "short_answer",
        "material_id": "charms-bird-conjuring",
        "prompt": "Describe the Bird-Conjuring Charm and explain what Ollivander's demonstration shows about testing a wand.",
        "difficulty": "explanation",
        "model_answer": "Avis, the Bird-Conjuring Charm, produces a flock of small birds from the wand. Ollivander casts it with Krum's hornbeam wand, and the birds fly out of the end and through the window with a blast like a gun. The demonstration shows that a wand test is functional, because the charm proves the wand is responding.",
        "required_points": ["flock", "hornbeam"],
        "rubric": [
            ("correctness", "Names the charm and describes the flock of birds.", 4),
            ("completeness", "Explains that the visible effect is used as a functional wand test.", 4),
        ],
    },
    {
        "item_id": "charms-short-007",
        "kind": "short_answer",
        "material_id": "charms-bluebell-flames",
        "prompt": "Describe Bluebell Flames and explain how Hermione uses them in the third-floor corridor.",
        "difficulty": "application",
        "model_answer": "Bluebell Flames are a charm-produced fire that gives light and warmth without needing wood. Hermione casts them on the Devil's Snare in the third-floor corridor, and the plant recoils from the light and heat. The scene shows the charm used as a quick tool in a crisis rather than as a weapon.",
        "required_points": ["bluebell", "snare"],
        "rubric": [
            ("correctness", "Describes the flames as charm-produced light and heat.", 4),
            ("completeness", "Explains the use against the Devil's Snare and the plant's reaction.", 4),
        ],
    },
    {
        "item_id": "charms-short-008",
        "kind": "short_answer",
        "material_id": "charms-fountain-of-wine",
        "prompt": "Describe the Fountain of Wine and explain what its use in the wand-weighing ceremony shows.",
        "difficulty": "explanation",
        "model_answer": "The Fountain of Wine is a conjuring charm that produces a controlled stream of liquid from the wand tip. Ollivander makes a fountain of wine shoot out of Harry's wand before pronouncing it in perfect condition. The display shows that charm work can be used for demonstration and verification, not only for combat or household tasks.",
        "required_points": ["fountain", "verification"],
        "rubric": [
            ("correctness", "Describes a controlled production of liquid from the wand.", 4),
            ("completeness", "Explains the ceremonial use as a demonstration of wand condition.", 4),
        ],
    },
    {
        "item_id": "charms-short-009",
        "kind": "short_answer",
        "material_id": "charms-orchideous",
        "prompt": "Describe Orchideous and explain what its use during the wand-weighing shows about charm work.",
        "difficulty": "explanation",
        "model_answer": "Orchideous produces a bunch of flowers from the wand tip. Ollivander uses it while checking Fleur's wand, and the flowers burst out before he hands the wand back. The charm is a simple conjuration, and its use in the ceremony shows that a small harmless effect can prove a wand is working.",
        "required_points": ["flowers", "conjuration"],
        "rubric": [
            ("correctness", "Describes the bunch of flowers produced from the wand.", 4),
            ("completeness", "Explains the demonstration as a simple functional test.", 4),
        ],
    },
    # sound, short answer
    {
        "item_id": "charms-short-010",
        "kind": "short_answer",
        "material_id": "charms-cheering",
        "prompt": "Explain what the Cheering Charm does and what the third-year exam shows about controlling it.",
        "difficulty": "explanation",
        "model_answer": "The Cheering Charm lifts a person's mood, and the third-years come out of Flitwick's lesson grinning broadly after practising it. In the third-year exam Harry overdoes it and Ron ends up in fits of hysterical laughter. The charm works on feelings rather than producing a physical effect, so the caster must judge how much to apply.",
        "required_points": ["mood", "laughter"],
        "rubric": [
            ("correctness", "States that the charm affects mood rather than the body.", 4),
            ("completeness", "Uses the overdone exam result to explain the need for control.", 4),
        ],
    },
    {
        "item_id": "charms-short-011",
        "kind": "short_answer",
        "material_id": "charms-countercharm-hiccups",
        "prompt": "Explain the principle of a counter-charm using the countercharm for hiccups as the example.",
        "difficulty": "explanation",
        "model_answer": "A counter-charm targets a particular unwanted effect rather than undoing all magic. The countercharm for hiccups is a small, specific counter-charm that Hermione mentions while reviewing the Charms theory paper. Its place on the exam shows that students are expected to know both the original nuisance and the precise counter.",
        "required_points": ["hiccups", "counter-charm"],
        "rubric": [
            ("correctness", "Explains that a counter-charm is specific to one effect.", 4),
            ("completeness", "Uses the hiccups countercharm and its exam context as the example.", 4),
        ],
    },
    # jinxes, short answer
    {
        "item_id": "charms-short-012",
        "kind": "short_answer",
        "material_id": "charms-densaugeo",
        "prompt": "Describe Densaugeo and explain what the corridor scene shows about hexes in a crowded space.",
        "difficulty": "application",
        "model_answer": "Densaugeo enlarges the target's front teeth. Malfoy casts it at Harry in the corridor, but the jet ricochets into Hermione, whose front teeth grow at an alarming rate. The scene shows that a miss can hit the wrong person, and it contrasts a local hex with the Growth Charm.",
        "required_points": ["teeth", "ricochets"],
        "rubric": [
            ("correctness", "Describes the local effect on the target's front teeth.", 4),
            ("completeness", "Explains the ricochet and the risk it creates in a crowded corridor.", 4),
        ],
    },
    {
        "item_id": "charms-short-013",
        "kind": "short_answer",
        "material_id": "charms-furnunculus",
        "prompt": "Describe Furnunculus and explain what the corridor scene shows about aim and line of sight.",
        "difficulty": "application",
        "model_answer": "Furnunculus covers the target in boils, and the Pimple Jinx is a hex with a clear and unpleasant effect. Harry casts it at Malfoy in the corridor, but the spell ricochets into Goyle, whose nose erupts in ugly boils. The scene shows that a missed hex can hit an ally, so aim and line of sight matter in a duel.",
        "required_points": ["boils", "ricochets"],
        "rubric": [
            ("correctness", "Describes the boils produced by the Pimple Jinx.", 4),
            ("completeness", "Explains the ricochet and why aim and line of sight matter.", 4),
        ],
    },
    {
        "item_id": "charms-short-014",
        "kind": "short_answer",
        "material_id": "charms-leg-locker",
        "prompt": "Describe the Leg-Locker Curse and explain what the bathroom duel shows about its risks.",
        "difficulty": "application",
        "model_answer": "The Leg-Locker Curse binds a target's legs. In the bathroom duel Harry attempts it, but the spell backfires off the wall and smashes the cistern. The scene shows both the purpose of the spell and the risk of aiming a jinx in a confined space, where a miss can hit the environment.",
        "required_points": ["legs", "cistern"],
        "rubric": [
            ("correctness", "States that the curse binds the target's legs.", 4),
            ("completeness", "Explains the backfire and the danger of a confined space.", 4),
        ],
    },
    {
        "item_id": "charms-short-015",
        "kind": "short_answer",
        "material_id": "charms-rictusempra",
        "prompt": "Describe Rictusempra and explain why it sits between a playful charm and a combat jinx.",
        "difficulty": "explanation",
        "model_answer": "Rictusempra is the Tickling Charm, a jet of silver light that overwhelms a target with tickling sensation. Harry casts it at Malfoy in the duelling club, and Malfoy doubles up wheezing and can barely move for laughing. It is not a curse, but it is disabling while it lasts, which is why it sits between a playful charm and a combat jinx.",
        "required_points": ["tickling", "duelling"],
        "rubric": [
            ("correctness", "Describes the tickling effect and the jet of light.", 4),
            ("completeness", "Explains why the effect is disabling without being a curse.", 4),
        ],
    },
    {
        "item_id": "charms-short-016",
        "kind": "short_answer",
        "material_id": "charms-tarantallegra",
        "prompt": "Describe Tarantallegra and explain what its effect shows about the difference between a jinx and a curse.",
        "difficulty": "comparison",
        "model_answer": "Tarantallegra forces a target's legs into a frantic dance. Malfoy casts it at Harry in the duelling club, and Harry's legs jerk out of his control in a kind of quickstep. The spell is a jinx with a visible and humiliating effect that takes away control of movement without killing or wounding, which is what separates it from a curse.",
        "required_points": ["dance", "jinx"],
        "rubric": [
            ("correctness", "Describes the forced dancing movement.", 4),
            ("completeness", "Explains that it removes control without wounding, unlike a curse.", 4),
        ],
    },
    # utility, short answer
    {
        "item_id": "charms-short-017",
        "kind": "short_answer",
        "material_id": "charms-scourgify",
        "prompt": "Explain what Scourgify does and what kind of charm it is.",
        "difficulty": "explanation",
        "model_answer": "Scourgify cleans a surface or object by removing dirt and mess rather than moving the object. Tonks uses it on Hedwig's cage, and Hermione uses it to vanish Stinksap from the train compartment. It is a household utility charm, and it improves a condition without changing a thing's identity.",
        "required_points": ["dirt", "identity"],
        "rubric": [
            ("correctness", "States that Scourgify cleans rather than moves or changes the object.", 4),
            ("completeness", "Explains its place as a household utility charm with an example.", 4),
        ],
    },
    {
        "item_id": "charms-short-018",
        "kind": "short_answer",
        "material_id": "charms-impervius",
        "prompt": "Explain how Impervius changes a surface's interaction with its environment, using the Quidditch example.",
        "difficulty": "application",
        "model_answer": "Impervius repels water from a surface. Angelina has the Quidditch team cast it to keep rain off their faces and preserve visibility during the match. The charm changes how an object interacts with its environment without changing the object itself.",
        "required_points": ["repels", "visibility"],
        "rubric": [
            ("correctness", "States that Impervius repels water from a surface.", 4),
            ("completeness", "Uses the Quidditch rain example and explains the environmental change.", 4),
        ],
    },
    {
        "item_id": "charms-short-019",
        "kind": "short_answer",
        "material_id": "charms-hover",
        "prompt": "Explain what the Hover Charm does and how it differs from Summoning or Banishing.",
        "difficulty": "comparison",
        "model_answer": "The Hover Charm lifts an object and holds it in the air as a sustained levitation. The Ministry writes to Harry about a Hover Charm used at Privet Drive, and Hermione uses one to get Harry into his bunk because she cannot lift him. Unlike Summoning or Banishing, it keeps the object aloft rather than calling it to hand or throwing it away.",
        "required_points": ["aloft", "lift"],
        "rubric": [
            ("correctness", "Describes the sustained lift rather than a pull or push.", 4),
            ("completeness", "Contrasts it with Summoning and Banishing explicitly.", 4),
        ],
    },
    # practice, short answer
    {
        "item_id": "charms-short-020",
        "kind": "short_answer",
        "material_id": "charms-owl-theory",
        "prompt": "Explain what the Charms theory paper tests and why it is not a formality.",
        "difficulty": "explanation",
        "model_answer": "The Charms theory paper is a written examination that asks candidates to explain charm work, such as the wand movement required to make objects fly. Hermione comes out of it unsure about Cheering Charms and the countercharm for hiccups. The paper is not a formality because the Wizarding Examinations Authority sets it and the papers carry Anti-Cheating Charms.",
        "required_points": ["theory", "hiccups"],
        "rubric": [
            ("correctness", "Describes the written paper as testing explanation of charm work.", 4),
            ("completeness", "Gives evidence that the paper is a serious, externally set examination.", 4),
        ],
    },
    {
        "item_id": "charms-short-021",
        "kind": "short_answer",
        "material_id": "charms-owl-practical",
        "prompt": "Explain how the Charms practical examination is conducted and what it asks candidates to do.",
        "difficulty": "explanation",
        "model_answer": "The Charms practical is examined one small group at a time in a side chamber, while students wait and practise their incantations and wand movements. Inside, the examiner asks for concrete results, such as making an eggcup cartwheel with the Levitation Charm. The practical is a performance test rather than a written explanation.",
        "required_points": ["chamber", "cartwheel"],
        "rubric": [
            ("correctness", "Describes the small-group, one-at-a-time format.", 4),
            ("completeness", "Gives the concrete eggcup task and contrasts it with the theory paper.", 4),
        ],
    },
    {
        "item_id": "charms-short-022",
        "kind": "short_answer",
        "material_id": "charms-spell-failure",
        "prompt": "Explain why charm failure in the books is usually a problem of technique rather than power, using two examples.",
        "difficulty": "explanation",
        "model_answer": "Charm failure usually comes from wrong movement, wrong emphasis, wrong incantation or too much force. Seamus prods his feather with his wand and sets it alight, while Ron shouts the incantation and waves his arms until Hermione tells him he is saying it wrong. The pattern repeats when Harry mixes up Color-Change and Growth and swells the rat instead of turning it orange.",
        "required_points": ["technique", "feather"],
        "rubric": [
            ("correctness", "Names technique errors as the cause of failure.", 4),
            ("completeness", "Uses two distinct failed attempts as evidence.", 4),
        ],
    },
    {
        "item_id": "charms-short-023",
        "kind": "short_answer",
        "material_id": "charms-wands",
        "prompt": "Explain what the wand-weighing ceremony shows about how a wand's condition is tested.",
        "difficulty": "explanation",
        "model_answer": "A wand is the focus through which charm work is performed, and the books treat its condition as part of the magic. Ollivander examines the champions' wands for scratches and tests each one with a charm, using Orchideous, Avis and a fountain of wine. The ceremony shows that the test is functional because the charm proves the wand is responding.",
        "required_points": ["scratches", "functional"],
        "rubric": [
            ("correctness", "States that a wand is the focus of charm work and that condition matters.", 4),
            ("completeness", "Describes the charm tests and why the demonstration is functional.", 4),
        ],
    },
    {
        "item_id": "charms-short-024",
        "kind": "short_answer",
        "material_id": "charms-class",
        "prompt": "Explain how Charms lessons are organised to turn practice into control.",
        "difficulty": "explanation",
        "model_answer": "Charms classes are practical, paired and noisy, with Flitwick moving between desks to correct wrist movements and incantations. The trio also use the Charms classroom outside lessons to rehearse for the Triwizard tasks with Flitwick's cushions, and the OWL year adds revision and exam pressure. The pattern is short attempts, visible success and immediate correction.",
        "required_points": ["paired", "cushions"],
        "rubric": [
            ("correctness", "Describes paired practice with immediate correction.", 4),
            ("completeness", "Uses the out-of-lesson rehearsal and the OWL revision to show repetition.", 4),
        ],
    },
    {
        "item_id": "charms-short-025",
        "kind": "short_answer",
        "material_id": "charms-flitwick",
        "prompt": "Explain the teaching pattern the books associate with Flitwick and why it suits charm learning.",
        "difficulty": "explanation",
        "model_answer": "Flitwick demonstrates a charm, corrects the class's wrist movements and incantations, and then has them repeat it. He announces the Levitation Charm and drills swish-and-flick before the class tries it, praises Hermione's success publicly, and sends the boys away with the single word practice after Ron's flask explodes. The pattern of demonstrate, correct and repeat suits charm learning because control comes from repetition.",
        "required_points": ["demonstrate", "repeat"],
        "rubric": [
            ("correctness", "Describes the sequence of demonstration, correction and repetition.", 4),
            ("completeness", "Connects the pattern to the need for control through practice.", 4),
        ],
    },
]


def _validate_specs() -> None:
    seen: set[str] = set()
    for spec in ITEMS:
        if spec["item_id"] in seen:
            raise SystemExit(f"duplicate item id in ITEMS: {spec['item_id']}")
        seen.add(spec["item_id"])
        if spec["kind"] == "mcq":
            if len(spec["options"]) < 6:
                raise SystemExit(f"{spec['item_id']}: needs at least six options")
            if not 0 <= spec["correct"] < len(spec["options"]):
                raise SystemExit(f"{spec['item_id']}: correct index out of range")
        elif spec["kind"] == "short_answer":
            if len(spec["rubric"]) < 2:
                raise SystemExit(f"{spec['item_id']}: needs two rubric criteria")
            if sum(marks for _, _, marks in spec["rubric"]) != 8:
                raise SystemExit(f"{spec['item_id']}: rubric must sum to 8")


def _build_item(spec: dict, material, mark_reviewed: bool, position: int = 0) -> BankItem:
    option_ids = "abcdef"
    common = {
        "item_id": spec["item_id"],
        "subject": SUBJECT,
        "kind": spec["kind"],
        "prompt": spec["prompt"],
        "topic": material.topic,
        "concepts": (material.concept,),
        "material_id": spec["material_id"],
        "source_refs": material.source_refs,
        "evidence_snapshot": EvidenceSnapshot(
            **{
                key: value
                for key, value in material.source_refs[0].model_dump().items()
                if key != "citation_bucket"
            }
        ),
        "difficulty": spec["difficulty"],
        "rationale": spec.get("rationale"),
        "review_status": "reviewed" if mark_reviewed else "draft",
        "prompt_version": PROMPT_VERSION,
    }
    if spec["kind"] == "mcq":
        ordered = list(spec["options"])
        correct_text = ordered.pop(spec["correct"])
        ordered.insert(position, correct_text)
        options = tuple(
            McqOption(option_id=option_ids[index], text=text)
            for index, text in enumerate(ordered)
        )
        return BankItem(
            **common,
            marks=3,
            options=options,
            correct_option_id=option_ids[position],
        )
    rubric = tuple(
        RubricCriterion(criterion_id=criterion_id, description=description, max_marks=marks)
        for criterion_id, description, marks in spec["rubric"]
    )
    return BankItem(
        **common,
        marks=8,
        model_answer=spec["model_answer"],
        required_points=tuple(spec["required_points"]),
        rubric=rubric,
    )


def main() -> int:
    publish = "--publish" in sys.argv
    mark_reviewed = "--mark-reviewed" in sys.argv
    force = "--force" in sys.argv
    _validate_specs()

    pack = load_subject_pack(REPO / "data" / "subjects" / SUBJECT)
    chunks = load_chunks(REPO / "data" / "chunks.jsonl")
    index_hash = text_hash(chunks)
    by_id = {chunk.id: chunk for chunk in chunks}
    materials = {material.material_id: material for material in pack.materials}

    if OUT.joinpath("manifest.toml").exists() and not force:
        import tomllib

        existing = tomllib.loads(OUT.joinpath("manifest.toml").read_text("utf-8"))
        if existing.get("status") == "published":
            print(
                f"{OUT} holds a published bank; pass --force to rebuild it as a draft",
                file=sys.stderr,
            )
            return 1

    items: list[BankItem] = []
    mcq_seen = 0
    for spec in ITEMS:
        material = materials.get(spec["material_id"])
        if material is None:
            raise SystemExit(f"{spec['item_id']}: unknown material {spec['material_id']!r}")
        position = mcq_seen % 6 if spec["kind"] == "mcq" else 0
        if spec["kind"] == "mcq":
            mcq_seen += 1
        items.append(_build_item(spec, material, mark_reviewed, position))

    if publish:
        unreviewed = [item.item_id for item in items if item.review_status != "reviewed"]
        if unreviewed:
            print(
                "cannot publish unreviewed items: "
                + ", ".join(unreviewed[:5])
                + (" ..." if len(unreviewed) > 5 else "")
                + "; run --mark-reviewed after the maintainer review",
                file=sys.stderr,
            )
            return 1

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = {"mcq": sum(1 for item in items if item.kind == "mcq"),
              "short_answer": sum(1 for item in items if item.kind == "short_answer")}
    manifest = BankManifest(
        subject=SUBJECT,
        tier=pack.manifest.tier,
        version=PUBLISH_VERSION if publish else DRAFT_VERSION,
        status="published" if publish else "draft",
        built_at=now,
        reviewed_at=now if publish else "",
        pack_version=pack.manifest.version,
        pack_fingerprint=pack_fingerprint(pack),
        index_text_hash=index_hash,
        generator_model=GENERATOR_MODEL,
        generator_temperature=0.0,
        generator_prompt_version="charms-bank-authoring-v1",
        judge_model=JUDGE_MODEL,
        judge_temperature=0.0,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        mcq_count=counts["mcq"],
        short_answer_count=counts["short_answer"],
    )
    bank = ExamBank(manifest=manifest, items=items)
    validation = validate_bank(bank, pack, by_id, index_hash)

    print(
        f"bank {manifest.version} status={manifest.status} "
        f"mcq={counts['mcq']} short_answer={counts['short_answer']}"
    )
    print(f"pack {pack.manifest.version} fingerprint={manifest.pack_fingerprint}")
    for warning in validation.warnings:
        print(f"warning: {warning}")
    for error in validation.errors:
        print(f"error: {error}")
    if not validation.ok:
        print("not writing the bank: validation failed")
        return 1

    write_exam_bank(bank, OUT)
    print(f"wrote {OUT}")
    print(
        "coverage: "
        + ", ".join(
            f"{topic}={sum(kind.values())}"
            for topic, kind in sorted(validation.coverage.per_topic_kind.items())
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
