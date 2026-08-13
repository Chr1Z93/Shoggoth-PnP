import json
from pathlib import Path
import requests
import sys
import uuid

# Config
TABOO_ID = 10  # FAQ 2.5 is 10

# Constants
MY_NAMESPACE = uuid.UUID("6ac6322a-82b1-4ef9-bb5f-8fa035179cc1")
CHAPTER = 1 if TABOO_ID < 11 else 2

# API URLs
CARD_DATA_API = f"https://api.arkham.build/v1/cache/cards/en"
TABOO_API = "https://api.arkham.build/v1/cache/taboo_sets_with_cards"
PACK_DATA_API = "https://api.arkham.build/v1/cache/metadata/en"  # language is always en for pack data


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


def get_taboo_card_ids():
    print("Fetching taboo card IDs...")
    card_ids = []
    try:
        response = requests.get(TABOO_API)
        response.raise_for_status()

        # Create a lookup map
        for taboo_list in response.json()["data"]["taboo_set"]:
            if taboo_list["id"] == TABOO_ID:
                for card in taboo_list["cards"]:
                    card_ids.append(card["code"])
                break

        print(f"Found {len(card_ids)} cards on the taboo list.")
        return card_ids

    except Exception as e:
        print(f"Error fetching taboo card IDs: {e}")
        sys.exit(1)


def update_ids():
    print(f"Updating IDs for Taboo '{TABOO_ID}'")
    taboo_card_ids = get_taboo_card_ids()
    card_data = load_card_data()

    # Create uuid map
    uuid_to_id = {}
    for card_id in taboo_card_ids:
        print(f"  Processing card {card_id}...")
        card = card_data.get(f"{card_id}-{TABOO_ID}")

        if card is None:
            print(f"    Skipping: Card data wasn't found")
            continue

        if "duplicate_of_code" in card:
            print(f"    Skipping: Card is a duplicate")
            continue

        card_chapter = card.get("chapter", 1)
        if card_chapter != CHAPTER:
            print(f"    Skipping: Card is not from chapter {CHAPTER}")
            continue

        short_id = card["id"][:-3]
        card_uuid = str(uuid.uuid5(MY_NAMESPACE, short_id))
        uuid_to_id[card_uuid] = f"{short_id}-t"

    update_shoggoth_project(uuid_to_id, f"Taboo{CHAPTER}.json")
    update_shoggoth_project(uuid_to_id, f"Taboo{CHAPTER}_de.json")
    update_shoggoth_project(uuid_to_id, f"Taboo{CHAPTER}_pl.json")


def update_shoggoth_project(uuid_to_id, filename):
    print(f"Updating {filename}...")
    script_path = Path(__file__).resolve()
    script_dir = script_path.parent
    project_path = script_dir / filename
    if not project_path.exists():
        print(f"File {filename} does not exist.")
        return

    with open(project_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)

    updated_count = 0
    cards = project_data.get("cards", [])

    if isinstance(cards, list):
        # Format: cards = [{id: ...}, ...]
        for card in cards:
            card_id = card.get("id")
            if card_id in uuid_to_id:
                new_id = uuid_to_id[card_id]
                if card_id != new_id:
                    card["id"] = new_id
                    updated_count += 1

    elif isinstance(cards, dict):
        # Format: cards = {uuid: {...}, ...}
        updated_cards = {}

        for card_id, card in cards.items():
            if card_id in uuid_to_id:
                new_id = uuid_to_id[card_id]
                updated_cards[new_id] = card
                updated_count += 1
            else:
                updated_cards[card_id] = card

        project_data["cards"] = updated_cards

    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, ensure_ascii=True, indent=4)

    print(f"Updated {updated_count} cards in {filename}.")


if __name__ == "__main__":
    update_ids()
