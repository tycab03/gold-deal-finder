from gold_price import get_gold_price_per_gram
from scraper import scrape_product


GOLD_PURITY = {
    9: 0.375,
    14: 0.585,
    18: 0.750,
    22: 0.916,
    24: 0.999,
}


def calculate_melt_value(weight, carat, gold_price):
    purity = GOLD_PURITY[carat]
    return weight * purity * gold_price


def calculate_percentage_difference(price, gold_value):
    return ((price / gold_value) - 1) * 100


print("=== GOLD DEAL FINDER ===")

url = input("Cash Converters product URL: ")

print("\nFetching product...")
product = scrape_product(url)

print("Fetching current gold price...")
gold_price = get_gold_price_per_gram()

melt_value = calculate_melt_value(
    product["weight"],
    product["carat"],
    gold_price
)

difference = product["price"] - melt_value

percentage_difference = calculate_percentage_difference(
    product["price"],
    melt_value
)


print("\n=== DEAL ANALYSIS ===")

print(f"Product:             {product['title']}")
print(f"Item Number:         {product['item_number']}")
print("---------------------------------------------")
print(f"Listing Price:       ${product['price']:,.2f}")
print(f"Weight:               {product['weight']:.2f}g")
print(f"Purity:               {product['carat']}ct")
print()
print(f"24ct Spot Price:      ${gold_price:.2f}/g")
print(f"{product['carat']}ct Gold Value/g:   "
      f"${gold_price * GOLD_PURITY[product['carat']]:.2f}/g")
print()
print(f"Gold Value:          ${melt_value:,.2f}")
print(f"Difference:          ${difference:+,.2f}")
print(f"Price vs Gold Value: {percentage_difference:+.1f}%")
print("---------------------------------------------")

if percentage_difference <= 0:
    print("Rating: BELOW GOLD VALUE")
elif percentage_difference <= 10:
    print("Rating: EXCELLENT")
elif percentage_difference <= 20:
    print("Rating: GOOD")
elif percentage_difference <= 35:
    print("Rating: FAIR")
else:
    print("Rating: EXPENSIVE")

print(f"\nURL: {product['url']}")