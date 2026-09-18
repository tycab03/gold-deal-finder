import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.cashconverters.com.au/shop/jewellery-fashion/jewellery/necklaces-chains/necklace/003700174445"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def scrape_product(url):
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Get all visible page text
    text = soup.get_text(" ", strip=True)

    # Title
    title = soup.title.string.split("|")[0].strip()

    # Item number
    item_match = re.search(r"Item Number:\s*(\d+)", text)
    item_number = item_match.group(1) if item_match else None

    # Carat
    carat_match = re.search(r"Carat:\s*(\d+)", text)
    carat = int(carat_match.group(1)) if carat_match else None

    # Weight
    weight_match = re.search(r"Weight:\s*([\d.]+)G", text, re.IGNORECASE)
    weight = float(weight_match.group(1)) if weight_match else None

    # Price
    price_match = re.search(r"\$([\d,]+)\s*\.?\s*(\d{2})?", text)

    if price_match:
        dollars = price_match.group(1).replace(",", "")
        cents = price_match.group(2) or "00"
        price = float(f"{dollars}.{cents}")
    else:
        price = None

    return {
        "title": title,
        "price": price,
        "carat": carat,
        "weight": weight,
        "item_number": item_number,
        "url": url,
    }


if __name__ == "__main__":
    product = scrape_product(URL)

    print("\n=== CASH CONVERTERS PRODUCT ===")
    print(f"Title:       {product['title']}")
    print(f"Price:       ${product['price']:.2f}")
    print(f"Carat:       {product['carat']}ct")
    print(f"Weight:      {product['weight']:.2f}g")
    print(f"Item Number: {product['item_number']}")
    print(f"URL:         {product['url']}")