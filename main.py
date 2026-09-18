# Gold Deal Finder
# Finds second-hand jewellery priced close to its underlying gold value.

GOLD_24CT_PRICE_PER_GRAM = 0.0  # We will automate this later

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

gold_price = float(input("Current 24ct gold price (AUD per gram): $"))
weight = float(input("Jewellery weight (grams): "))
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
print(f"9ct gold content: {weight * purity:.2f}g pure gold")
print(f"Listing price: ${price:.2f}")
print(f"Theoretical melt value: ${melt_value:.2f}")
print(f"Premium over gold value: {premium:.1f}%")