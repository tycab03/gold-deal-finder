import requests
from bs4 import BeautifulSoup

URL = "https://www.cashconverters.com.au/shop/jewellery-fashion/jewellery/necklaces-chains/necklace/003700174445"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(URL, headers=headers, timeout=10)

print(f"Status code: {response.status_code}")

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

print(f"Page title: {soup.title.string}")