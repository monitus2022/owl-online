"""Author DADA Units 2-8 as a material batch (appends to the Unit 1 pack).

Every claim in the prose was written only after reading the cited chunk. The
`cites` entries carry a short anchor phrase that occurs in that chunk; the
script slices the corpus there, widens to a whole sentence or a sane word
window, and stores the verbatim quote. The pack validator then recomputes the
chunk hashes and checks every quote is a real substring, so a drifted or
invented quotation fails the build.

  uv run python scripts/author_dada_units.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.materials import (  # noqa: E402
    Material,
    ReferenceLink,
    SourceRef,
    chunk_text_hash,
)
from app.knowledge.packs import (  # noqa: E402
    Concept,
    PackManifest,
    SubjectPack,
    Topic,
    load_subject_pack,
    validate_pack,
    write_subject_pack,
)
from app.pipeline.index.builder import load_chunks  # noqa: E402

INDEX_HASH = "aca4c57462d449f5"
VERSION = "0.3.0"
CITE_RE = re.compile(r"\[(b[1-7]-c\d{2}-\d{4})\]")

MATERIALS: list[dict] = [
    # ---------------------------------------------------------------- Unit 2
    {
        "unit": 2,
        "material_id": "dada-dark-creatures-dementors-nature",
        "topic": "dark-creatures",
        "concept": "dada-creature-dementors",
        "text": """
            A dementor is not a beast one fights so much as a climate one
            endures. They infest the darkest, filthiest places, glory in
            decay and despair, and drain peace, hope and happiness out of the
            air around them [b3-c10-0016]. Left too long with a wizard, they
            are supposed to drain his powers; most who are trapped with them
            go mad within weeks [b3-c10-0020]. The hood comes down only for
            their last and worst weapon, the Dementor's Kiss: they clamp
            their jaws upon the victim's mouth and suck out the soul
            [b3-c12-0051], [b3-c12-0052]. Resisting one does not solve the
            problem - the more there are, the harder they are to hold off
            [b3-c10-0021]. That is why the Patronus is taught as a discipline
            of its own, and why a dementor is never a small thing to bring
            into a room.
        """,
        "cites": {
            "b3-c10-0016": "Dementors are among the foulest creatures",
            "b3-c10-0020": "Most of them go mad within weeks",
            "b3-c12-0051": "only to use its last and worst weapon",
            "b3-c12-0052": "suck out his soul",
            "b3-c10-0021": "The more there are, the more difficult it becomes",
        },
    },
    {
        "unit": 2,
        "material_id": "dada-magic-patronus-theory",
        "topic": "defensive-magic",
        "concept": "dada-magic-patronus",
        "text": """
            The Patronus is a kind of positive force, a projection of the
            very things the dementor feeds upon - hope, happiness, the desire
            to survive - but it cannot feel despair, so a dementor cannot
            hurt it [b3-c12-0015]. The incantation is Expecto Patronum, and
            the concentration must be on a happy memory rather than on the
            danger [b3-c12-0018]. An indistinct silver shadow is not yet a
            Patronus: it hovers and drains the caster without driving
            anything away [b3-c12-0047]. The true Patronus charges the
            dementors and makes them disappear [b3-c12-0049]. For a
            thirteen-year-old, even an indistinct Patronus is a considerable
            achievement, and a caster who can hold one long enough to reach
            the ground has done the work the charm is for [b3-c12-0048],
            [b3-c12-0049].
        """,
        "cites": {
            "b3-c12-0015": "The Patronus is a kind of positive force",
            "b3-c12-0018": "The incantation is this",
            "b3-c12-0047": "his Patronus was too feeble",
            "b3-c12-0049": "The true Patronus does do that",
            "b3-c12-0048": "even an indistinct Patronus is a huge achievement",
        },
    },
    {
        "unit": 2,
        "material_id": "dada-magic-patronus-training",
        "topic": "defensive-magic",
        "concept": "dada-magic-corporeal-patronus",
        "text": """
            Training follows the danger without borrowing it. Lupin used a
            boggart as the nearest substitute for a real dementor, because it
            would turn into one when it saw the student [b3-c12-0012],
            [b3-c12-0013]. The method is honest about failure: a session can
            end with the caster on the floor, the classroom lamps relit, and
            no shame in trying again [b3-c12-0021]. When the boggart has
            served its purpose it is dismissed with Riddikulus, and the caster
            is left as exhausted as after a mile run [b3-c12-0033]. The D.A.
            later used the same trick, and Harry warned that a Patronus raised
            in a bright classroom is very different from one raised under
            threat [b5-c27-0032], [b5-c27-0034]. The Patronus is not meant to
            be pretty; it is meant to protect you [b5-c27-0033].
        """,
        "cites": {
            "b3-c12-0012": "Another boggart",
            "b3-c12-0013": "nearest we'll get to a real dementor",
            "b3-c12-0021": "lying flat on his back on the floor",
            "b3-c12-0033": "as exhausted as if he'd just run a mile",
            "b5-c27-0032": "very different to producing it when confronted",
            "b5-c27-0034": "that's how I learned",
            "b5-c27-0033": "They're not supposed to be pretty",
        },
    },
    # ---------------------------------------------------------------- Unit 3
    {
        "unit": 3,
        "material_id": "dada-dark-creatures-fieldcraft-pixies",
        "topic": "dark-creatures",
        "concept": "dada-creature-pixie",
        "text": """
            The Cornish pixie is the classroom's best argument for
            preparation. Lockhart called them devilish tricky little blighters
            and opened the cage to show the class [b2-c06-0063],
            [b2-c06-0064]. Electric blue, eight inches high and shrill as
            budgerigars, they seized Neville by the ears and lifted him into
            the air, smashed the window, sprayed ink, shredded books, and left
            half the class sheltering under the desks [b2-c06-0065],
            [b2-c06-0066]. Lockhart's incantation, Peskipiksi Pesternomi, had
            no effect at all; a pixie took his wand and threw it out of the
            window too [b2-c06-0067]. The lesson was salvaged by Hermione, who
            immobilised two pixies with a Freezing Charm and stuffed them back
            into the cage [b2-c06-0069]. The creature is not lethal; the
            failure is. A working counter, practised before the cage opens, is
            the whole difference between a demonstration and a rout.
        """,
        "cites": {
            "b2-c06-0063": "Freshly caught Cornish pixies",
            "b2-c06-0064": "Devilish tricky little blighters",
            "b2-c06-0065": "seized Neville by the ears",
            "b2-c06-0066": "wreck the classroom",
            "b2-c06-0067": "Peskipiksi Pesternomi",
            "b2-c06-0069": "immobilizing two pixies",
        },
    },
    {
        "unit": 3,
        "material_id": "dada-dark-creatures-fieldcraft-water-and-marsh",
        "topic": "dark-creatures",
        "concept": "dada-creature-grindylow",
        "text": """
            Lupin's third-year practical put the class through the hazards in
            the order a traveller meets them. They waded a deep pool
            containing a grindylow, crossed potholes full of Red Caps, crossed
            a marsh while ignoring misleading directions from a hinkypunk, and
            finished by climbing into a trunk to battle a fresh boggart
            [b3-c16-0018]. The hinkypunk is the subtle one: it lures travellers
            into bogs with a lantern dangling from its hand, hopping ahead so
            that people follow the light [b3-c10-0011], [b3-c10-0012]. Ron did
            well until the hinkypunk confused him into sinking waist-high into
            the quagmire [b3-c16-0020]. By the end of the year the class had
            covered boggarts, Red Caps, kappas and grindylows - first-year
            creatures, Snape said, and he was not wrong that they should be
            automatic [b3-c09-0031], [b3-c09-0032].
        """,
        "cites": {
            "b3-c16-0018": "a sort of obstacle course",
            "b3-c10-0011": "Lures travelers into bogs",
            "b3-c10-0012": "Hops ahead",
            "b3-c16-0020": "sinking waist-high into the quagmire",
            "b3-c09-0031": "we've done boggarts, Red Caps, kappas, and grindylows",
            "b3-c09-0032": (
                "I would expect first years to be able to deal with Red Caps and grindylows"
            ),
        },
    },
    {
        "unit": 3,
        "material_id": "dada-dark-creatures-fieldcraft-thestrals",
        "topic": "dark-creatures",
        "concept": "dada-creature-thestral",
        "text": """
            Thestrals are the clearest case of a creature judged by its
            reputation. Hogwarts keeps a whole herd, and the superstition says
            they bring misfortune to those who see them [b5-c21-0022]. The
            truth is narrower: only people who have seen death can see them at
            all [b5-c21-0025], [b5-c33-0051]. The Ministry classifies them as
            dangerous; Hagrid's correction is that they are not dangerous,
            though they may bite if really annoyed, and that their bad name
            comes from the death thing [b5-c21-0030], [b5-c21-0031]. In battle
            they are neither omens nor pets but cavalry: thestrals and
            Buckbeak scratched at the eyes of Voldemort's giants
            [b7-c36-0037]. Harry's summary to a first-year is the one to
            remember - they are gentle things, and there is nothing scary about
            them [b7-c36-0119].
        """,
        "cites": {
            "b5-c21-0022": "They're supposed to bring all sorts of horrible misfortune",
            "b5-c21-0025": "are people who have seen death",
            "b5-c33-0051": "unless you've watched someone",
            "b5-c21-0030": "classified thestrals as",
            "b5-c21-0031": "bad reputation because o' the death thing",
            "b7-c36-0037": "thestrals and Buckbeak the hippogriff",
            "b7-c36-0119": "They're gentle things",
        },
    },
    # ---------------------------------------------------------------- Unit 4
    {
        "unit": 4,
        "material_id": "dada-dark-creatures-werewolves-recognition",
        "topic": "dark-creatures",
        "concept": "dada-creature-werewolf",
        "text": """
            The approved lessons on werewolves are a case study in what a
            classroom can and cannot do. Snape, covering for Lupin, skipped the
            planned hinkypunk lesson and turned the class to page 394,
            announcing that he had never met third years who could not
            recognise a werewolf [b3-c09-0033], [b3-c09-0035]. The class sat
            and made notes; the homework was two rolls of parchment on the
            ways to recognise and kill werewolves [b3-c09-0039],
            [b3-c09-0040]. Set that against Lockhart's version two years
            earlier, where Harry was hauled to the front to act the werewolf
            and the lesson ended with the fur vanishing and the fangs
            shrinking [b2-c10-0001], [b2-c10-0004]. One teacher made the
            danger a performance; the other made it a textbook. Neither put
            the class in front of the real thing.
        """,
        "cites": {
            "b3-c09-0033": "we're due to start hinkypunks",
            "b3-c09-0035": "wouldn't even recognize a werewolf",
            "b3-c09-0039": "ways you recognize and kill werewolves",
            "b3-c09-0040": "two rolls of parchment",
            "b2-c10-0001": "acting a werewolf",
            "b2-c10-0004": "the fur vanished",
        },
    },
    {
        "unit": 4,
        "material_id": "dada-dark-creatures-werewolves-law-and-fear",
        "topic": "dark-creatures",
        "concept": "dada-creature-werewolf",
        "text": """
            Werewolf law and werewolf fear are not the same subject, though the
            books keep them in the same room. Umbridge drafted anti-werewolf
            legislation two years before the fifth year that made it almost
            impossible for Lupin to get a job [b5-c14-0104], and Sirius
            describes her as loathing part-humans, with a campaign to round up
            and tag merpeople to prove it [b5-c14-0105]. The fear has a real
            face as well: Fenrir Greyback is the exception used to justify the
            rule, a werewolf who attacks without the full moon and boasts of
            liking children [b6-c27-0054], [b6-c27-0055]. Defence teaching has
            to hold both facts at once - the ordinary werewolf who wants a job
            and the predator who makes the law easy to pass - or it teaches
            prejudice and calls it vigilance.
        """,
        "cites": {
            "b5-c14-0104": "anti-werewolf legislation",
            "b5-c14-0105": "part-humans",
            "b6-c27-0054": "Is that you, Fenrir",
            "b6-c27-0055": "how much I like kids",
        },
    },
    {
        "unit": 4,
        "material_id": "dada-dark-creatures-grim-private-fear",
        "topic": "dark-creatures",
        "concept": "dada-creature-grim",
        "text": """
            The Grim is the other half of the same lesson: what fear does when
            it has no body to fight. Harry saw a great black dog twice, and
            both appearances were followed by near-fatal accidents - the
            Knight Bus, then the fifty-foot fall from his broom
            [b3-c10-0002], [b3-c10-0003]. He kept it to himself because he
            knew Ron would panic and Hermione would scoff [b3-c10-0002]. For
            a defence class the episode is a warning about private fear: an
            omen kept secret cannot be checked, while a fear spoken aloud can
            be tested against the evidence. The counter to a Grim is not a
            spell; it is the habit of naming the fear before it starts steering
            your choices.
        """,
        "cites": {
            "b3-c10-0002": "it had now appeared twice",
            "b3-c10-0003": "fallen fifty feet from his broomstick",
        },
    },
    # ---------------------------------------------------------------- Unit 5
    {
        "unit": 5,
        "material_id": "dada-dark-arts-unforgivables-law",
        "topic": "dark-arts",
        "concept": "dada-magic-unforgivable-curses",
        "text": """
            Three curses carry the weight of wizarding law: Avada Kedavra,
            Imperius and Cruciatus. The use of any one of them on a fellow
            human being is enough to earn a life sentence in Azkaban
            [b4-c14-0031]. The Ministry's syllabus for the fourth year stops at
            countercurses and does not show illegal Dark curses until the sixth
            year; Dumbledore overrode that, on the argument that the sooner you
            know what you are up against, the better [b4-c14-0009],
            [b4-c14-0010]. Moody's own justification is narrower than it
            sounds: he is not teaching the casting, he is teaching the
            recognition, because you cannot defend against something you have
            never seen [b4-c14-0010]. The lesson ends not with a spell but
            with a standing order: constant, never-ceasing vigilance
            [b4-c14-0031].
        """,
        "cites": {
            "b4-c14-0031": "are known as the Unforgivable Curses",
            "b4-c14-0009": "I'm supposed to teach you countercurses",
            "b4-c14-0010": "defend yourself against something you've never seen",
        },
    },
    {
        "unit": 5,
        "material_id": "dada-dark-arts-imperius-demonstration",
        "topic": "dark-arts",
        "concept": "dada-magic-imperius-curse",
        "text": """
            The Imperius Curse is demonstrated before it is described. Moody
            put it on a spider and made it swing on a thread, do a back flip
            and cartwheel across the desk [b4-c14-0014]. Then he announced
            that he would put it on each student in turn, to show its power and
            to see whether they could resist [b4-c15-0008]. Hermione objected
            that it was illegal; Moody answered that Dumbledore wanted them
            taught what it felt like [b4-c15-0009]. Harry's account is the
            clearest evidence of why: it was the most wonderful feeling, every
            thought and worry wiped gently away, and the order to jump onto the
            desk arrived as if from a distant chamber [b4-c15-0012],
            [b4-c15-0013]. He resisted by answering the order with a second
            voice - no, I don't think I will - and came out of it with two
            fractured kneecaps rather than a broken will [b4-c15-0014].
        """,
        "cites": {
            "b4-c14-0014": "began to swing backward and forward",
            "b4-c15-0008": "putting the Imperius Curse on each of them",
            "b4-c15-0009": "Dumbledore wants you taught what it feels like",
            "b4-c15-0012": "the most wonderful feeling",
            "b4-c15-0013": "echoing in some distant chamber",
            "b4-c15-0014": "No, I don't think I will",
        },
    },
    {
        "unit": 5,
        "material_id": "dada-dark-arts-cruciatus-evidence",
        "topic": "dark-arts",
        "concept": "dada-magic-cruciatus-curse",
        "text": """
            The Cruciatus Curse is the one the books refuse to make abstract.
            Moody's spider bent its legs in upon its body, rolled over and
            twitched horribly; no sound came from it, but the class understood
            that if it could have screamed it would have [b4-c14-0020].
            Neville's hands were clenched white on the desk and his eyes were
            horrified, and Hermione was looking at Neville rather than at the
            spider [b4-c14-0021]. Moody's summary is the definition: you do
            not need thumbscrews or knives to torture someone if you can
            perform the Cruciatus Curse [b4-c14-0022]. The curse is not a
            threat to be traded in an argument; it is the thing defence exists
            to prevent, and the class is expected to know what it looks like
            before they are asked to face it.
        """,
        "cites": {
            "b4-c14-0020": "legs bent in upon its body",
            "b4-c14-0021": "Neville's hands were clenched",
            "b4-c14-0022": "You don't need thumbscrews or knives",
        },
    },
    {
        "unit": 5,
        "material_id": "dada-dark-arts-killing-curse-limits",
        "topic": "dark-arts",
        "concept": "dada-magic-killing-curse",
        "text": """
            Avada Kedavra is the last and worst. A flash of green light and a
            rushing sound, and the spider rolled onto its back, unmarked but
            unmistakably dead [b4-c14-0024], [b4-c14-0025]. There is no
            countercurse and no blocking it; only one known person has ever
            survived it [b4-c14-0026]. Moody is careful about the limits of
            the demonstration: the curse needs a powerful bit of magic behind
            it, and a class full of wands pointed at him and saying the words
            would not give him so much as a nosebleed [b4-c14-0030]. That is
            the distinction the unit turns on - knowing the words is not the
            same as being able to cast them, and being able to cast them is not
            the same as being willing to. Defence begins with the third
            question.
        """,
        "cites": {
            "b4-c14-0024": "Moody roared",
            "b4-c14-0025": "unmarked, but unmistakably dead",
            "b4-c14-0026": "no countercurse",
            "b4-c14-0030": "needs a powerful bit of magic behind it",
        },
    },
    # ---------------------------------------------------------------- Unit 6
    {
        "unit": 6,
        "material_id": "dada-dueling-disarming-charm",
        "topic": "dueling",
        "concept": "dada-magic-disarming-charm",
        "text": """
            The Disarming Charm is the first spell of the duelling club
            [b2-c11-0029] and the last one Harry casts against Voldemort
            [b7-c36-0079]. Snape demonstrated it on Lockhart, blasting him off
            his feet and into the wall; Lockhart called it a Disarming Charm
            and admitted he had lost his wand [b2-c11-0029], [b2-c11-0030].
            Harry opened the D.A. with the same
            spell, over Zacharias Smith's sneer, because it had saved his life
            the previous June [b5-c18-0081], [b5-c18-0082]. The drill is
            partner work: on the count of three, wands fly, missed spells hit
            the shelves, and the partner who is watching the wrong way is not a
            realistic opponent [b5-c18-0084], [b5-c18-0086]. By the seventh
            year Lupin is urging Harry to move past Disarming, and the Death
            Eaters have learned to read it as his signature [b7-c05-0026],
            [b7-c05-0028]. A basic spell is not a weak one; it is a spell whose
            limits you have to know.
        """,
        "cites": {
            "b2-c11-0029": "blasted off his feet",
            "b2-c11-0030": "That was a Disarming Charm",
            "b5-c18-0081": "the first thing we should do is Expelliarmus",
            "b5-c18-0082": "It saved my life last June",
            "b5-c18-0084": "Wands flew in all directions",
            "b5-c18-0086": "unlikely to be staring in the opposite direction",
            "b7-c05-0026": "for Disarming is past",
            "b7-c05-0028": "signature move",
            "b7-c36-0079": "Expelliarmus!",
        },
    },
    {
        "unit": 6,
        "material_id": "dada-dueling-stunning-spell",
        "topic": "dueling",
        "concept": "dada-magic-stunning-spell",
        "text": """
            The Stunning Spell is the duellist's working tool, and the books
            are honest about when it fails. Harry's Stupefy rebounded off a
            Blast-Ended Skrewt's armour and singed his hair; Impedimenta
            worked only when it hit a soft spot [b4-c31-0077],
            [b4-c31-0078]. Against Krum it hit him in the back and dropped him
            at once [b4-c31-0082]. Against the giant spider in the maze it did
            no more than aggravate the creature, and Harry had to disarm it to
            make it let go [b4-c31-0099], [b4-c31-0100], [b4-c31-0101]. In
            the battle the spell is used constantly - Harry knocks spiders off
            the castle wall, Dean drops a Death Eater with one [b7-c32-0003],
            [b7-c32-0026]. The lesson is not that Stupefy is unreliable; it
            is that a duellist must know which target will accept it.
        """,
        "cites": {
            "b4-c31-0077": "Its thick armor glinted",
            "b4-c31-0078": "The spell hit the skrewt's armor and rebounded",
            "b4-c31-0082": "The spell hit Krum in the back",
            "b4-c31-0099": "might as well have thrown a stone at it",
            "b4-c31-0100": "doing no more than aggravating it",
            "b4-c31-0101": "the Disarming Spell made the spider drop him",
            "b7-c32-0003": "Harry fired Stunning Spells down upon them",
            "b7-c32-0026": "knocking him out with a Stunning Spell",
        },
    },
    {
        "unit": 6,
        "material_id": "dada-dueling-shield-charm",
        "topic": "defensive-magic",
        "concept": "dada-magic-shield-charm",
        "text": """
            The Shield Charm is the defensive spine of the D.A. curriculum: a
            means of deflecting minor jinxes so that they rebound upon the
            attacker [b5-c25-0045]. Neville mastered it faster than anyone but
            Hermione [b5-c25-0045]. Its ceiling matters as much as its floor. Harry's
            Protego against Snape was strong enough to knock him off balance
            and send his wand upward [b5-c26-0094], and in the final battle his
            Shield Charm expanded across the Great Hall [b7-c36-0052]. But the
            charm is described for minor jinxes, not for the Killing Curse;
            against Avada Kedavra there is no blocking at all [b4-c14-0026]. A
            shield is a discipline of proportion - know what it can stop before
            you stand behind it.
        """,
        "cites": {
            "b5-c25-0045": "a means of deflecting minor jinxes",
            "b5-c26-0094": "Snape staggered; his wand flew upward",
            "b7-c36-0052": "the Shield Charm expanded in the middle of the Hall",
            "b4-c14-0026": "no blocking it",
        },
    },
    # ---------------------------------------------------------------- Unit 7
    {
        "unit": 7,
        "material_id": "dada-countering-countercurse-doctrine",
        "topic": "defensive-magic",
        "concept": "dada-magic-countercurse",
        "text": """
            Moody's first fourth-year lesson states the doctrine plainly. The
            class had a thorough grounding in Dark creatures but was very
            behind on curses, and the Ministry's syllabus stopped at
            countercurses [b4-c14-0006], [b4-c14-0009]. Moody refused that
            limit: you cannot defend yourself against something you have never
            seen, so he showed the illegal curses two years early and taught
            recognition before response [b4-c14-0010]. Snape's formulation is
            the same idea from the other side: defence must be as flexible and
            inventive as the arts you seek to undo [b6-c09-0029]. Umbridge's
            theory-only syllabus is the counter-example - Parvati's objection
            that they had never practised a countercurse is the whole argument
            against it [b5-c12-0101]. Countercurse work is not a list of
            answers; it is the habit of matching the response to the attack.
        """,
        "cites": {
            "b4-c14-0006": "on dealing with curses",
            "b4-c14-0009": "I'm supposed to teach you countercurses",
            "b4-c14-0010": "defend yourself against something you've never seen",
            "b6-c09-0029": "as flexible and inventive as the arts you seek to undo",
            "b5-c12-0101": "Without ever practicing them before?",
        },
    },
    {
        "unit": 7,
        "material_id": "dada-countering-hex-deflection",
        "topic": "defensive-magic",
        "concept": "dada-magic-hex-deflection",
        "text": """
            Hex-deflection is taught as a physical skill, not a reading. Moody
            gave the class such a rigorous test of hex-deflection that many
            left nursing small injuries, and Harry spent the walk back holding
            his ears because of a bad case of Twitchy Ears [b4-c28-0045]. The
            D.A. year turned the same practice into competition: Harry and Ron
            worked through fresh hexes at every spare moment, and Ron called it
            good training for Aurors [b4-c31-0011], [b4-c31-0012]. The
            reference book the trio relied on was Practical Defensive Magic and
            Its Use Against the Dark Arts, full of moving illustrations of
            counterjinxes and hexes [b5-c23-0046]. The point of the bruising is
            not toughness; it is that a counter practised only on paper has
            never met a real jinx.
        """,
        "cites": {
            "b4-c28-0045": "rigorous test of hex-deflection",
            "b4-c31-0011": "Good training for when we're all Aurors",
            "b4-c31-0012": "practicing hexes at every available moment",
            "b5-c23-0046": "Practical Defensive Magic and Its Use Against the Dark Arts",
        },
    },
    {
        "unit": 7,
        "material_id": "dada-countering-detection-and-concealment",
        "topic": "defensive-magic",
        "concept": "dada-magic-concealment-charm",
        "text": """
            Detection is the quiet half of defence. A Secrecy Sensor vibrates
            when it detects concealment and lies, though too much ordinary
            student dishonesty can make it hum constantly [b4-c20-0023].
            Secrecy Sensors are used to find Dark Magic and Dark objects
            because they pick up jinxes, curses and concealment charms
            [b6-c15-0016]. The Fidelius Charm is the opposite extreme: a
            secret hidden inside a single living soul, impossible to find
            unless the Secret-Keeper chooses to divulge it [b3-c10-0083],
            [b3-c10-0084]. That is the whole spectrum the unit has to teach - a
            sensor that catches a lie, and a charm that can hide a house from a
            war. Both are only as good as the person trusted with them.
        """,
        "cites": {
            "b4-c20-0023": "Vibrates when it detects concealment and lies",
            "b6-c15-0016": "detect jinxes, curses, and concealment charms",
            "b3-c10-0083": "involving the magical concealment of a secret inside a",
            "b3-c10-0084": "impossible to find",
        },
    },
    # ---------------------------------------------------------------- Unit 8
    {
        "unit": 8,
        "material_id": "dada-protective-fidelius-trust",
        "topic": "defensive-magic",
        "concept": "dada-magic-fidelius-charm",
        "text": """
            The Fidelius Charm is the clearest lesson in trust in the pack. It
            hides a secret inside a single living soul, the Secret-Keeper, and
            the information is impossible to find unless that person chooses to
            divulge it [b3-c10-0083], [b3-c10-0084]. The Potters'
            Secret-Keeper was Sirius Black, and the charm was performed barely
            a week before it failed
            [b3-c10-0087]. When Dumbledore, the Secret-Keeper for Grimmauld
            Place, died, everyone he had told became a Secret-Keeper in turn;
            that diluted the charm and multiplied the chances of a leak
            [b7-c06-0015]. The charm does not fail because the magic is weak;
            it fails because a person decides to speak. Protective magic under
            pressure is therefore a study of people as much as spells.
        """,
        "cites": {
            "b3-c10-0083": "their best chance was the Fidelius Charm",
            "b3-c10-0084": "impossible to find",
            "b3-c10-0087": "barely a week after the Fidelius Charm had been performed",
            "b7-c06-0015": "after the death of Dumbledore, their Secret-Keeper",
        },
    },
    {
        "unit": 8,
        "material_id": "dada-protective-wards-at-scale",
        "topic": "defensive-magic",
        "concept": "dada-magic-shield-charm",
        "text": """
            At the scale of a castle, protection becomes an incantation of
            great complexity. Flitwick was muttering Protego Horribilis at the
            smashed window, and the effect sounded as though he had unleashed
            the power of the wind into the grounds [b7-c30-0044],
            [b7-c30-0045]. At the scale of a hall, Harry's Protego expanded
            across the Great Hall and made Voldemort look around for the source
            [b7-c36-0052]. The same charm at the scale of a classroom is only
            a deflection for minor jinxes [b5-c25-0045]. The unit's lesson is
            proportion: the spell is the same, the skill is in knowing how much
            of the world you are trying to hold, and what it costs to hold it.
        """,
        "cites": {
            "b7-c30-0044": "unleashed the power of the wind into the grounds",
            "b7-c30-0045": "Protego Horribilis",
            "b7-c36-0052": "the Shield Charm expanded in the middle of the Hall",
            "b5-c25-0045": "deflecting minor jinxes",
        },
    },
    {
        "unit": 8,
        "material_id": "dada-protective-patronus-field",
        "topic": "defensive-magic",
        "concept": "dada-magic-patronus",
        "text": """
            The Patronus is the one protective spell in the pack that has to
            work while the caster is afraid. Harry's first true field use held
            a boggart-dementor at bay long enough for him to recognise it and
            finish it with Riddikulus [b4-c31-0068]. The D.A. trained the same
            way, with a boggart standing in for a dementor, because a bright
            classroom is very different from a threat [b5-c27-0032],
            [b5-c27-0034]. Harry's warning to the D.A. is the unit's thesis:
            the Patronus is not supposed to be pretty, it is supposed to
            protect you [b5-c27-0033]. A protective spell that only works when
            you are comfortable is not a protective spell; it is a
            performance.
        """,
        "cites": {
            "b4-c31-0068": "You're a boggart! Riddikulus!",
            "b5-c27-0032": "very different to producing it when confronted",
            "b5-c27-0034": "that's how I learned",
            "b5-c27-0033": "They're not supposed to be pretty",
        },
    },
]

TOPICS = {
    "dark-creatures": "Dark Creatures",
    "dark-arts": "The Dark Arts",
    "defensive-magic": "Defensive Magic",
    "dueling": "Dueling",
}

LESSON_MAP = {
    2: [
        "Hook: a dementor is a climate, not a duel - nature material.",
        "Mechanism: the Kiss and the numbers problem - nature material.",
        "Counter: the Patronus as a positive force - theory material.",
        "Practice: boggart-as-dementor drill, failure allowed - training material.",
        "Failure cases: indistinct Patronus, passing out, classroom vs threat.",
        "Rationale: why a thirteen-year-old's silver shadow still counts.",
    ],
    3: [
        "Hook: the pixie lesson as a rout that could have been a demonstration.",
        "Mechanism: the exam's obstacle order - water, potholes, marsh, trunk.",
        "Counter: Freezing Charm, keeping to the path, ignoring the lantern.",
        "Practice: partner drill against one hazard at a time.",
        "Failure cases: opened cage, followed light, misjudged reputation.",
        "Rationale: fieldcraft is preparation, not courage.",
    ],
    4: [
        "Hook: two teachers, one performance and one textbook, neither the real thing.",
        "Mechanism: what the approved lessons actually establish about recognition.",
        "Counter: law and fear separated - Umbridge's legislation vs Greyback.",
        "Practice: test the claim, not the stereotype.",
        "Failure cases: private fear (the Grim) steering choices unchecked.",
        "Rationale: defence that teaches prejudice is not defence.",
    ],
    5: [
        "Hook: three curses, one life sentence - law material.",
        "Mechanism: Imperius demonstrated and resisted - demonstration material.",
        "Counter: recognition before response; constant vigilance.",
        "Practice: identify the curse, not cast it.",
        "Failure cases: no countercurse, no blocking, one survivor.",
        "Rationale: knowing the words is not the same as being able to cast them.",
    ],
    6: [
        "Hook: Expelliarmus opens the club and ends the duel with Voldemort.",
        "Mechanism: Stupefy's uneven record against armour and size.",
        "Counter: the Shield Charm's floor and ceiling.",
        "Practice: partner counts, flying wands, a controlled stop.",
        "Failure cases: spell rebound, wrong target, own-side risk.",
        "Rationale: proportion - a basic spell is not a weak one.",
    ],
    7: [
        "Hook: the Ministry stops at countercurses; Moody refuses.",
        "Mechanism: recognition before response - you cannot fight what you have not seen.",
        "Counter: hex-deflection drilled until it bruises.",
        "Practice: match the response to the attack, not to a list.",
        "Failure cases: theory-only syllabus; paper counters meeting a real jinx.",
        "Rationale: detection and concealment are the quiet half of defence.",
    ],
    8: [
        "Hook: the Fidelius Charm hides a house, then fails through a person.",
        "Mechanism: Protego at classroom, hall and castle scale.",
        "Counter: the Patronus under threat, not in a bright room.",
        "Practice: one spell, three scales, one cost.",
        "Failure cases: a Secret-Keeper who speaks; a shield past its rating.",
        "Rationale: protective magic under pressure is a study of people.",
    ],
}


def _ascii_form(value: str) -> str:
    """Map curly punctuation to ASCII without changing length, so match
    indices still address the raw chunk text."""
    return (
        value.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )


def quote_for(text: str, needle: str) -> str:
    """Verbatim whole-sentence slice at `needle`, with a word-window fallback."""
    pattern = re.compile(
        r"\s+".join(re.escape(word) for word in _ascii_form(needle).split()),
        re.IGNORECASE,
    )
    match = pattern.search(_ascii_form(text))
    if match is None:
        raise ValueError(f"anchor not found: {needle!r}")
    idx, end = match.start(), match.end()
    s, e = idx, end
    while s > 0 and not text[s - 1].isspace():
        s -= 1
    while e < len(text) and not text[e].isspace():
        e += 1
    sent_end = {".", "!", "?", ":"}
    left = s
    while left > 0 and text[left - 1] not in sent_end:
        left -= 1
    while left < s and (text[left].isspace() or text[left] in "\u201d\""):
        left += 1
    right = e
    limit = min(len(text), e + 420)
    while right < limit and text[right - 1] not in sent_end:
        right += 1
    if right < len(text) and text[right] == "\u201d" and text[right - 1] in sent_end:
        right += 1
    if right >= limit and right < len(text) and not text[right].isspace():
        while right > e and not text[right - 1].isspace():
            right -= 1
    candidate = text[left:right]
    if 3 <= len(candidate.split()) <= 90 and len(candidate) <= 480:
        return candidate
    # Long sentence: take a centred word window, still a verbatim substring.
    words = list(re.finditer(r"\S+", text))
    hit = next((i for i, w in enumerate(words) if w.start() <= idx < w.end()), 0)
    lo, hi = max(0, hit - 12), min(len(words), hit + 18)
    while hi - lo > 40:
        lo += 1
    return text[words[lo].start():words[hi - 1].end()]


def concept_from_seed(seed: dict) -> Concept:
    aliases = tuple(a for a in seed.get("aliases", ()) if a.lower() != "various")
    return Concept(
        concept_id=seed["concept_id"],
        subject=seed["subject"],
        kind=seed["kind"],
        title=seed["title"],
        aliases=aliases,
    )


def reference_from_seed(seed: dict) -> ReferenceLink | None:
    ref = seed.get("reference")
    return ReferenceLink(**ref) if ref else None


def main() -> int:
    out = REPO / "data/subjects/dada"
    pack = load_subject_pack(out)
    if pack.manifest.status == "published" and "--force" not in sys.argv:
        print(
            f"{out} holds a published pack; pass --force to rebuild it as a draft",
            file=sys.stderr,
        )
        return 1
    seeds = {
        s["concept_id"]: s
        for s in (
            json.loads(line)
            for line in (out / "seeds.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    chunks = {c.id: c for c in load_chunks(REPO / "data/chunks.jsonl")}

    topics = {t.topic_id: t for t in pack.topics}
    for topic_id, title in TOPICS.items():
        topics.setdefault(
            topic_id, Topic(topic_id=topic_id, subject="dada", title=title)
        )
    concepts = {c.concept_id: c for c in pack.concepts}
    materials = {m.material_id: m for m in pack.materials}

    review_rows: list[dict] = []

    for spec in MATERIALS:
        text = " ".join(spec["text"].split())
        cited = CITE_RE.findall(text)
        if len(cited) != len(set(cited)):
            # A repeat is allowed in prose, but the ref list is deduped.
            cited = list(dict.fromkeys(cited))
        missing = [c for c in cited if c not in spec["cites"]]
        extra = [c for c in spec["cites"] if c not in cited]
        if missing or extra:
            print(
                f"{spec['material_id']}: cite mismatch missing={missing} extra={extra}",
                file=sys.stderr,
            )
            return 1
        seed = seeds[spec["concept"]]
        refs = []
        for cid in cited:
            chunk = chunks.get(cid)
            if chunk is None:
                print(f"{spec['material_id']}: chunk {cid} not in corpus", file=sys.stderr)
                return 1
            try:
                quote = quote_for(chunk.text, spec["cites"][cid])
            except ValueError as exc:
                print(f"{spec['material_id']} {cid}: {exc}", file=sys.stderr)
                return 1
            refs.append(
                SourceRef(
                    chunk_id=cid,
                    book=chunk.metadata.book_num,
                    chapter=chunk.metadata.chapter_num,
                    quote=quote,
                    text_hash=chunk_text_hash(chunk.text),
                    index_text_hash=INDEX_HASH,
                )
            )
        reference = reference_from_seed(seed)
        materials[spec["material_id"]] = Material(
            material_id=spec["material_id"],
            subject="dada",
            topic=spec["topic"],
            concept=spec["concept"],
            kind=seed["kind"],
            text=text,
            source_refs=refs,
            references=[reference] if reference else [],
            review_status="draft",
        )
        concepts[spec["concept"]] = concept_from_seed(seed)
        review_rows.append(
            {
                "unit": spec["unit"],
                "material_id": spec["material_id"],
                "material": materials[spec["material_id"]],
            }
        )

    pack = SubjectPack(
        manifest=PackManifest(
            subject="dada",
            tier="owl",
            version=VERSION,
            status="draft",
            built_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            index_text_hash=INDEX_HASH,
        ),
        topics=sorted(topics.values(), key=lambda t: t.topic_id),
        concepts=sorted(concepts.values(), key=lambda c: c.concept_id),
        materials=sorted(materials.values(), key=lambda m: m.material_id),
    )

    result = validate_pack(pack, chunks, INDEX_HASH)
    print(
        f"validate: ok={result.ok} materials={len(pack.materials)} "
        f"concepts={len(pack.concepts)} errors={len(result.errors)} "
        f"warnings={len(result.warnings)}"
    )
    for err in result.errors[:20]:
        print(f"  ERROR {err}")
    for warn in result.warnings:
        print(f"  warn  {warn}")
    if not result.ok:
        return 1

    write_subject_pack(pack, out)
    print(f"pack {pack.manifest.version} written to {out}")

    lines = [
        "# DADA materials review: Units 2-8",
        "",
        f"Pack {pack.manifest.version}, index hash `{INDEX_HASH}`. Every",
        "material is `review_status=draft` pending the maintainer's prose",
        "pass. Every quote below was reconstructed from the corpus at a",
        "hand-picked anchor phrase, then hash-checked by `validate_pack`.",
        "",
        "## Coverage",
        "",
        "| Unit | Materials | Concept | Refs |",
        "|---|---|---|---|",
    ]
    for row in review_rows:
        m = row["material"]
        lines.append(
            f"| {row['unit']} | `{m.material_id}` | `{m.concept}` | "
            f"{len(m.source_refs)} |"
        )
    lines += ["", f"Pack totals: {len(pack.materials)} materials, "
              f"{len(pack.concepts)} concepts, "
              f"{len(pack.topics)} topics.", ""]

    for unit in range(2, 9):
        rows = [r for r in review_rows if r["unit"] == unit]
        lines += [f"## Unit {unit}", ""]
        for row in rows:
            m: Material = row["material"]
            lines += [
                f"### `{m.material_id}`",
                "",
                f"Topic `{m.topic}` | concept `{m.concept}` | {len(m.source_refs)} refs",
                "",
                m.text,
                "",
            ]
            for ref in m.source_refs:
                q = " ".join(ref.quote.split())
                q = q.replace(" .", ".").replace(" ,", ",")
                lines.append(f"- `{ref.chunk_id}`: \"{q}\"")
            lines.append("")
        lines += ["Lesson assembly:", ""]
        for step in LESSON_MAP[unit]:
            lines.append(f"- {step}")
        lines.append("")

    lines += ["## References (attribution only, never load-bearing)", ""]
    seen_refs: set[str] = set()
    for row in review_rows:
        for ref in row["material"].references:
            if ref.url in seen_refs:
                continue
            seen_refs.add(ref.url)
            lines.append(
                f"- {ref.title} - {ref.url} ({ref.publisher}, accessed {ref.accessed})"
            )
    lines += [
        "",
        "## Checks",
        "",
        f"- `validate_pack`: ok={result.ok}; "
        f"{len(pack.materials)} materials, {len(pack.concepts)} concepts",
        "- every chunk text hash recomputed against the corpus",
        "- every quote a verbatim substring of its chunk",
        "- every ref book/chapter matched to chunk metadata",
        f"- index text hash `{INDEX_HASH}`",
        f"- warnings: {len(result.warnings)} (all `review_status=draft`)",
        "",
        "## Gaps found while authoring",
        "",
        "- Werewolf restraint needs `b3 c18` (Wolfsbane and the full moon)",
        "  and `b5 c22` (the bite has no cure); neither is an approved row.",
        "  Unit 4 therefore covers recognition, law and fear, not containment.",
        "- The Unbreakable Vow's explanation is in `b6 c02`, not the approved",
        "  `b6 c15`; Unit 5 does not make a claim the approved row cannot carry.",
        "- The b6 c09 strike candidate is overturned: `b6-c09-0029` is Snape's",
        "  defence doctrine and `b6-c09-0036` is a Shield Charm, both DADA.",
        "- The b6 rows' shared reason (\"Dumbledore's Army practical chapters\")",
        "  is wrong for book 6; relabel when the table is next touched.",
        "",
    ]
    (out / "UNITS_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"review notes: {out / 'UNITS_REVIEW.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
