"""
apps/lexicon/seed_data.py — The v1 tasting vocabulary, as data.

Loaded by the ``seed_lexicon`` management command. Kept as a Python literal
rather than a JSON fixture so each entry can carry a comment explaining why it
is worded the way it is — the wording is the product here, and a bare fixture
would lose the reasoning the first time someone edited it.

On provenance: the four-phase sequence, the primary/secondary/tertiary aroma
framework and the structural components are the standard teaching method,
taught by every wine school and free to build on. The prompts and descriptors
below are written for this app. They are deliberately NOT a transcription of
any awarding body's published lexicon — see the IP note in PRD §11 — which
also means they can be tuned for a phone screen rather than a printed sheet.

Editing this file only changes what a *new* lexicon version seeds. Correcting
a published version is an admin edit; replacing one is a new version, because
sessions record which version they were taken against.
"""

from __future__ import annotations

from typing import TypedDict

from apps.core.enums import Control, Phase, WineType

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
    swatch: str
    wine_types: list[str]
    children: list["OptionSpec"]


class QuestionSpec(TypedDict, total=False):
    """One seeded question."""

    code: str
    phase: str
    prompt: str
    help: str
    control: str
    wine_types: list[str]
    options: list[OptionSpec]


def _flat(*pairs: tuple[str, str]) -> list[OptionSpec]:
    """Build a flat option list from (code, label) pairs."""
    return [{"code": code, "label": label} for code, label in pairs]


def _nested(tree: dict[str, tuple[str, list[tuple[str, str]]]]) -> list[OptionSpec]:
    """Build a one-level option tree from {code: (label, [(code, label)])}.

    The shape mirrors how the method teaches a taster to narrow in: open a
    broad category, then pick the specific descriptor (PRD §6.3).
    """
    return [
        {
            "code": code,
            "label": label,
            "children": [
                {"code": child_code, "label": child_label}
                for child_code, child_label in children
            ],
        }
        for code, (label, children) in tree.items()
    ]


# The aroma tree. Used twice — once on the nose, once on the palate — because
# a taster names what they smell and what they taste from the same vocabulary,
# and because comparing the two sets is itself part of the method.
AROMA_TREE: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "citrus": (
        "Citrus fruit",
        [
            ("grapefruit", "Grapefruit"),
            ("lemon", "Lemon"),
            ("lime", "Lime"),
            ("orange_peel", "Orange peel"),
        ],
    ),
    "green_fruit": (
        "Green fruit",
        [
            ("apple", "Apple"),
            ("pear", "Pear"),
            ("gooseberry", "Gooseberry"),
            ("quince", "Quince"),
        ],
    ),
    "stone_fruit": (
        "Stone fruit",
        [
            ("peach", "Peach"),
            ("apricot", "Apricot"),
            ("nectarine", "Nectarine"),
        ],
    ),
    "tropical_fruit": (
        "Tropical fruit",
        [
            ("pineapple", "Pineapple"),
            ("mango", "Mango"),
            ("passion_fruit", "Passion fruit"),
            ("banana", "Banana"),
        ],
    ),
    "red_fruit": (
        "Red fruit",
        [
            ("strawberry", "Strawberry"),
            ("raspberry", "Raspberry"),
            ("red_cherry", "Red cherry"),
            ("redcurrant", "Redcurrant"),
        ],
    ),
    "black_fruit": (
        "Black fruit",
        [
            ("blackberry", "Blackberry"),
            ("blackcurrant", "Blackcurrant"),
            ("black_cherry", "Black cherry"),
            ("plum", "Plum"),
        ],
    ),
    "floral": (
        "Floral",
        [
            ("elderflower", "Elderflower"),
            ("rose", "Rose"),
            ("violet", "Violet"),
            ("honeysuckle", "Honeysuckle"),
        ],
    ),
    "herbaceous": (
        "Herbaceous",
        [
            ("green_pepper", "Green pepper"),
            ("grass", "Grass"),
            ("tomato_leaf", "Tomato leaf"),
            ("asparagus", "Asparagus"),
        ],
    ),
    "herbal": (
        "Herbal",
        [
            ("mint", "Mint"),
            ("eucalyptus", "Eucalyptus"),
            ("fennel", "Fennel"),
            ("dill", "Dill"),
        ],
    ),
    "spice": (
        "Spice",
        [
            ("black_pepper", "Black pepper"),
            ("white_pepper", "White pepper"),
            ("liquorice", "Liquorice"),
        ],
    ),
}

