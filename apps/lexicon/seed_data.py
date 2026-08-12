"""
apps/lexicon/seed_data.py — The v1 tasting vocabulary, as data.

Loaded by the ``seed_lexicon`` management command. Kept as a Python literal
rather than a JSON fixture so each entry can carry a comment explaining why it
is worded the way it is — the wording is the product here, and a bare fixture
would lose the reasoning the first time someone edited it.

Two principles run through all of it.

**Teach, do not test.** Every question carries `how_to_tell`: the physical
instruction, what to do with the glass or your mouth, and what sensation to
look for. Every option on a scale carries `guidance` saying how to know it is
this one and not the one beside it. "Medium" and "high" acidity is the whole
difficulty, and a label on its own teaches nobody. `why_it_matters` is the
second layer, available on tap, for what the answer says about the wine.

**The app does the deduction.** Descriptors are what a person can actually
smell — brioche, butter, vanilla — not what caused them. Each carries its
`origin` (primary, secondary, tertiary) and, where it points somewhere, an
`implies` code. The app sorts them into the framework and names the process.
Asking a taster to file their own descriptors under "secondary" or to answer
"did this go through malolactic conversion?" is asking them to already know
the thing they came to learn.

On provenance: the four-phase sequence, the primary/secondary/tertiary
framework and the structural components are the standard teaching method,
taught by every wine school and free to build on. The prompts and descriptors
below are written for this app. They are deliberately NOT a transcription of
any awarding body's published lexicon — see the IP note in PRD §11.
"""

from __future__ import annotations

from typing import TypedDict

from apps.core.enums import AromaOrigin, Control, Phase, WineType

# Annotated list[str] rather than list[WineType]: these land in a JSONField
# and in a TypedDict of plain strings, and list is invariant, so the enum type
# would not satisfy either.
WHITE_ISH: list[str] = [WineType.STILL_WHITE, WineType.SPARKLING]
RED_ISH: list[str] = [WineType.STILL_RED, WineType.FORTIFIED]
TANNIC: list[str] = [WineType.STILL_RED, WineType.ROSE, WineType.FORTIFIED]


class OptionSpec(TypedDict, total=False):
    """One seeded option, optionally with the descriptors beneath it."""

    code: str
    label: str
    guidance: str
    origin: str
    implies: str
    swatch: str
    wine_types: list[str]
    children: list["OptionSpec"]


class QuestionSpec(TypedDict, total=False):
    """One seeded question."""

    code: str
    phase: str
    prompt: str
    short: str
    how: str
    why: str
    control: str
    wine_types: list[str]
    options: list[OptionSpec]


class InferenceSpec(TypedDict):
    """One thing the app concludes from the descriptors chosen."""

    code: str
    label: str
    explanation: str


def _scale(*rungs: tuple[str, str, str]) -> list[OptionSpec]:
    """Build a scale from (code, label, guidance) triples."""
    return [
        {"code": code, "label": label, "guidance": guidance}
        for code, label, guidance in rungs
    ]


def _flat(*pairs: tuple[str, str]) -> list[OptionSpec]:
    """Build a flat option list from (code, label) pairs."""
    return [{"code": code, "label": label} for code, label in pairs]


# ———————————————————————————————————————————————————————————————
# The aroma and flavour tree
# ———————————————————————————————————————————————————————————————
# Grouped by what things smell LIKE, not by where they came from. A taster
# opens "Baking and dairy" because they can smell bread; they are not asked to
# know that bread means yeast, which means time on the lees. That is the app's
# job, and it does it from the `origin` and `implies` tags below.
#
# Each entry: (code, label, origin, implies).

type Descriptor = tuple[str, str, str, str]

