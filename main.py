from gold_price import get_gold_price_per_gram

GOLD_PURITY = {
    "9ct": 0.375,
    "14ct": 0.585,
    "18ct": 0.750,
    "22ct": 0.916,
    "24ct": 0.999,
}


def calculate_melt_value(weight, purity, gold_price):
    pure_gold_weight = weight * purity
    return pure_gold_weight * gold_price


def calculate_premium(price, melt_value):
    return ((price / melt_value) - 1) * 100


print("=== GOLD DEAL FINDER ===")

# Automatically retrieve current gold price
gold_price = get_gold_price_per_gram()

print(f"Current 24ct gold price: ${gold_price:.2f} AUD/g")
print(f"Current 9ct gold value: ${gold_price * 0.375:.2f} AUD/g")

weight = float(input("\nJewellery weight (grams): "))
price = float(input("Listing price: $"))

purity = GOLD_PURITY["9ct"]

melt_value = calculate_melt_value(
    weight,
    purity,
    gold_price
)

premium = calculate_premium(price, melt_value)

print("\n--- RESULTS ---")
print(f"Weight: {weight:.2f}g")
print(f"9ct pure gold equivalent: {weight * purity:.2f}g")
print(f"Listing price: ${price:.2f}")
print(f"Theoretical melt value: ${melt_value:.2f}")
difference = price - melt_value

print(f"Gold value: ${melt_value:.2f}")
print(f"Difference: ${difference:+.2f}")
print(f"Price vs gold value: {premium:+.1f}%")

if premium <= 0:
    print("Rating:  BELOW MELT VALUE")
elif premium <= 10:
    print("Rating:  EXCELLENT")
elif premium <= 20:
    print("Rating:  GOOD")
elif premium <= 35:
    print("Rating:  FAIR")
else:
    print("Rating:  EXPENSIVE")