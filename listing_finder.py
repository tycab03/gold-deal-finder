import re
import time
import requests

from gold_price import get_gold_price_per_gram


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.cashconverters.com.au"

SEARCH_ENDPOINT = (
    BASE_URL
    + "/c3api/search/results"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# Gold purity values
SUPPORTED_CARATS = {
    9: 0.375,
    14: 0.585,
    18: 0.750,
    22: 0.916,
    24: 0.999,
}


# ============================================================
# EXTRACT CARAT FROM PRODUCT TITLE
# ============================================================

def extract_carat(title):
    """
    Extract gold carat from titles such as:

    9ct Yellow Gold Chain
    18CT Gold Ring
    14ct White Gold Pendant
    """

    match = re.search(
        r"\b(9|14|18|22|24)\s*ct\b",
        title,
        re.IGNORECASE
    )

    if match:
        return int(match.group(1))

    return None


# ============================================================
# EXTRACT WEIGHT FROM PRODUCT TITLE
# ============================================================

def extract_weight(title):
    """
    Extract weight from titles such as:

    Gold Bangle - 8.99G
    Gold Pendant 2.3G
    Gold Chain 12G
    """

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*[gG]\b",
        title
    )

    if not matches:
        return None

    # Usually the final gram value
    # in the title is the product weight.
    return float(matches[-1])


# ============================================================
# SEARCH CASH CONVERTERS API
# ============================================================