SECONDARY_TREE: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "yeast": (
        "Yeast and lees",
        [
            ("biscuit", "Biscuit"),
            ("bread_dough", "Bread dough"),
            ("brioche", "Brioche"),
            ("pastry", "Pastry"),
        ],
    ),
    "malolactic": (
        "Malolactic",
        [
            ("butter", "Butter"),
            ("cream", "Cream"),
            ("cheese", "Cheese rind"),
        ],
    ),
    "oak": (
        "Oak",
        [
            ("vanilla", "Vanilla"),
            ("coconut", "Coconut"),
            ("clove", "Clove"),
            ("cedar", "Cedar"),
            ("smoke", "Smoke"),
            ("charred_wood", "Charred wood"),
        ],
    ),
}

TERTIARY_TREE: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "oxidative": (
        "Deliberate oxidation",
        [
            ("almond", "Almond"),
            ("hazelnut", "Hazelnut"),
            ("caramel", "Caramel"),
            ("toffee", "Toffee"),
        ],
    ),
    "fruit_development": (
        "Fruit development",
        [
            ("dried_apricot", "Dried apricot"),
            ("marmalade", "Marmalade"),
            ("cooked_plum", "Cooked plum"),
            ("fig", "Fig"),
        ],
    ),
    "bottle_age": (
        "Bottle age",
        [
            ("honey", "Honey"),
            ("petrol", "Petrol"),
            ("mushroom", "Mushroom"),
            ("leather", "Leather"),
            ("forest_floor", "Forest floor"),
            ("tobacco", "Tobacco"),
        ],
    ),
}

