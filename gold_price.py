import json
from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# CONFIG
# ============================================================

TROY_OUNCE_TO_GRAMS = 31.1034768

API_URL = (
    "https://api.goldprice.dev/v1/prices"
    "?symbol=XAU-AUD-SPOT"
)

CACHE_FILE = Path("gold_price_cache.json")


# ============================================================
# CACHE
# ============================================================

def save_cached_price(price):

    data = {
        "price_per_gram": price,
        "updated": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
        )


def load_cached_price():

    if not CACHE_FILE.exists():
        return None

    try:

        with open(
            CACHE_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        return float(
            data["price_per_gram"]
        )

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):

        return None


# ============================================================
# GOLD PRICE
# ============================================================

def get_gold_price_per_gram():

    try:

        response = requests.get(
            API_URL,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        price_per_ounce = float(
            data["symbols"][0]["price"]
        )

        price_per_gram = (
            price_per_ounce
            / TROY_OUNCE_TO_GRAMS
        )

        # Save successful API result
        save_cached_price(
            price_per_gram
        )

        return price_per_gram

    except (
        requests.RequestException,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as error:

        cached_price = (
            load_cached_price()
        )

        if cached_price is not None:

            print()
            print(
                "Gold price API unavailable."
            )

            print(
                "Using last cached gold price:"
            )

            print(
                f"${cached_price:.2f} AUD/g"
            )

            return cached_price

        raise RuntimeError(
            "Gold price API is unavailable "
            "and no cached gold price exists."
        ) from error


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    price = (
        get_gold_price_per_gram()
    )

    print(
        f"24ct gold: "
        f"${price:.2f} AUD/g"
    )

    print(
        f"9ct gold:  "
        f"${price * 0.375:.2f} AUD/g"
    )