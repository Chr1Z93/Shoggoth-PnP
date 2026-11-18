import json
from pathlib import Path
import requests
import sys
import uuid

# Config
LOCALE = "de"
OUTPUT_FILE = "FetchResult.json"

# Constants
CHAPTER = 1
FIRST_PARALLEL_ID = 90001
LAST_PARALLEL_ID = 90097

# API URLs
CARD_DATA_API = f"https://api.arkham.build/v1/cache/cards/{LOCALE}"
PACK_DATA_API = "https://api.arkham.build/v1/cache/metadata/en"  # language is always en for pack data

# Strings to automatically replace in card text
REPLACEMENT_MAP = {
    # Ability triggers
    "[reaction]": "<reaction>",
    "[action]": "<action>",
    "[fast]": "<free>",
    "[free]": "<free>",
    # Tokens
    "[auto_fail]": "<auto_fail>",
    "[elder_sign]": "<elder_sign>",
    "[skull]": "<skull>",
    "[cultist]": "<cultist>",
    "[tablet]": "<tablet>",
    "[elder_thing]": "<elder_thing>",
    "[frost]": "<frost>",
    "[bless]": "<blessing>",
    "[curse]": "<curse>",
    # Traits
    "[[": "<t>",
    "]]": "</t>",
    # Classes
    "[guardian]": "<guardian>",
    "[seeker]": "<seeker>",
    "[rogue]": "<rogue>",
    "[mystic]": "<mystic>",
    "[survivor]": "<survivor>",
    # Keywords
    "<b>Revelation</b> -": "<rev>",
    "<b>Forced</b> -": "<for>",
}

# Mapping of pack codes to collection icon names
COLLECTION_ICON_OVERRIDES = {
    "rod": "read_or_die",
    "rtr": "read_tide_rising",
    "btb": "by_the_book",
    "aon": "all_or_nothing",
    "bad": "bad_blood",
    "otr": "on_the_road_again",
    "ltr": "laid_to_rest",
    "ptr": "path_of_the_righteous",
    "rop": "relics_of_the_past",
    "hfa": "hunting_for_answers",
    "pap": "pistols_and_pearls",
    "aof": "aura_of_faith",
    "enc": "enthralling_encore",
}


def load_card_data():
    print("Fetching card data...")
    card_data = {}
    try:
        response = requests.get(CARD_DATA_API)
        response.raise_for_status()

        # Create a lookup map
        for card in response.json()["data"]["all_card"]:
            card_data[card["id"]] = card

        return card_data

    except Exception as e:
        print(f"Error fetching card data: {e}")
        sys.exit(1)


def load_pack_data():
    print("Fetching pack data...")
    pack_data = {}
    try:
        response = requests.get(PACK_DATA_API)
        response.raise_for_status()

        # Create a lookup map
        for pack in response.json()["data"]["pack"]:
            pack_data[pack["code"]] = pack["cycle_code"]

        return pack_data

    except Exception as e:
        print(f"Error fetching pack data: {e}")
        sys.exit(1)