AROMA_GROUPS: list[tuple[str, str, list[Descriptor]]] = [
    (
        "citrus",
        "Citrus",
        [
            ("grapefruit", "Grapefruit", AromaOrigin.PRIMARY, ""),
            ("lemon", "Lemon", AromaOrigin.PRIMARY, ""),
            ("lime", "Lime", AromaOrigin.PRIMARY, ""),
            ("orange_peel", "Orange peel", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "orchard_fruit",
        "Orchard fruit",
        [
            ("apple", "Apple", AromaOrigin.PRIMARY, ""),
            ("pear", "Pear", AromaOrigin.PRIMARY, ""),
            ("quince", "Quince", AromaOrigin.PRIMARY, ""),
            ("peach", "Peach", AromaOrigin.PRIMARY, ""),
            ("apricot", "Apricot", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "tropical_fruit",
        "Tropical fruit",
        [
            ("pineapple", "Pineapple", AromaOrigin.PRIMARY, ""),
            ("mango", "Mango", AromaOrigin.PRIMARY, ""),
            ("passion_fruit", "Passion fruit", AromaOrigin.PRIMARY, ""),
            # Banana is the giveaway for carbonic maceration — the smell most
            # people can name without being taught, pointing at a process most
            # people have never heard of. Exactly the trade this app wants.
            ("banana", "Banana", AromaOrigin.PRIMARY, "carbonic"),
        ],
    ),
    (
        "red_fruit",
        "Red fruit",
        [
            ("strawberry", "Strawberry", AromaOrigin.PRIMARY, ""),
            ("raspberry", "Raspberry", AromaOrigin.PRIMARY, ""),
            ("red_cherry", "Red cherry", AromaOrigin.PRIMARY, ""),
            ("redcurrant", "Redcurrant", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "black_fruit",
        "Black fruit",
        [
            ("blackberry", "Blackberry", AromaOrigin.PRIMARY, ""),
            ("blackcurrant", "Blackcurrant", AromaOrigin.PRIMARY, ""),
            ("black_cherry", "Black cherry", AromaOrigin.PRIMARY, ""),
            ("plum", "Plum", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "flowers",
        "Flowers",
        [
            ("elderflower", "Elderflower", AromaOrigin.PRIMARY, ""),
            ("rose", "Rose", AromaOrigin.PRIMARY, ""),
            ("violet", "Violet", AromaOrigin.PRIMARY, ""),
            ("honeysuckle", "Honeysuckle", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "green_things",
        "Green things",
        [
            ("green_pepper", "Green pepper", AromaOrigin.PRIMARY, ""),
            ("cut_grass", "Cut grass", AromaOrigin.PRIMARY, ""),
            ("tomato_leaf", "Tomato leaf", AromaOrigin.PRIMARY, ""),
            ("mint", "Mint", AromaOrigin.PRIMARY, ""),
            ("eucalyptus", "Eucalyptus", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "pepper_spice",
        "Pepper and spice",
        [
            ("black_pepper", "Black pepper", AromaOrigin.PRIMARY, ""),
            ("white_pepper", "White pepper", AromaOrigin.PRIMARY, ""),
            ("liquorice", "Liquorice", AromaOrigin.PRIMARY, ""),
        ],
    ),
    (
        "baking",
        "Bread and pastry",
        [
            ("bread_dough", "Bread dough", AromaOrigin.SECONDARY, "lees"),
            ("biscuit", "Biscuit", AromaOrigin.SECONDARY, "lees"),
            ("brioche", "Brioche", AromaOrigin.SECONDARY, "lees"),
            ("pastry", "Pastry", AromaOrigin.SECONDARY, "lees"),
        ],
    ),
    (
        "dairy",
        "Dairy",
        [
            ("butter", "Butter", AromaOrigin.SECONDARY, "malolactic"),
            ("cream", "Cream", AromaOrigin.SECONDARY, "malolactic"),
            ("yoghurt", "Yoghurt", AromaOrigin.SECONDARY, "malolactic"),
            ("cheese_rind", "Cheese rind", AromaOrigin.SECONDARY, "malolactic"),
        ],
    ),
    (
        "sweet_spice_wood",
        "Sweet spice and wood",
        [
            ("vanilla", "Vanilla", AromaOrigin.SECONDARY, "oak"),
            ("coconut", "Coconut", AromaOrigin.SECONDARY, "oak"),
            ("clove", "Clove", AromaOrigin.SECONDARY, "oak"),
            ("cedar", "Cedar", AromaOrigin.SECONDARY, "oak"),
            ("smoke", "Smoke", AromaOrigin.SECONDARY, "oak"),
            ("toast", "Toast", AromaOrigin.SECONDARY, "oak"),
        ],
    ),
    (
        "nuts_caramel",
        "Nuts and caramel",
        [
            ("almond", "Almond", AromaOrigin.TERTIARY, "oxidative"),
            ("hazelnut", "Hazelnut", AromaOrigin.TERTIARY, "oxidative"),
            ("caramel", "Caramel", AromaOrigin.TERTIARY, "oxidative"),
            ("toffee", "Toffee", AromaOrigin.TERTIARY, "oxidative"),
        ],
    ),
    (
        "dried_fruit",
        "Dried and cooked fruit",
        [
            ("dried_apricot", "Dried apricot", AromaOrigin.TERTIARY, "bottle_age"),
            ("marmalade", "Marmalade", AromaOrigin.TERTIARY, "bottle_age"),
            ("cooked_plum", "Cooked plum", AromaOrigin.TERTIARY, "bottle_age"),
            ("fig", "Fig", AromaOrigin.TERTIARY, "bottle_age"),
            ("raisin", "Raisin", AromaOrigin.TERTIARY, "bottle_age"),
        ],
    ),
    (
        "earth_forest",
        "Earth and forest",
        [
            ("mushroom", "Mushroom", AromaOrigin.TERTIARY, "bottle_age"),
            ("forest_floor", "Forest floor", AromaOrigin.TERTIARY, "bottle_age"),
            ("leather", "Leather", AromaOrigin.TERTIARY, "bottle_age"),
            ("tobacco", "Tobacco", AromaOrigin.TERTIARY, "bottle_age"),
            ("honey", "Honey", AromaOrigin.TERTIARY, "bottle_age"),
            ("petrol", "Petrol", AromaOrigin.TERTIARY, "bottle_age"),
        ],
    ),
]


def _aroma_options() -> list[OptionSpec]:
    """Build the aroma tree, tags and all."""
    return [
        {
            "code": code,
            "label": label,
            "children": [
                {
                    "code": d_code,
                    "label": d_label,
                    "origin": origin,
                    "implies": implies,
                }
                for d_code, d_label, origin, implies in descriptors
            ],
        }
        for code, label, descriptors in AROMA_GROUPS
    ]


# ———————————————————————————————————————————————————————————————
# What the app concludes
# ———————————————————————————————————————————————————————————————
# Fired by the `implies` tags above. Every one of these was, in the previous
# version of this app, a question the taster was asked. That was backwards.

INFERENCES: list[InferenceSpec] = [
    {
        "code": "lees",
        "label": "Time on the lees",
        "explanation": (
            "Bread, biscuit and pastry come from the wine resting on its spent "
            "yeast after fermentation. It is a deliberate choice, and it adds "
            "texture as well as smell."
        ),
    },
    {
        "code": "malolactic",
        "label": "Malolactic conversion",
        "explanation": (
            "Butter and cream mean the sharp malic acid of apples has been "
            "converted into softer lactic acid — the acid in milk. It is why "
            "the wine feels rounder than its acidity alone would suggest."
        ),
    },
    {
        "code": "oak",
        "label": "Oak",
        "explanation": (
            "Vanilla, clove, cedar and smoke are the barrel talking, not the "
            "grape. Coconut in particular tends to mean American oak; toast and "
            "smoke mean the barrel was charred inside."
        ),
    },
    {
        "code": "carbonic",
        "label": "Carbonic maceration",
        "explanation": (
            "Banana, and often bubblegum, come from fermentation starting "
            "inside whole uncrushed grapes. It makes soft, low-tannin reds "
            "meant to be drunk young."
        ),
    },
    {
        "code": "oxidative",
        "label": "Deliberate oxidation",
        "explanation": (
            "Almond, hazelnut and caramel mean the wine was given air on "
            "purpose during ageing. Distinct from a wine that has simply gone "
            "off — here it is the style, and the fruit is still there under it."
        ),
    },
    {
        "code": "bottle_age",
        "label": "Bottle age",
        "explanation": (
            "Mushroom, forest floor, leather, honey and petrol only arrive with "
            "years in the bottle. Finding them means the wine has history, and "
            "usually that it is at or near its peak."
        ),
    },
]


QUESTIONS: list[QuestionSpec] = [
    # ——— LOOK ———————————————————————————————————————————————
    {
        "code": "clarity",
        "phase": Phase.LOOK,
        "short": "Clarity",
        "prompt": "Clear or hazy?",
        "how": (
            "Hold the glass against something white and look through the wine, "
            "not at it. Clear means you can read print through the middle of "
            "the glass."
        ),
        "why": (
            "Haze can mean an unfined, unfiltered wine — a stylistic choice — "
            "or a fault. Note it now and let the nose settle the question."
        ),
        "control": Control.SINGLE,
        "options": [
            {
                "code": "clear",
                "label": "Clear",
                "guidance": "You can see straight through it.",
            },
            {
                "code": "hazy",
                "label": "Hazy",
                "guidance": "Cloudy or dull, like weak tea rather than glass.",
            },
        ],
    },
    {
        "code": "appearance_intensity",
        "phase": Phase.LOOK,
        "short": "Depth",
        "prompt": "How deep is the colour?",
        "how": (
            "Tilt the glass away from you over something white and look down "
            "through it. Judge the width of the watery rim at the edge, not the "
            "colour in the middle."
        ),
        "why": (
            "Depth hints at the grape, the climate and how long the juice sat "
            "on the skins. Thick-skinned grapes in warm places make deep wines."
        ),
        "control": Control.SCALE,
        "options": _scale(
            (
                "pale",
                "Pale",
                "A wide watery rim; the colour fades well before the edge.",
            ),
            (
                "medium",
                "Medium",
                "Colour holds most of the way out, with a narrow rim.",
            ),
            (
                "deep",
                "Deep",
                "Coloured right to the edge; you cannot see the stem through it.",
            ),
        ),
    },
    {
        "code": "colour",
        "phase": Phase.LOOK,
        "short": "Colour",
        "prompt": "What colour is it?",
        "how": (
            "Look at the middle of the wine, then at the rim — they are often "
            "different, and the rim moves first. Daylight if you can; candlelight "
            "makes everything look older than it is."
        ),
        "why": (
            "Colour moves with age in a predictable direction. Whites darken "
            "towards gold and amber; reds fade from purple through ruby and "
            "garnet towards brown. It is your first evidence of age."
        ),
        "control": Control.SINGLE,
        "options": [
            # Swatches are decoration; the label is the answer. Never rely on
            # the colour alone (PRD §8, accessibility).
            {
                "code": "lemon_green",
                "label": "Lemon-green",
                "guidance": "Green glints at the rim. Young, cool-climate, or both.",
                "swatch": "#dfe08a",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "lemon",
                "label": "Lemon",
                "guidance": "Straw yellow with no green and no orange. The commonest white.",
                "swatch": "#f2e08c",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "gold",
                "label": "Gold",
                "guidance": "Deeper yellow. Age, oak, sweetness or a warm place.",
                "swatch": "#e6c34a",
                "wine_types": [*WHITE_ISH, WineType.FORTIFIED],
            },
            {
                "code": "amber",
                "label": "Amber",
                "guidance": "Orange-brown. Considerable age, oxidation, or skin contact.",
                "swatch": "#c98a2b",
                "wine_types": [*WHITE_ISH, WineType.FORTIFIED],
            },
            {
                "code": "pink",
                "label": "Pink",
                "guidance": "Clear pink with no orange. A short time on the skins.",
                "swatch": "#f2a7bd",
                "wine_types": [WineType.ROSE, WineType.SPARKLING],
            },
            {
                "code": "salmon",
                "label": "Salmon",
                "guidance": "Pink leaning orange. Provence in style, or a little age.",
                "swatch": "#f2a07a",
                "wine_types": [WineType.ROSE, WineType.SPARKLING],
            },
            {
                "code": "orange",
                "label": "Orange",
                "guidance": "More orange than pink. Age, or a deliberately oxidative style.",
                "swatch": "#e08a4a",
                "wine_types": [WineType.ROSE],
            },
            {
                "code": "purple",
                "label": "Purple",
                "guidance": "Blue or violet at the rim. Almost always under three years old.",
                "swatch": "#5b1e6b",
                "wine_types": RED_ISH,
            },
            {
                "code": "ruby",
                "label": "Ruby",
                "guidance": "Clear red, like a cough sweet. No purple, no orange.",
                "swatch": "#8e1220",
                "wine_types": RED_ISH,
            },
            {
                "code": "garnet",
                "label": "Garnet",
                "guidance": "Red with an orange-brown rim. Several years in.",
                "swatch": "#7b2318",
                "wine_types": RED_ISH,
            },
            {
                "code": "tawny",
                "label": "Tawny",
                "guidance": "More brown than red. Old, or aged in contact with air.",
                "swatch": "#9c5426",
                "wine_types": RED_ISH,
            },
            {
                "code": "brown",
                "label": "Brown",
                "guidance": "Little red left. Very old, or oxidised past its best.",
                "swatch": "#5c3218",
            },
        ],
    },
    {
        "code": "mousse",
        "phase": Phase.LOOK,
        "short": "Bubbles",
        "prompt": "How are the bubbles?",
        "how": (
            "Watch a single stream rise from the bottom of the glass. Judge the "
            "size of the bubbles and how long the ring of foam lasts at the edge."
        ),
        "why": (
            "Fine, persistent bubbles usually mean a second fermentation in the "
            "bottle and time on the lees. Big, short-lived ones point at a "
            "faster tank method."
        ),
        "control": Control.SINGLE,
        "wine_types": [WineType.SPARKLING],
        "options": _scale(
            (
                "delicate",
                "Delicate",
                "Tiny bubbles in slow steady threads; barely a prickle.",
            ),
            (
                "creamy",
                "Creamy",
                "Fine bubbles that feel like foam rather than fizz.",
            ),
            (
                "aggressive",
                "Aggressive",
                "Big bubbles, loud on the tongue, gone quickly.",
            ),
        ),
    },
    # ——— SMELL ——————————————————————————————————————————————
    {
        "code": "condition",
        "phase": Phase.SMELL,
        "short": "Condition",
        "prompt": "Clean, or is something off?",
        "how": (
            "Smell before you swirl. Wet cardboard or damp cellar is cork "
            "taint. Vinegar or nail varnish is volatile acidity. Sherry notes "
            "in a young wine are oxidation. Boiled cabbage is reduction, and "
            "often blows off after a minute."
        ),
        "why": (
            "A faulty wine cannot be assessed, and going through the motions on "
            "one teaches you the wrong lesson. Say so first, then decide "
            "whether to carry on."
        ),
        "control": Control.SINGLE,
        "options": [
            {
                "code": "clean",
                "label": "Clean",
                "guidance": "Nothing musty, sour or chemical. Smells like wine.",
            },
            {
                "code": "faulty",
                "label": "Something is off",
                "guidance": "Wet cardboard, vinegar, nail varnish, or old sherry in a young wine.",
            },
        ],
    },
    {
        "code": "nose_intensity",
        "phase": Phase.SMELL,
        "short": "Intensity",
        "prompt": "How much is it giving?",
        "how": (
            "Smell once with the glass still, then swirl hard and smell again. "
            "Judge how far from the glass you can pick it up — at the rim, or "
            "halfway to your nose."
        ),
        "why": (
            "A wine that needs coaxing out of the glass is telling you about "
            "its concentration and its age. Pronounced aromatics point at "
            "certain grapes on their own."
        ),
        "control": Control.SCALE,
        "options": _scale(
            (
                "light",
                "Light",
                "You have to put your nose in the glass to find anything.",
            ),
            (
                "medium",
                "Medium",
                "Clear at the rim of the glass without leaning in.",
            ),
            ("pronounced", "Pronounced", "You could smell it across the table."),
        ),
    },
    {
        "code": "aromas",
        "phase": Phase.SMELL,
        "short": "Aromas",
        "prompt": "What can you smell?",
        "how": (
            "Swirl, then short sharp sniffs rather than one long one — your "
            "nose tires in seconds. Open a group that sounds close and pick "
            "everything you find. Name what it smells LIKE; sorting out where "
            "each one came from is our job, not yours."
        ),
        "why": (
            "This is the raw material for everything at the end. We sort what "
            "you pick into what the grape brought, what the winemaking added "
            "and what age has done, and show you the split when you finish."
        ),
        "control": Control.MULTI,
        "options": _aroma_options(),
    },
    # ——— TASTE ——————————————————————————————————————————————
    {
        "code": "sweetness",
        "phase": Phase.TASTE,
        "short": "Sweetness",
        "prompt": "How sweet is it?",
        "how": (
            "Sweetness registers on the tip of your tongue, in the first "
            "second. Take a small sip and notice that first moment before "
            "anything else arrives."
        ),
        "why": (
            "Do not confuse sweetness with ripe fruit. A wine can smell of jam "
            "and taste bone dry — the smell is fruit, the taste is sugar, and "
            "they are separate facts."
        ),
        "control": Control.SCALE,
        "options": _scale(
            ("dry", "Dry", "No sweetness at all on the tip of the tongue."),
            (
                "off_dry",
                "Off-dry",
                "A hint of sweetness, easy to miss; softens the acidity.",
            ),
            ("medium_dry", "Medium-dry", "Clearly sweet, but the acidity still leads."),
            (
                "medium_sweet",
                "Medium-sweet",
                "Sweet enough to notice first; a dessert wine's lighter end.",
            ),
            ("sweet", "Sweet", "Unmistakably sweet, syrupy, coats the tongue."),
        ),
    },
    {
        "code": "acidity",
        "phase": Phase.TASTE,
        "short": "Acidity",
        "prompt": "How much acidity?",
        "how": (
            "Swallow, then close your mouth and wait. Acidity is how much your "
            "mouth waters afterwards, and for how long. It is a feeling at the "
            "sides of the tongue, not a flavour."
        ),
        "why": (
            "Acidity is the clearest signal of where a wine grew. High acidity "
            "means a cooler place or an earlier pick; soft acidity means heat "
            "or a late harvest."
        ),
        "control": Control.SCALE,
        "options": _scale(
            (
                "low",
                "Low",
                "Mouth stays dry; the wine feels broad, soft, almost flat.",
            ),
            (
                "medium",
                "Medium",
                "A little watering that settles within a few seconds.",
            ),
            (
                "high",
                "High",
                "Your mouth floods and keeps going; you may wince slightly.",
            ),
        ),
    },
    {
        "code": "tannin",
        "phase": Phase.TASTE,
        "short": "Tannin",
        "prompt": "How much tannin?",
        "how": (
            "Tannin is texture, not taste. After swallowing, run your tongue "
            "over your front teeth and the inside of your cheeks. Tannin is the "
            "dry, grippy, suede-like drag — like over-stewed tea."
        ),
        "why": (
            "It comes from skins, pips, stems and oak, and it is what lets a "
            "red age. It is easy to mistake for acidity: acidity makes you "
            "water, tannin dries you out."
        ),
        "control": Control.SCALE,
        "wine_types": TANNIC,
        "options": _scale(
            (
                "low",
                "Low",
                "Barely any grip; the wine feels smooth and slips away.",
            ),
            (
                "medium",
                "Medium",
                "A noticeable drag on the gums that fades in a few seconds.",
            ),
            (
                "high",
                "High",
                "Your mouth feels stripped and furry; it lasts and lasts.",
            ),
        ),
    },
    {
        "code": "alcohol",
        "phase": Phase.TASTE,
        "short": "Alcohol",
        "prompt": "How much alcohol?",
        "how": (
            "Swallow, then breathe out gently through your mouth. Alcohol is "
            "the warmth at the back of your throat and the top of your chest. "
            "Do not look at the label first."
        ),
        "why": (
            "Alcohol comes from sugar, and sugar comes from sun. Higher alcohol "
            "usually means riper grapes, and riper grapes usually mean a warmer "
            "place or a later pick."
        ),
        "control": Control.SCALE,
        "options": _scale(
            (
                "low",
                "Low",
                "No warmth. Under about 11% — often German or Italian whites.",
            ),
            ("medium", "Medium", "Mild warmth, easy to overlook. Roughly 11–13.5%."),
            ("high", "High", "Real heat in the throat and chest. Above about 14%."),
        ),
    },
    {
        "code": "body",
        "phase": Phase.TASTE,
        "short": "Body",
        "prompt": "How does it feel in the mouth?",
        "how": (
            "Ignore flavour entirely and judge weight — how much of your mouth "
            "the wine seems to fill, and how thick it feels moving across your "
            "tongue. The milk test: skimmed, semi-skimmed, or double cream."
        ),
        "why": (
            "Body is the sum of alcohol, sugar, tannin and extract rather than "
            "an ingredient of its own. High alcohol nearly always means fuller "
            "body, which is a useful cross-check on the last answer."
        ),
        "control": Control.SCALE,
        "options": _scale(
            (
                "light",
                "Light",
                "Like skimmed milk or water. Leaves the mouth quickly.",
            ),
            ("medium", "Medium", "Like semi-skimmed. Present but not heavy."),
            (
                "full",
                "Full",
                "Like double cream. Coats the mouth and sits there.",
            ),
        ),
    },
    {
        "code": "flavour_intensity",
        "phase": Phase.TASTE,
        "short": "Flavour",
        "prompt": "How intense is the flavour?",
        "how": (
            "Hold a small sip and draw a little air through it, then judge how "
            "much flavour arrives. Separate from body — a wine can be light in "
            "weight and loud in flavour."
        ),
        "why": (
            "A wine that smells shy and tastes loud is worth noticing; so is "
            "the reverse. The gap between nose and palate is itself a piece of "
            "evidence."
        ),
        "control": Control.SCALE,
        "options": _scale(
            ("light", "Light", "You have to concentrate to name anything."),
            ("medium", "Medium", "Flavours are clear without being insistent."),
            (
                "pronounced",
                "Pronounced",
                "Flavour arrives immediately and fills the mouth.",
            ),
        ),
    },
    {
        "code": "flavours",
        "phase": Phase.TASTE,
        "short": "Flavours",
        "prompt": "What can you taste?",
        "how": (
            "Same vocabulary as the nose, on purpose. Take a sip, draw a little "
            "air through it, and breathe out through your nose — most of what "
            "you call taste happens there."
        ),
        "why": (
            "Whether the palate confirms or contradicts the nose is evidence in "
            "itself. Oak that shows on the nose but not the palate, for "
            "instance, usually means a short time in older barrels."
        ),
        "control": Control.MULTI,
        "options": _aroma_options(),
    },
    {
        "code": "finish",
        "phase": Phase.TASTE,
        "short": "Finish",
        "prompt": "How long does it last?",
        "how": (
            "Swallow and count. You are timing the flavour, not the burn of "
            "alcohol or the grip of tannin — those fade on their own schedule "
            "and are not the finish."
        ),
        "why": (
            "Length is one of the better indicators of quality, and one of the "
            "hardest to fake. Cheap wine tends to stop abruptly."
        ),
        "control": Control.SCALE,
        "options": _scale(
            ("short", "Short", "Gone within a couple of seconds."),
            ("medium", "Medium", "Holds for five to ten seconds, then fades."),
            ("long", "Long", "Still there after fifteen seconds or more."),
        ),
    },
    # ——— CONCLUDE ———————————————————————————————————————————
    {
        "code": "quality",
        "phase": Phase.CONCLUDE,
        "short": "Quality",
        "prompt": "How good is it?",
        "how": (
            "Weigh four things in this order: is it balanced — does anything "
            "stick out; how long is the finish; how intense is the flavour; and "
            "how many different things can you find in it."
        ),
        "why": (
            "This is not whether you enjoyed it. A wine can be excellent and "
            "not to your taste, and saying so is the skill being learned."
        ),
        "control": Control.SCALE,
        "options": _scale(
            ("faulty", "Faulty", "Undrinkable. A fault dominates everything else."),
            ("poor", "Poor", "Unbalanced or hollow. Something is clearly wrong."),
            (
                "acceptable",
                "Acceptable",
                "Correct and unexciting. Nothing wrong, nothing to say.",
            ),
            ("good", "Good", "Balanced, decent length, a few things going on."),
            (
                "very_good",
                "Very good",
                "Balanced with real length and complexity.",
            ),
            ("outstanding", "Outstanding", "Long, complex and balanced. Memorable."),
        ),
    },
    {
        "code": "readiness",
        "phase": Phase.CONCLUDE,
        "short": "Readiness",
        "prompt": "Is it ready?",
        "how": (
            "Compare the fruit against the structure. Hard tannin or searing "
            "acidity with the fruit hiding behind it means too young. Fruit "
            "faded and the structure left bare means too late."
        ),
        "why": (
            "Deciding when to open a bottle is the most practical thing this "
            "method gives you, and it comes straight out of the answers you "
            "have already given."
        ),
        "control": Control.SINGLE,
        "options": [
            {
                "code": "too_young",
                "label": "Too young",
                "guidance": "Structure dominates; the fruit is in there but shut down.",
            },
            {
                "code": "drink_or_keep",
                "label": "Drink now, will improve",
                "guidance": "Enjoyable today, but the parts have not knitted together yet.",
            },
            {
                "code": "drink_now",
                "label": "Drink now, not for keeping",
                "guidance": "At its best. Waiting will lose you fruit, not gain complexity.",
            },
            {
                "code": "too_old",
                "label": "Past its best",
                "guidance": "Fruit gone, structure bare, and the finish drops away.",
            },
        ],
    },
    {
        "code": "guess_climate",
        "phase": Phase.CONCLUDE,
        "short": "Climate",
        "prompt": "Cool, moderate or warm climate?",
        "how": (
            "Read it off your own answers rather than guessing. High acidity, "
            "lower alcohol, lighter body and tart or green fruit point cool. "
            "Soft acidity, high alcohol, full body and jammy fruit point warm."
        ),
        "why": (
            "Climate narrows the field faster than anything else, and it is the "
            "step that turns a description into a deduction."
        ),
        "control": Control.SINGLE,
        "options": [
            {
                "code": "cool",
                "label": "Cool",
                "guidance": "High acid, under 12.5%, green or tart red fruit.",
            },
            {
                "code": "moderate",
                "label": "Moderate",
                "guidance": "Balanced acid and alcohol; ripe but not jammy fruit.",
            },
            {
                "code": "warm",
                "label": "Warm",
                "guidance": "Soft acid, 14%+, cooked or jammy fruit, full body.",
            },
        ],
    },
    {
        "code": "guess_grape",
        "phase": Phase.CONCLUDE,
        "short": "Grape",
        "prompt": "Which grape?",
        "how": (
            "Work from structure first and flavour second — acidity, tannin and "
            "body rule most grapes out before you consider what it tastes of. "
            "Commit even when unsure: a wrong guess you can look back on "
            "teaches more than a blank."
        ),
        "why": (
            "This is the payoff. Whether you are right matters less than "
            "whether your reasoning was sound, and the journal keeps both so "
            "you can check."
        ),
        "control": Control.SINGLE,
        "options": [
            {
                "code": "chardonnay",
                "label": "Chardonnay",
                "guidance": "Medium acid, often oak or butter, orchard to tropical fruit.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "sauvignon_blanc",
                "label": "Sauvignon Blanc",
                "guidance": "High acid, no oak, grass, gooseberry, green pepper.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "riesling",
                "label": "Riesling",
                "guidance": "Very high acid, low alcohol, lime and green apple; petrol with age.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "chenin_blanc",
                "label": "Chenin Blanc",
                "guidance": "High acid, quince and apple, often a waxy or honeyed note.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "pinot_grigio",
                "label": "Pinot Grigio",
                "guidance": "Light, neutral, medium acid, pear and lemon.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "viognier",
                "label": "Viognier",
                "guidance": "Low acid, full body, high alcohol, apricot and blossom.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "albarino",
                "label": "Albariño",
                "guidance": "High acid, light body, citrus and a saline edge.",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "cabernet_sauvignon",
                "label": "Cabernet Sauvignon",
                "guidance": "High tannin, blackcurrant, cedar, often a green pepper note.",
                "wine_types": TANNIC,
            },
            {
                "code": "merlot",
                "label": "Merlot",
                "guidance": "Medium tannin, plum and black cherry, softer than Cabernet.",
                "wine_types": TANNIC,
            },
            {
                "code": "pinot_noir",
                "label": "Pinot Noir",
                "guidance": "Pale, low tannin, high acid, red cherry; forest floor with age.",
                "wine_types": TANNIC,
            },
            {
                "code": "syrah",
                "label": "Syrah",
                "guidance": "Deep, medium-high tannin, black pepper and blackberry.",
                "wine_types": TANNIC,
            },
            {
                "code": "grenache",
                "label": "Grenache",
                "guidance": "High alcohol, low-medium tannin, strawberry and dried herbs.",
                "wine_types": TANNIC,
            },
            {
                "code": "tempranillo",
                "label": "Tempranillo",
                "guidance": "Medium everything, red fruit, usually vanilla and coconut oak.",
                "wine_types": TANNIC,
            },
            {
                "code": "sangiovese",
                "label": "Sangiovese",
                "guidance": "High acid, high tannin, sour cherry and tomato leaf.",
                "wine_types": TANNIC,
            },
            {
                "code": "nebbiolo",
                "label": "Nebbiolo",
                "guidance": "Pale but ferociously tannic, high acid, rose and tar.",
                "wine_types": TANNIC,
            },
            {
                "code": "malbec",
                "label": "Malbec",
                "guidance": "Deep purple, plush tannin, plum and violet.",
                "wine_types": TANNIC,
            },
            {
                "code": "other",
                "label": "Something else",
                "guidance": "Nothing on this list fits.",
            },
            {
                "code": "no_idea",
                "label": "No idea",
                "guidance": "Honest, and better than a random pick.",
            },
        ],
    },
    {
        "code": "guess_origin",
        "phase": Phase.CONCLUDE,
        "short": "Origin",
        "prompt": "Old World or New?",
        "how": (
            "A rough split, and a useful one. Earthy, savoury, restrained and "
            "higher in acid tends towards Europe. Fruit-forward, riper and "
            "higher in alcohol tends away from it."
        ),
        "why": (
            "It is the same evidence as the climate answer read a different "
            "way, and it is usually the last thing that narrows a guess to a "
            "region."
        ),
        "control": Control.SINGLE,
        "options": [
            {
                "code": "old_world",
                "label": "Old World",
                "guidance": "Europe. Earth and savour before fruit; higher acid, lower alcohol.",
            },
            {
                "code": "new_world",
                "label": "New World",
                "guidance": "Everywhere else. Fruit first, riper, fuller, more alcohol.",
            },
            {
                "code": "unsure",
                "label": "Could go either way",
                "guidance": "The signals are mixed. Say so rather than flipping a coin.",
            },
        ],
    },
    {
        "code": "confidence",
        "phase": Phase.CONCLUDE,
        "short": "Confidence",
        "prompt": "How sure are you?",
        "how": "No technique here — just say honestly how much you would bet on it.",
        "why": (
            "Recorded so you can look back and see whether your confidence "
            "tracks your accuracy. For most people, at first, it does not — and "
            "noticing that is worth more than being right."
        ),
        "control": Control.SCALE,
        "options": _scale(
            (
                "guessing",
                "Guessing",
                "You picked something because the box needed filling.",
            ),
            ("unsure", "Unsure", "One or two things fit; the rest is hope."),
            ("fairly_sure", "Fairly sure", "The structure and the flavours agree."),
            (
                "confident",
                "Confident",
                "You would say it out loud in a room of people.",
            ),
        ),
    },
]