QUESTIONS: list[QuestionSpec] = [
    # ——— LOOK ———————————————————————————————————————————————
    {
        "code": "clarity",
        "phase": Phase.LOOK,
        "prompt": "Clear or hazy?",
        "help": (
            "Haze can mean an unfined, unfiltered wine — a stylistic choice — "
            "or a fault. Note it now and let the nose settle the question."
        ),
        "control": Control.SINGLE,
        "options": _flat(("clear", "Clear"), ("hazy", "Hazy")),
    },
    {
        "code": "appearance_intensity",
        "phase": Phase.LOOK,
        "prompt": "How deep is the colour?",
        "help": (
            "Tilt the glass and look at the rim. A watery rim means a paler "
            "wine than the middle suggests. Depth hints at grape, climate and "
            "extraction."
        ),
        "control": Control.SCALE,
        "options": _flat(("pale", "Pale"), ("medium", "Medium"), ("deep", "Deep")),
    },
    {
        "code": "colour",
        "phase": Phase.LOOK,
        "prompt": "What colour is it?",
        "help": (
            "Colour moves with age in a predictable direction — whites darken, "
            "reds fade from purple towards brown — so it is your first "
            "evidence of how old the wine is."
        ),
        "control": Control.SINGLE,
        "options": [
            # Swatches are decoration; the label is the answer. Never rely on
            # the colour alone (PRD §8, accessibility).
            {
                "code": "lemon_green",
                "label": "Lemon-green",
                "swatch": "#dfe08a",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "lemon",
                "label": "Lemon",
                "swatch": "#f2e08c",
                "wine_types": WHITE_ISH,
            },
            {
                "code": "gold",
                "label": "Gold",
                "swatch": "#e6c34a",
                "wine_types": [*WHITE_ISH, WineType.FORTIFIED],
            },
            {
                "code": "amber",
                "label": "Amber",
                "swatch": "#c98a2b",
                "wine_types": [*WHITE_ISH, WineType.FORTIFIED],
            },
            {
                "code": "pink",
                "label": "Pink",
                "swatch": "#f2a7bd",
                "wine_types": [WineType.ROSE, WineType.SPARKLING],
            },
            {
                "code": "salmon",
                "label": "Salmon",
                "swatch": "#f2a07a",
                "wine_types": [WineType.ROSE, WineType.SPARKLING],
            },
            {
                "code": "orange",
                "label": "Orange",
                "swatch": "#e08a4a",
                "wine_types": [WineType.ROSE],
            },
            {
                "code": "purple",
                "label": "Purple",
                "swatch": "#5b1e6b",
                "wine_types": RED_ISH,
            },
            {
                "code": "ruby",
                "label": "Ruby",
                "swatch": "#8e1220",
                "wine_types": RED_ISH,
            },
            {
                "code": "garnet",
                "label": "Garnet",
                "swatch": "#7b2318",
                "wine_types": RED_ISH,
            },
            {
                "code": "tawny",
                "label": "Tawny",
                "swatch": "#9c5426",
                "wine_types": RED_ISH,
            },
            {"code": "brown", "label": "Brown", "swatch": "#5c3218"},
        ],
    },
    {
        "code": "mousse",
        "phase": Phase.LOOK,
        "prompt": "How are the bubbles?",
        "help": (
            "Fine, persistent bubbles usually mean a second fermentation in "
            "the bottle. Big, short-lived ones point at a tank method."
        ),
        "control": Control.SINGLE,
        "wine_types": [WineType.SPARKLING],
        "options": _flat(
            ("delicate", "Delicate"),
            ("creamy", "Creamy"),
            ("aggressive", "Aggressive"),
        ),
    },
    # ——— SMELL ——————————————————————————————————————————————
    {
        "code": "condition",
        "phase": Phase.SMELL,
        "prompt": "Clean, or is something off?",
        "help": (
            "Wet cardboard is cork taint. Vinegar or nail varnish is volatile "
            "acidity. Sherry-like notes in a young wine are oxidation. Say so "
            "before describing anything else — a faulty wine cannot be "
            "assessed."
        ),
        "control": Control.SINGLE,
        "options": _flat(("clean", "Clean"), ("faulty", "Faulty")),
    },
    {
        "code": "nose_intensity",
        "phase": Phase.SMELL,
        "prompt": "How much is it giving?",
        "help": (
            "Judge before you swirl, then again after. A wine that needs "
            "coaxing out of the glass is telling you something about its age "
            "and its concentration."
        ),
        "control": Control.SCALE,
        "options": _flat(
            ("light", "Light"), ("medium", "Medium"), ("pronounced", "Pronounced")
        ),
    },
    {
        "code": "primary_aromas",
        "phase": Phase.SMELL,
        "prompt": "Primary — what came from the grape?",
        "help": (
            "Fruit, flowers, herbs and pepper: everything the grape brought "
            "with it, before anyone made a decision about it. Pick a category "
            "first, then narrow in."
        ),
        "control": Control.MULTI,
        "options": _nested(AROMA_TREE),
    },
    {
        "code": "secondary_aromas",
        "phase": Phase.SMELL,
        "prompt": "Secondary — what came from the winemaking?",
        "help": (
            "Bread and biscuit from yeast, butter and cream from malolactic "
            "conversion, vanilla and smoke from oak. These are choices someone "
            "made, not the grape speaking."
        ),
        "control": Control.MULTI,
        "options": _nested(SECONDARY_TREE),
    },
    {
        "code": "tertiary_aromas",
        "phase": Phase.SMELL,
        "prompt": "Tertiary — what came from age?",
        "help": (
            "Nuts and caramel from oxygen, dried fruit from time, mushroom and "
            "leather from years in the bottle. Finding these means the wine has "
            "history."
        ),
        "control": Control.MULTI,
        "options": _nested(TERTIARY_TREE),
    },
    # ——— TASTE ——————————————————————————————————————————————
    {
        "code": "sweetness",
        "phase": Phase.TASTE,
        "prompt": "How sweet is it?",
        "help": (
            "Sweetness is felt on the tip of the tongue. Do not confuse it "
            "with ripe fruit — a wine can taste of jam and still be bone dry."
        ),
        "control": Control.SCALE,
        "options": _flat(
            ("dry", "Dry"),
            ("off_dry", "Off-dry"),
            ("medium_dry", "Medium-dry"),
            ("medium_sweet", "Medium-sweet"),
            ("sweet", "Sweet"),
        ),
    },
    {
        "code": "acidity",
        "phase": Phase.TASTE,
        "prompt": "How much acidity?",
        "help": (
            "Acidity is the water in your mouth after you swallow. More "
            "watering, higher acidity — and usually a cooler place or an "
            "earlier pick."
        ),
        "control": Control.SCALE,
        "options": _flat(("low", "Low"), ("medium", "Medium"), ("high", "High")),
    },
    {
        "code": "tannin",
        "phase": Phase.TASTE,
        "prompt": "How much tannin?",
        "help": (
            "Tannin is texture, not taste: the drying grip on your gums and "
            "the inside of your cheeks. It comes from skins, pips, stems and "
            "oak."
        ),
        "control": Control.SCALE,
        "wine_types": TANNIC,
        "options": _flat(("low", "Low"), ("medium", "Medium"), ("high", "High")),
    },
    {
        "code": "alcohol",
        "phase": Phase.TASTE,
        "prompt": "How much alcohol?",
        "help": (
            "Warmth at the back of the throat after swallowing. Higher alcohol "
            "usually means riper grapes, and riper grapes usually mean a "
            "warmer place."
        ),
        "control": Control.SCALE,
        "options": _flat(("low", "Low"), ("medium", "Medium"), ("high", "High")),
    },
    {
        "code": "body",
        "phase": Phase.TASTE,
        "prompt": "How does it feel in the mouth?",
        "help": (
            "Body is weight — skimmed milk to double cream. It is the sum of "
            "alcohol, sugar, tannin and extract, not a separate ingredient."
        ),
        "control": Control.SCALE,
        "options": _flat(("light", "Light"), ("medium", "Medium"), ("full", "Full")),
    },
    {
        "code": "flavour_intensity",
        "phase": Phase.TASTE,
        "prompt": "How intense is the flavour?",
        "help": (
            "Judged separately from the nose. A wine can smell shy and taste "
            "loud, and the gap between the two is worth noticing."
        ),
        "control": Control.SCALE,
        "options": _flat(
            ("light", "Light"), ("medium", "Medium"), ("pronounced", "Pronounced")
        ),
    },
    {
        "code": "flavour_characteristics",
        "phase": Phase.TASTE,
        "prompt": "What do you taste?",
        "help": (
            "Same vocabulary as the nose, on purpose. Whether the palate "
            "confirms or contradicts what you smelled is itself evidence."
        ),
        "control": Control.MULTI,
        "options": _nested({**AROMA_TREE, **SECONDARY_TREE, **TERTIARY_TREE}),
    },
    {
        "code": "finish",
        "phase": Phase.TASTE,
        "prompt": "How long does it last?",
        "help": (
            "Time the flavour after you swallow, not the burn of alcohol or "
            "the grip of tannin. Length is one of the better indicators of "
            "quality."
        ),
        "control": Control.SCALE,
        "options": _flat(("short", "Short"), ("medium", "Medium"), ("long", "Long")),
    },
    # ——— CONCLUDE ———————————————————————————————————————————
    {
        "code": "quality",
        "phase": Phase.CONCLUDE,
        "prompt": "How good is it?",
        "help": (
            "Balance, length, intensity and complexity — in that order. Not "
            "whether you enjoyed it: a wine can be excellent and not to your "
            "taste."
        ),
        "control": Control.SCALE,
        "options": _flat(
            ("faulty", "Faulty"),
            ("poor", "Poor"),
            ("acceptable", "Acceptable"),
            ("good", "Good"),
            ("very_good", "Very good"),
            ("outstanding", "Outstanding"),
        ),
    },
    {
        "code": "readiness",
        "phase": Phase.CONCLUDE,
        "prompt": "Is it ready?",
        "help": (
            "Fruit fading and tannin still hard means too young. Fruit gone "
            "and structure hollow means too late."
        ),
        "control": Control.SINGLE,
        "options": _flat(
            ("too_young", "Too young"),
            ("drink_or_keep", "Drink now, will improve"),
            ("drink_now", "Drink now, not for keeping"),
            ("too_old", "Past its best"),
        ),
    },
    {
        "code": "guess_climate",
        "phase": Phase.CONCLUDE,
        "prompt": "Cool, moderate or warm climate?",
        "help": (
            "High acidity, lower alcohol and green or tart fruit point cool. "
            "Soft acidity, higher alcohol and jammy fruit point warm."
        ),
        "control": Control.SINGLE,
        "options": _flat(("cool", "Cool"), ("moderate", "Moderate"), ("warm", "Warm")),
    },
    {
        "code": "guess_grape",
        "phase": Phase.CONCLUDE,
        "prompt": "Which grape?",
        "help": (
            "Commit to an answer even when unsure — a wrong guess you can look "
            "back on teaches more than a blank."
        ),
        "control": Control.SINGLE,
        "options": [
            {"code": "chardonnay", "label": "Chardonnay", "wine_types": WHITE_ISH},
            {
                "code": "sauvignon_blanc",
                "label": "Sauvignon Blanc",
                "wine_types": WHITE_ISH,
            },
            {"code": "riesling", "label": "Riesling", "wine_types": WHITE_ISH},
            {"code": "chenin_blanc", "label": "Chenin Blanc", "wine_types": WHITE_ISH},
            {"code": "pinot_grigio", "label": "Pinot Grigio", "wine_types": WHITE_ISH},
            {"code": "viognier", "label": "Viognier", "wine_types": WHITE_ISH},
            {"code": "albarino", "label": "Albariño", "wine_types": WHITE_ISH},
            {
                "code": "cabernet_sauvignon",
                "label": "Cabernet Sauvignon",
                "wine_types": TANNIC,
            },
            {"code": "merlot", "label": "Merlot", "wine_types": TANNIC},
            {"code": "pinot_noir", "label": "Pinot Noir", "wine_types": TANNIC},
            {"code": "syrah", "label": "Syrah", "wine_types": TANNIC},
            {"code": "grenache", "label": "Grenache", "wine_types": TANNIC},
            {"code": "tempranillo", "label": "Tempranillo", "wine_types": TANNIC},
            {"code": "sangiovese", "label": "Sangiovese", "wine_types": TANNIC},
            {"code": "nebbiolo", "label": "Nebbiolo", "wine_types": TANNIC},
            {"code": "malbec", "label": "Malbec", "wine_types": TANNIC},
            {"code": "other", "label": "Something else"},
            {"code": "no_idea", "label": "No idea"},
        ],
    },
    {
        "code": "guess_origin",
        "phase": Phase.CONCLUDE,
        "prompt": "Old World or New?",
        "help": (
            "A rough split, and a useful one: earthy and restrained tends "
            "towards Europe, fruit-forward and generous tends away from it."
        ),
        "control": Control.SINGLE,
        "options": _flat(
            ("old_world", "Old World"),
            ("new_world", "New World"),
            ("unsure", "Could go either way"),
        ),
    },
    {
        "code": "winemaking",
        "phase": Phase.CONCLUDE,
        "prompt": "What was done to it?",
        "help": (
            "The clues you already collected on the nose and palate, stated as "
            "decisions someone made."
        ),
        "control": Control.MULTI,
        "options": _flat(
            ("oak", "Oak ageing"),
            ("malolactic", "Malolactic conversion"),
            ("lees", "Lees ageing"),
            ("skin_contact", "Skin contact"),
            ("carbonic", "Carbonic maceration"),
            ("botrytis", "Botrytis"),
            ("none_obvious", "Nothing obvious"),
        ),
    },
    {
        "code": "confidence",
        "phase": Phase.CONCLUDE,
        "prompt": "How sure are you?",
        "help": (
            "Recorded so you can look back and see whether your confidence "
            "tracks your accuracy. It usually does not, at first."
        ),
        "control": Control.SCALE,
        "options": _flat(
            ("guessing", "Guessing"),
            ("unsure", "Unsure"),
            ("fairly_sure", "Fairly sure"),
            ("confident", "Confident"),
        ),
    },
]