def build_shoggoth_card(item, pack_data):
    name = item.get("name") or item.get("real_name") or ""
    text = item.get("text") or item.get("real_text") or ""

    # Perform replacements
    for key, value in REPLACEMENT_MAP.items():
        text = text.replace(key, value)

    # Also replace the card's name in the text field with the tag
    text = text.replace(name, "<name>")
    card_type = item.get("type_code", "asset")
    front = {
        "text": text,
        "traits": item.get("real_traits") or item.get("traits") or "",
    }

    if LOCALE == "en":
        if item.get("is_unique"):
            front["name"] = "<unique><name>"

        front["type"] = card_type

        if card_type in ["asset", "event"]:
            front["cost"] = str(item.get("cost", "<dash>"))

        if card_type in ["asset", "event", "skill"]:
            front["level"] = str(item.get("xp"))

        front["collection_number"] = str(item.get("position", 0))

        # Work out the collection icon
        pack_code = item.get("pack_code", "unknown_pack")
        cycle_code = pack_data.get(pack_code, pack_code)
        icon_name = pack_code

        if pack_code in COLLECTION_ICON_OVERRIDES:
            # Use override if available
            icon_name = COLLECTION_ICON_OVERRIDES[pack_code]

        elif (
            not Path(f"./icons/{pack_code}.svg").exists()
            and Path(f"./icons/{cycle_code}.svg").exists()
        ):
            # Use cycle code icon if pack code icon doesn't exist
            icon_name = cycle_code

        front["collection_icon"] = (
            f'<image color="inverted" src="./icons/{icon_name}.svg">'
        )

        # Determine Release Year
        release_year = "202?"  # Default value if no match is found
        front["copyright"] = f"©  {release_year} FFG"

        if "illustrator" in item:
            front["illustrator"] = "Illus. " + item["illustrator"]

        # Classes
        if "restrictions" in item and "trait" in item["restrictions"]:
            front["classes"] = ["specialist"]
        elif "subtype_code" in item and item["subtype_code"] == "weakness":
            front["classes"] = ["weakness"]
        else:
            front["classes"] = []

            if "faction_code" in item:
                front["classes"].append(item["faction_code"])

            if "faction2_code" in item:
                front["classes"].append(item["faction2_code"])

            if "faction3_code" in item:
                front["classes"].append(item["faction3_code"])

        # Health & Sanity
        if item.get("health"):
            front["health"] = str(item["health"])
            if not front.get("sanity"):
                front["sanity"] = "<dash>"

        if item.get("sanity"):
            front["sanity"] = str(item["sanity"])
            if not front.get("health"):
                front["health"] = "<dash>"

        # Slots
        if item.get("real_slot"):
            slot = str(item["real_slot"]).strip().lower()
            front["slots"] = [slot]

        if card_type == "investigator":
            # Investigator stats
            for skill in ["willpower", "intellect", "combat", "agility"]:
                if item.get(f"skill_{skill}"):
                    front[skill] = str(item[f"skill_{skill}"])
        else:
            # Skill Icons
            skill_string = ""
            for skill in ["willpower", "intellect", "combat", "agility", "wild"]:
                if item.get(f"skill_{skill}"):
                    abbreviation = skill[0].upper() if skill != "wild" else "Q"
                    skill_string += abbreviation * item[f"skill_{skill}"]

            if skill_string != "":
                front["icons"] = skill_string

    # Translatable Fields
    fields = {
        "subtitle": item.get("subname") or item.get("real_subname"),
        "traits": item.get("traits") or item.get("real_traits"),
        "flavor_text": item.get("flavor") or item.get("real_flavor"),
    }

    for key, value in fields.items():
        if value is not None:
            front[key] = value

    # Handle Investigator backs
    if card_type == "investigator":
        back = {
            "type": "investigator_back",
            "text": (item.get("back_text") or item.get("real_back_text") or "").replace(
                name, "<name>"
            ),
            "flavor_text": (
                item.get("back_flavor") or item.get("real_back_flavor") or ""
            ).replace(name, "<name>"),
        }
    else:
        back = {"type": "player"}

    shoggoth_card = {
        "name": name,
        "id": f"{item['id']}",
        "front": front,
    }

    if LOCALE == "en":
        shoggoth_card["amount"] = item.get("deck_limit", 2)
        shoggoth_card["back"] = back
    else:
        shoggoth_card["back"] = {}

    return shoggoth_card


def build_project():
    print(f"Building project for Parallel Content with Locale '{LOCALE}'...")
    card_data = load_card_data()
    pack_data = load_pack_data()
    shoggoth_cards = []

    for card_id in range(FIRST_PARALLEL_ID, LAST_PARALLEL_ID + 1):
        print(f"  Processing card {card_id}...")
        card = card_data.get(str(card_id))

        if card is None:
            card = card_data.get(str(card_id) + "a")

            if card is None:
                print(f"    Skipping: Card data wasn't found")
                continue

            print(f"    Info: Fetching data for {str(card_id) + "a"} instead")

        if "duplicate_of_code" in card:
            print(f"    Skipping: Card is a duplicate")
            continue

        card_chapter = card.get("chapter", 1)
        if card_chapter != CHAPTER:
            print(f"    Skipping: Card is not from chapter {CHAPTER}")
            continue

        shoggoth_card = build_shoggoth_card(card, pack_data)
        shoggoth_cards.append(shoggoth_card)

    if len(shoggoth_cards) == 0:
        print("No matching cards found.")
        sys.exit(1)

    name = f"Parallel{CHAPTER}"

    # Build the project dictionary based on the locale
    if LOCALE == "en":
        project = {
            "name": name,
            "code": f"PP{CHAPTER}",
            "icon": "",
            "id": str(uuid.uuid4()),
            "cards": shoggoth_cards,
            "meta": {"dirty": []},
        }
    else:
        project = {
            "language": LOCALE,
            "project": name + ".json",
            "project_name": name,
            "cards": {
                card["id"]: {k: v for k, v in card.items() if k != "id"}
                for card in shoggoth_cards
            },
            "guides": [],
        }

    # Information that is always needed
    project["encounter_sets"] = []

    # Write the project to a JSON file
    script_path = Path(__file__).parent.resolve()
    output_file = script_path / OUTPUT_FILE
    output_file.write_text(
        json.dumps(project, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(project['cards'])} cards to {OUTPUT_FILE}")


if __name__ == "__main__":
    build_project()