def search_cashies(
    query="9ct gold",
    page=1,
    number_of_results=24
):

    params = {
        "query": query,
        "page": page,
        "NumberOfResults": number_of_results,
    }

    response = requests.get(
        SEARCH_ENDPOINT,
        headers=HEADERS,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("WasSuccessful"):

        raise RuntimeError(
            "Cashies search failed: "
            + str(data.get("Message"))
        )

    product_list = (
        data["Value"]["ProductList"]
    )

    products = product_list[
        "ProductListItems"
    ]

    total = product_list[
        "ProductListItemCount"
    ]

    return products, total


# ============================================================
# FIND GOLD PRODUCTS
# ============================================================

def find_gold_candidates(
    query="9ct gold",
    pages=10,
    results_per_page=24
):

    candidates = []

    seen_codes = set()

    total = 0

    print(
        "=== CASHIES GOLD CANDIDATE FINDER ==="
    )

    print()

    print(
        f"Search: {query}"
    )

    print(
        f"Pages to scan: {pages}"
    )

    print()

    # --------------------------------------------------------
    # SCAN SEARCH PAGES
    # --------------------------------------------------------

    for page in range(
        1,
        pages + 1
    ):

        print(
            f"Fetching page "
            f"{page}/{pages}..."
        )

        try:

            products, total = search_cashies(
                query=query,
                page=page,
                number_of_results=results_per_page,
            )

        except Exception as error:

            print(
                f"  Error fetching page "
                f"{page}: {error}"
            )

            continue

        print(
            f"  API returned "
            f"{len(products)} products"
        )

        # ----------------------------------------------------
        # PROCESS PRODUCTS
        # ----------------------------------------------------

        for product in products:

            code = product.get(
                "Code"
            )

            # Skip products without code
            if not code:
                continue

            # Skip duplicates
            if code in seen_codes:
                continue

            seen_codes.add(code)

            title = product.get(
                "Title",
                ""
            )

            # Extract gold information
            carat = extract_carat(
                title
            )

            weight = extract_weight(
                title
            )

            # We need a recognised carat
            if carat not in SUPPORTED_CARATS:
                continue

            # We need weight to calculate
            # theoretical gold value
            if weight is None:
                continue

            # ------------------------------------------------
            # PRICE
            # ------------------------------------------------

            try:

                price = float(
                    product.get("Sp")
                    or product.get("Rrp")
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            # ------------------------------------------------
            # SHIPPING
            # ------------------------------------------------

            try:

                shipping = float(
                    product.get(
                        "ShippingCost"
                    )
                    or 0
                )

            except (
                TypeError,
                ValueError
            ):

                shipping = 0.0

            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            url = product.get(
                "Url"
            )

            if (
                url
                and url.startswith("/")
            ):

                url = (
                    BASE_URL
                    + url
                )

            # ------------------------------------------------
            # SAVE CANDIDATE
            # ------------------------------------------------

            candidates.append({
                "code": code,
                "title": title,
                "price": price,
                "shipping": shipping,
                "carat": carat,
                "weight": weight,
                "store": product.get(
                    "StoreNameWithState"
                ),
                "category": product.get(
                    "Category"
                ),
                "url": url,
            })

        # Small delay between requests
        time.sleep(0.5)

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()

    print(
        f"Catalogue reports "
        f"{total:,} matching products."
    )

    print(
        f"Found "
        f"{len(candidates)} products "
        f"with carat + weight in title."
    )

    return candidates


# ============================================================
# ANALYSE GOLD VALUE
# ============================================================

def analyse_products(
    products,
    gold_price
):

    analysed_products = []

    for product in products:

        carat = product[
            "carat"
        ]

        weight = product[
            "weight"
        ]

        price = product[
            "price"
        ]

        shipping = product[
            "shipping"
        ]

        purity = SUPPORTED_CARATS[
            carat
        ]

        # ----------------------------------------------------
        # GOLD VALUE PER GRAM
        # ----------------------------------------------------

        gold_value_per_gram = (
            gold_price
            * purity
        )

        # ----------------------------------------------------
        # THEORETICAL CONTAINED GOLD VALUE
        # ----------------------------------------------------

        theoretical_gold_value = (
            weight
            * gold_value_per_gram
        )

        # ----------------------------------------------------
        # TOTAL ACQUISITION PRICE
        # ----------------------------------------------------

        total_price = (
            price
            + shipping
        )

        # ----------------------------------------------------
        # DIFFERENCE VS GOLD VALUE
        # ----------------------------------------------------

        difference = (
            total_price
            - theoretical_gold_value
        )

        # ----------------------------------------------------
        # PERCENTAGE ABOVE / BELOW GOLD VALUE
        # ----------------------------------------------------

        price_vs_gold_pct = (
            (
                total_price
                / theoretical_gold_value
            )
            - 1
        ) * 100

        # ----------------------------------------------------
        # ADD CALCULATED VALUES
        # ----------------------------------------------------

        product[
            "purity"
        ] = purity

        product[
            "gold_value_per_gram"
        ] = gold_value_per_gram

        product[
            "theoretical_gold_value"
        ] = theoretical_gold_value

        product[
            "total_price"
        ] = total_price

        product[
            "difference"
        ] = difference

        product[
            "price_vs_gold_pct"
        ] = price_vs_gold_pct

        analysed_products.append(
            product
        )

    # --------------------------------------------------------
    # SORT BEST -> WORST
    # --------------------------------------------------------

    analysed_products.sort(
        key=lambda product:
        product[
            "price_vs_gold_pct"
        ]
    )

    return analysed_products


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_results(
    products,
    gold_price,
    number_to_show=20
):

    print()
    print()

    print(
        "=" * 72
    )

    print(
        "                    BEST GOLD DEALS"
    )

    print(
        "=" * 72
    )

    print()

    print(
        f"24ct Spot Price: "
        f"${gold_price:.2f} AUD/g"
    )

    print(
        f"9ct Gold Value:  "
        f"${gold_price * 0.375:.2f}/g"
    )

    print(
        f"Products Analysed: "
        f"{len(products)}"
    )

    # --------------------------------------------------------
    # TOP RESULTS
    # --------------------------------------------------------

    for rank, product in enumerate(
        products[:number_to_show],
        start=1
    ):

        print()

        print(
            "=" * 72
        )

        print(
            f"#{rank}  "
            f"{product['title']}"
        )

        print(
            "-" * 72
        )

        print(
            f"Listing Price:       "
            f"${product['price']:,.2f}"
        )

        print(
            f"Shipping:            "
            f"${product['shipping']:,.2f}"
        )

        print(
            f"Total Cost:          "
            f"${product['total_price']:,.2f}"
        )

        print()

        print(
            f"Weight:              "
            f"{product['weight']:.2f}g"
        )

        print(
            f"Carat:               "
            f"{product['carat']}ct"
        )

        print(
            f"Purity:              "
            f"{product['purity'] * 100:.1f}%"
        )

        print()

        print(
            f"Gold Value / g:      "
            f"${product['gold_value_per_gram']:.2f}"
        )

        print(
            f"Theoretical Value:   "
            f"${product['theoretical_gold_value']:,.2f}"
        )

        print()

        print(
            f"Difference:          "
            f"${product['difference']:+,.2f}"
        )

        print(
            f"Price vs Gold:       "
            f"{product['price_vs_gold_pct']:+.1f}%"
        )

        print()

        print(
            f"Category:            "
            f"{product['category']}"
        )

        print(
            f"Store:               "
            f"{product['store']}"
        )

        print()

        print(
            f"URL:"
        )

        print(
            product["url"]
        )


# ============================================================
# MAIN PROGRAM
# ============================================================

if __name__ == "__main__":

    print()

    # --------------------------------------------------------
    # STEP 1 - FIND CASHIES PRODUCTS
    # --------------------------------------------------------

    products = find_gold_candidates(
        query="9ct gold",
        pages=10,
        results_per_page=24,
    )

    if not products:

        print(
            "\nNo suitable gold "
            "products were found."
        )

        raise SystemExit

    # --------------------------------------------------------
    # STEP 2 - GET LIVE GOLD PRICE
    # --------------------------------------------------------

    print()

    print(
        "Fetching live gold price..."
    )

    try:

        gold_price = (
            get_gold_price_per_gram()
        )

    except Exception as error:

        print(
            "Could not fetch "
            f"gold price: {error}"
        )

        raise SystemExit

    print(
        f"Current 24ct spot price: "
        f"${gold_price:.2f} AUD/g"
    )

    # --------------------------------------------------------
    # STEP 3 - ANALYSE PRODUCTS
    # --------------------------------------------------------

    print(
        "\nCalculating gold values..."
    )

    analysed_products = (
        analyse_products(
            products,
            gold_price
        )
    )

    # --------------------------------------------------------
    # STEP 4 - DISPLAY BEST DEALS
    # --------------------------------------------------------

    display_results(
        analysed_products,
        gold_price,
        number_to_show=20
    )