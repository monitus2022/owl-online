"""Author the Charms exam bank on the published Charms 1.0.0 pack (#213).

The bank prose lives here rather than in the pack: each item cites one reviewed
material, reuses that material's books-bucket source refs, and is validated by
`app.exam.bank.validate_bank` against the current corpus index hash. Evidence
quotes are never invented; they come from the pack's hash-checked refs.

Items are concept-only. Neither the prompt nor the golden answer may name a
character, house, book or scene, and a student must not need story knowledge to
answer. A scene may supply evidence, but the item restates the concept in
general terms ("a caster", "a target", "a learner"). `_check_prose` enforces a
denylist so a future edit cannot reintroduce a character or a scene.

    uv run python scripts/author_charms_bank.py                    # draft rebuild
    uv run python scripts/author_charms_bank.py --mark-reviewed    # record approval
    uv run python scripts/author_charms_bank.py --publish          # publish reviewed
    uv run python scripts/author_charms_bank.py --mark-reviewed --publish --force
"""

from __future__ import annotations

import re
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
PROMPT_VERSION = "charms-bank-authoring-v1"
GENERATOR_MODEL = "deepseek/deepseek-v4.1-flash"
JUDGE_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
JUDGE_PROMPT_VERSION = "owl-bank-judge-v3"

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
            "Charms requires no incantation; Transfiguration requires no wand movement.",
        ],
        "correct": 1,
        "rationale": "The subject boundary is behaviour versus identity, not practical versus theoretical.",
    },
    {
        "item_id": "charms-mcq-003",
        "kind": "mcq",
        "material_id": "charms-foundation-incantation",
        "prompt": "Why does precise pronunciation matter when casting Wingardium Leviosa?",
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
        "prompt": "What wand movement is used for the Levitation Charm?",
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
        "rationale": "The swish-and-flick wrist movement is the standard form for the charm.",
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
        "prompt": "Which result shows the Levitation Charm working correctly?",
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
        "rationale": "The charm lifts the target clear of the desk without changing or damaging it.",
    },
    {
        "item_id": "charms-mcq-007",
        "kind": "mcq",
        "material_id": "charms-banishing",
        "prompt": "Why can a missed Banishing Charm be dangerous?",
        "difficulty": "explanation",
        "options": [
            "It can turn the target into a heavier object.",
            "It can send a heavy object flying off course into the caster or a bystander.",
            "It can silence everyone nearby.",
            "It can make the caster lose control of the wand permanently.",
            "It can make the object impossible to summon later.",
            "It can create a second copy of the object.",
        ],
        "correct": 1,
        "rationale": "A missed Banishing Charm can send a heavy object off course.",
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
        "prompt": "What is the effect of Locomotor when cast on an object?",
        "difficulty": "application",
        "options": [
            "It shrinks the trunk to fit in a pocket.",
            "It moves the object through the air under the caster's direction.",
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
        "prompt": "What does a resisted Alohomora show about the spell?",
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
        "rationale": "Alohomora is a practical tool with limits.",
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
        "prompt": "Why can the Drought Charm not remove a large body of water?",
        "difficulty": "application",
        "options": [
            "It only works on salt water.",
            "It dries puddles and ponds but cannot drain a body of water as large as a lake.",
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
        "material_id": "charms-scourgify",
        "prompt": "A caster needs to remove dirt from a surface without moving it. Which charm fits?",
        "difficulty": "application",
        "options": [
            "Reparo",
            "Scourgify",
            "Diffindo",
            "Impervius",
            "Incendio",
            "Sonorus",
        ],
        "correct": 1,
        "rationale": "Scourgify removes dirt and mess without moving or changing the object.",
    },
    # foundations, short answer
    {
        "item_id": "charms-short-001",
        "kind": "short_answer",
        "material_id": "charms-foundation-concentration",
        "prompt": "Explain why concentration is treated as part of charm technique, and what happens when it is not controlled.",
        "difficulty": "explanation",
        "model_answer": "Concentration is the inward half of charm work: it coordinates the incantation and the wand movement toward one clear intention. A caster who recites the words with great force but without a settled intention can produce the wrong effect or an uncontrolled one. Concentration does not replace technique; it holds the word and the movement together.",
        "required_points": ["concentration", "intention"],
        "rubric": [
            ("correctness", "Explains concentration as the coordinating intention behind word and movement.", 4),
            ("completeness", "Explains that force or wording alone does not replace a settled intention.", 4),
        ],
    },
    {
        "item_id": "charms-short-002",
        "kind": "short_answer",
        "material_id": "charms-foundation-charm-vs-transfiguration",
        "prompt": "A pineapple is made to tap-dance and a mouse is turned into a snuffbox. Explain which change is a charm and which is Transfiguration, and why.",
        "difficulty": "comparison",
        "model_answer": "A charm gives an object or creature a new action, quality or movement without changing what it fundamentally is. Transfiguration changes what the thing is, so a pineapple made to tap-dance is still a pineapple, while a mouse turned into a snuffbox is not. The boundary matters because the two subjects test different kinds of change.",
        "required_points": ["charm", "transfiguration"],
        "rubric": [
            ("correctness", "States that a charm adds behaviour and Transfiguration changes identity.", 4),
            ("completeness", "Uses both example tasks to show the difference.", 4),
        ],
    },
    # movement, short answer
    {
        "item_id": "charms-short-003",
        "kind": "short_answer",
        "material_id": "charms-levitation-practice",
        "prompt": "Explain the parts of charm technique a learner must coordinate, and why raw power cannot make up for a mistake in them.",
        "difficulty": "explanation",
        "model_answer": "The Levitation Charm requires the swish-and-flick wrist movement, the precise incantation Wingardium Leviosa, and a clear intention held in mind. An attempt fails when a learner prods the target instead of performing the movement, stresses the syllables wrongly, or waves the arm without control. Power does not compensate for those errors, because the charm depends on coordinated technique rather than force.",
        "required_points": ["swish", "technique"],
        "rubric": [
            ("correctness", "Names movement, wording and focus as the charm's requirements.", 4),
            ("completeness", "Explains why force does not compensate for a technique error.", 4),
        ],
    },
    {
        "item_id": "charms-short-004",
        "kind": "short_answer",
        "material_id": "charms-growth",
        "prompt": "Describe the Growth Charm, explain how it differs from a generic intention to make something bigger, and what can go wrong if its incantation is confused with a color-change spell.",
        "difficulty": "application",
        "model_answer": "The Growth Charm makes an object or creature larger and has its own incantation. It is a distinct charm, so a caster who mixes its incantation with a color-change spell can produce an oversized target instead of the intended color. The mistake shows that Growth must be learned as a specific spell, not treated as a vague wish to enlarge something.",
        "required_points": ["larger", "incantation"],
        "rubric": [
            ("correctness", "States the effect of the Growth Charm and that it has its own incantation.", 4),
            ("completeness", "Explains the confusion with a color-change spell and the resulting oversized target.", 4),
        ],
    },
    # elements, short answer
    {
        "item_id": "charms-short-005",
        "kind": "short_answer",
        "material_id": "charms-nox",
        "prompt": "Explain what Nox does and why it is described as the counterpart of Lumos.",
        "difficulty": "explanation",
        "model_answer": "Nox extinguishes wandlight, ending the illumination created by Lumos. It is a precise command: the light goes out without affecting anything else, and the caster can still speak quietly. It is the counterpart of Lumos because it removes a previous charm rather than creating a new object or force.",
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
        "prompt": "Describe the Bird-Conjuring Charm and explain what its effect shows about conjuration as charm work.",
        "difficulty": "explanation",
        "model_answer": "Avis, the Bird-Conjuring Charm, produces a flock of small birds from the wand. The birds are real enough to fly away, and the spell carries force and direction as they burst from the wand tip. It is a conjuration within charm work: the caster creates a small living effect rather than changing an existing object.",
        "required_points": ["flock", "conjuration"],
        "rubric": [
            ("correctness", "Names the charm and describes the flock of birds.", 4),
            ("completeness", "Explains that the charm creates a living effect rather than changing an object.", 4),
        ],
    },
    {
        "item_id": "charms-short-007",
        "kind": "short_answer",
        "material_id": "charms-bluebell-flames",
        "prompt": "Describe Bluebell Flames and explain why they are useful against a light-shy plant.",
        "difficulty": "application",
        "model_answer": "Bluebell Flames are a charm-produced fire that gives light and warmth without needing wood. They can be cast quickly and used as a tool in a crisis, for example to drive back a light-shy plant. They behave like fire for that purpose, but they are created by the charm rather than fuelled by a material.",
        "required_points": ["bluebell", "warmth"],
        "rubric": [
            ("correctness", "Describes the flames as charm-produced light and heat.", 4),
            ("completeness", "Explains their use against a light-shy plant and how they behave like fire.", 4),
        ],
    },
    {
        "item_id": "charms-short-008",
        "kind": "short_answer",
        "material_id": "charms-fountain-of-wine",
        "prompt": "Describe the Fountain of Wine and explain how a conjured liquid effect can be used to test a wand.",
        "difficulty": "explanation",
        "model_answer": "The Fountain of Wine is a conjuring charm that produces a controlled stream of liquid from the wand tip. It is not a combat spell; it demonstrates controlled production and can show that a wand is responding. The effect shows that charm work can serve demonstration and verification as well as combat or household tasks.",
        "required_points": ["fountain", "verification"],
        "rubric": [
            ("correctness", "Describes a controlled production of liquid from the wand.", 4),
            ("completeness", "Explains the demonstration as a controlled production that verifies the wand.", 4),
        ],
    },
    {
        "item_id": "charms-short-009",
        "kind": "short_answer",
        "material_id": "charms-orchideous",
        "prompt": "Describe Orchideous and explain how a small conjured effect can be used to test a wand.",
        "difficulty": "explanation",
        "model_answer": "Orchideous produces a bunch of flowers from the wand tip. It is a simple conjuration that creates a small, harmless object rather than changing an existing one. A quick effect of this kind can serve as a functional test, showing that the wand is responding.",
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
        "prompt": "Explain what the Cheering Charm does and why controlling how much is applied matters.",
        "difficulty": "explanation",
        "model_answer": "The Cheering Charm lifts a person's mood, and the effect is visible in behaviour rather than in a physical transformation. Because it works on feelings, an excessive application can tip the target into uncontrolled laughter instead of a balanced lift in mood. The caster therefore has to judge the strength of the effect, not just the incantation.",
        "required_points": ["mood", "laughter"],
        "rubric": [
            ("correctness", "States that the charm affects mood rather than the body.", 4),
            ("completeness", "Explains that an excessive application produces uncontrolled laughter.", 4),
        ],
    },
    {
        "item_id": "charms-short-011",
        "kind": "short_answer",
        "material_id": "charms-countercharm-hiccups",
        "prompt": "Explain the principle of a counter-charm using the countercharm for hiccups as the example.",
        "difficulty": "explanation",
        "model_answer": "A counter-charm targets a particular unwanted effect rather than undoing all magic. The countercharm for hiccups is a small, specific counter-charm, and it serves as the model for the principle: a counter must match the effect it answers. Its narrowness is the point: it does not disable every spell, only the effect it is designed to answer.",
        "required_points": ["hiccups", "counter-charm"],
        "rubric": [
            ("correctness", "Explains that a counter-charm is specific to one effect.", 4),
            ("completeness", "Uses the hiccups countercharm as the example of a specific counter.", 4),
        ],
    },
    # jinxes, short answer
    {
        "item_id": "charms-short-012",
        "kind": "short_answer",
        "material_id": "charms-densaugeo",
        "prompt": "Describe Densaugeo and explain the risk a local hex creates when it misses.",
        "difficulty": "application",
        "model_answer": "Densaugeo enlarges the target's front teeth. The effect is local and specific, but a missed jet can ricochet and strike someone other than the intended target. That risk distinguishes a precise hex from a broad effect and makes aim and line of sight important.",
        "required_points": ["teeth", "local"],
        "rubric": [
            ("correctness", "Describes the local effect on the target's front teeth.", 4),
            ("completeness", "Explains the ricochet and the risk it creates for bystanders.", 4),
        ],
    },
    {
        "item_id": "charms-short-013",
        "kind": "short_answer",
        "material_id": "charms-furnunculus",
        "prompt": "Describe Furnunculus and explain why aim and line of sight matter when casting a hex.",
        "difficulty": "application",
        "model_answer": "Furnunculus covers the target in boils, and the Pimple Jinx is a hex with a clear, unpleasant effect. A missed hex can ricochet off a surface and strike an ally instead of the intended target. Aim and line of sight therefore matter as much as the incantation in a crowded space.",
        "required_points": ["boils", "ally"],
        "rubric": [
            ("correctness", "Describes the boils produced by the Pimple Jinx.", 4),
            ("completeness", "Explains the ricochet and why aim and line of sight matter.", 4),
        ],
    },
    {
        "item_id": "charms-short-014",
        "kind": "short_answer",
        "material_id": "charms-leg-locker",
        "prompt": "Describe the Leg-Locker Curse and explain the risk of casting it in a confined space.",
        "difficulty": "application",
        "model_answer": "The Leg-Locker Curse binds a target's legs. It is simple in principle but dangerous in practice: a missed spell can strike a wall or an object and affect the environment instead. In a confined space, the caster must consider the background as well as the target.",
        "required_points": ["legs", "confined"],
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
        "model_answer": "Rictusempra is the Tickling Charm, a jet of silver light that overwhelms a target with tickling sensation. It is not a curse, but it is disabling while it lasts because the target can barely move for laughing. That combination of a harmless label and a disabling effect is why it sits between a playful charm and a combat jinx.",
        "required_points": ["tickling", "jinx"],
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
        "model_answer": "Tarantallegra forces a target's legs into a frantic dance. The effect is visible and humiliating, and it takes away control of movement without killing or wounding. That distinguishes a jinx from a curse: the spell disrupts and embarrasses rather than causing lasting harm.",
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
        "model_answer": "Scourgify cleans a surface or object by removing dirt and mess rather than moving the object. It is a household utility charm, and it improves a condition without changing the thing's identity. Its short incantation and pointed wand action make it a practical spell for ordinary mess rather than a combat effect.",
        "required_points": ["dirt", "identity"],
        "rubric": [
            ("correctness", "States that Scourgify cleans rather than moves or changes the object.", 4),
            ("completeness", "Explains its place as a household utility charm and what it leaves unchanged.", 4),
        ],
    },
    {
        "item_id": "charms-short-018",
        "kind": "short_answer",
        "material_id": "charms-impervius",
        "prompt": "Explain how Impervius changes how a surface interacts with its environment, using rain as the example.",
        "difficulty": "application",
        "model_answer": "Impervius repels water from a surface. It is a practical response to weather: a water-repellent surface keeps rain off and preserves visibility for as long as the charm lasts. The charm changes how an object interacts with its environment without changing the object itself.",
        "required_points": ["repels", "visibility"],
        "rubric": [
            ("correctness", "States that Impervius repels water from a surface.", 4),
            ("completeness", "Explains the rain-repellent effect and the environmental change.", 4),
        ],
    },
    {
        "item_id": "charms-short-019",
        "kind": "short_answer",
        "material_id": "charms-hover",
        "prompt": "Explain what the Hover Charm does and how it differs from Summoning or Banishing.",
        "difficulty": "comparison",
        "model_answer": "The Hover Charm lifts an object and holds it in the air as a sustained levitation. It is used when an object is too heavy or awkward to lift by hand, and the object stays aloft rather than being thrown or pulled to the caster. Unlike Summoning or Banishing, it maintains the object in place in the air.",
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
        "material_id": "charms-incendio",
        "prompt": "Explain what Incendio produces and why it demands care in an enclosed space.",
        "difficulty": "application",
        "model_answer": "Incendio produces fire with an immediate, visible effect of light and heat. Because the fire is real and can spread, it is dangerous in an enclosed space where the caster and others have little room to avoid it. The spell is controlled fire production, useful for light, heat or burning, but it must be used with that risk in mind.",
        "required_points": ["fire", "enclosed"],
        "rubric": [
            ("correctness", "States that Incendio produces fire with light and heat.", 4),
            ("completeness", "Explains the danger of fire in an enclosed space.", 4),
        ],
    },
    {
        "item_id": "charms-short-021",
        "kind": "short_answer",
        "material_id": "charms-impediment",
        "prompt": "Explain what the Impediment Curse does and why a caster might choose it over a binding spell.",
        "difficulty": "comparison",
        "model_answer": "The Impediment Curse slows a target and disrupts its momentum rather than stopping it outright. That makes it a defensive choice when the caster needs to buy time without fully restraining the target. A binding spell imposes a harder stop, so the choice depends on how much restraint the situation allows.",
        "required_points": ["slows", "momentum"],
        "rubric": [
            ("correctness", "States that the curse slows and disrupts rather than binds.", 4),
            ("completeness", "Contrasts it with a binding spell and explains the choice.", 4),
        ],
    },
    {
        "item_id": "charms-short-022",
        "kind": "short_answer",
        "material_id": "charms-spell-failure",
        "prompt": "Explain why charm failure is usually a problem of technique rather than power, using two examples.",
        "difficulty": "explanation",
        "model_answer": "Charm failure is usually a matter of technique: wrong movement, wrong emphasis, wrong incantation or too much force. A learner who prods the target instead of performing the movement may set it alight, while a learner who shouts and waves the arm can still be saying the incantation wrongly. The pattern repeats when one charm's incantation is confused with another and the wrong effect appears.",
        "required_points": ["technique", "movement"],
        "rubric": [
            ("correctness", "Names technique errors as the cause of failure.", 4),
            ("completeness", "Uses two distinct failed attempts as evidence.", 4),
        ],
    },
    {
        "item_id": "charms-short-023",
        "kind": "short_answer",
        "material_id": "charms-wands",
        "prompt": "Explain how a wand's condition is tested and why the test is functional.",
        "difficulty": "explanation",
        "model_answer": "A wand is the focus through which charm work is performed, and its condition is part of the magic. A functional test uses a charm whose visible effect proves that the wand is responding, and different charms can be used for that test. The test is practical rather than decorative because a damaged or failing wand will not produce the expected effect.",
        "required_points": ["functional", "condition"],
        "rubric": [
            ("correctness", "States that a wand is the focus of charm work and that condition matters.", 4),
            ("completeness", "Explains why a visible charm effect is a practical test of condition.", 4),
        ],
    },
    {
        "item_id": "charms-short-024",
        "kind": "short_answer",
        "material_id": "charms-diffindo",
        "prompt": "Explain what Diffindo does and why precise aim matters when casting it.",
        "difficulty": "application",
        "model_answer": "Diffindo cuts or splits an object along a line rather than blasting it apart. Because the effect is precise, the caster must aim carefully: a cut in the wrong place can damage what should have been left intact. It is a versatile utility charm, not a healing spell, and it separates material rather than restoring it.",
        "required_points": ["cuts", "carefully"],
        "rubric": [
            ("correctness", "Describes a precise cut or split along a line.", 4),
            ("completeness", "Explains why aim matters and what the charm is not.", 4),
        ],
    },
    {
        "item_id": "charms-short-025",
        "kind": "short_answer",
        "material_id": "charms-reparo",
        "prompt": "Explain how Reparo reverses a break rather than hiding it.",
        "difficulty": "explanation",
        "model_answer": "Reparo mends a broken object by bringing its pieces back together. The object is rejoined rather than covered over, so the break is actually reversed and the object is good as new. That makes it a practical everyday charm rather than a cosmetic repair.",
        "required_points": ["pieces", "break"],
        "rubric": [
            ("correctness", "States that the pieces rejoin and the object is mended.", 4),
            ("completeness", "Explains that the break is reversed rather than hidden.", 4),
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
            answer = spec["model_answer"].lower()
            for point in spec["required_points"]:
                if point.lower() not in answer:
                    raise SystemExit(
                        f"{spec['item_id']}: required point {point!r} is missing "
                        "from the golden answer"
                    )
        _check_prose(spec)


# Concept-only rule: prompts, keys, options and rubrics must never need story
# knowledge. Names and scene markers are rejected rather than reviewed.
_FORBIDDEN_CHARACTERS = (
    "harry", "ron", "hermione", "malfoy", "neville", "seamus", "cedric",
    "ollivander", "tonks", "angelina", "bagman", "dumbledore", "hagrid",
    "krum", "fleur", "goyle", "crabbe", "flitwick", "mcgonagall", "snape",
    "dolohov", "ginny", "george", "fred", "luna", "sirius", "lupin",
    "voldemort", "quirrell", "lockhart", "umbridge", "slughorn", "crouch",
    "fudge", "skeeter", "cho", "dean", "lavender", "parvati", "dobby",
    "kreacher", "buckbeak", "hedwig", "crookshanks", "scabbers", "norbert",
    "aragog", "myrtle", "filch", "trelawney", "baruffio", "bellatrix",
    "lucius", "narcissa", "pettigrew", "wormtail", "moody", "kingsley",
    "shacklebolt", "pomfrey", "sprout", "vector", "binns", "hooch",
    "dudley", "vernon", "petunia", "riddle", "aberforth", "regulus",
    "karkaroff", "maxime", "grindelwald", "parkinson", "zabini", "chang",
    "diggory", "johnson", "spinnet", "alicia", "katie",
    "percy", "bill", "charlie", "arthur", "molly", "nymphadora",
)
_FORBIDDEN_HOUSES = ("gryffindor", "slytherin", "ravenclaw", "hufflepuff")
_FORBIDDEN_SCENES = (
    "privet drive", "third-floor", "duelling club", "bathroom", "train "
    "compartment", "quidditch", "triwizard", "grimmauld", "ministry of magic",
    "little whinging", "diagon alley", "hogwarts", "d.a.", "dumbledore's army",
    "chamber of secrets", "room of requirement", "burrow", "spinner's end",
    "library", "great hall", "whomping willow", "forbidden forest", "azkaban",
    "hogsmeade", "hogwarts express", "platform nine", "leaky cauldron",
    "gringotts", "shrieking shack", "department of mysteries",
    "quidditch pitch", "malfoy manor", "godric's hollow", "little hangleton",
    "philosopher's stone", "sorcerer's stone", "prisoner of azkaban",
    "goblet of fire", "order of the phoenix", "half-blood prince",
    "deathly hallows",
)
# Exam administration and classroom pedagogy are not charm concepts. A paper
# that asks about the exam while the student is sitting it is a bad item.
_FORBIDDEN_PEDAGOGY = (
    "exam", "exams", "lesson", "lessons", "classroom", "syllabus", "revision",
    "curriculum", "student", "students", "teacher", "teachers", "pupil",
    "pupils", "paper", "papers", "school", "professor", "taught", "homework",
    "schoolwork", "practical examination", "written paper", "theory paper",
)


def _check_prose(spec: dict) -> None:
    """Reject a character name or scene marker anywhere student-facing."""
    fields: list[tuple[str, str]] = [
        ("prompt", spec["prompt"]),
        ("rationale", spec.get("rationale") or ""),
    ]
    fields.extend(
        (f"options[{index}]", text)
        for index, text in enumerate(spec.get("options", []))
    )
    fields.extend(
        (f"required_points[{index}]", point)
        for index, point in enumerate(spec.get("required_points", []))
    )
    fields.extend(
        (f"rubric[{criterion_id}]", description)
        for criterion_id, description, _ in spec.get("rubric", [])
    )
    if spec.get("model_answer"):
        fields.append(("model_answer", spec["model_answer"]))
    for name, value in fields:
        lowered = value.lower()
        for term in _FORBIDDEN_CHARACTERS:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                raise SystemExit(
                    f"{spec['item_id']}: {name} names a character ({term!r}); "
                    "questions must stand without story knowledge"
                )
        for term in _FORBIDDEN_HOUSES:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                raise SystemExit(
                    f"{spec['item_id']}: {name} names a house ({term!r}); "
                    "questions must stand without story knowledge"
                )
        for term in _FORBIDDEN_SCENES:
            if term in lowered:
                raise SystemExit(
                    f"{spec['item_id']}: {name} refers to a scene ({term!r}); "
                    "questions must stand without story knowledge"
                )
        for term in _FORBIDDEN_PEDAGOGY:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                raise SystemExit(
                    f"{spec['item_id']}: {name} asks about exams or teaching "
                    f"({term!r}); items test charm concepts only"
                )


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
        generator_prompt_version=PROMPT_VERSION,
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
