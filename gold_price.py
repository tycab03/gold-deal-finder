import requests

TROY_OUNCE_TO_GRAMS = 31.1034768

API_URL = "https://api.goldprice.dev/v1/prices?symbol=XAU-AUD-SPOT"


def get_gold_price_per_gram():
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()

    data = response.json()

    price_per_ounce = float(data["symbols"][0]["price"])
    price_per_gram = price_per_ounce / TROY_OUNCE_TO_GRAMS

    return price_per_gram


if __name__ == "__main__":
    price = get_gold_price_per_gram()

    print(f"24ct gold: ${price:.2f} AUD/g")
    print(f"9ct gold:  ${price * 0.375:.2f} AUD/g")