import re
import time
import requests

from gold_price import get_gold_price_per_gram


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.cashconverters.com.au"
SEARCH_ENDPOINT = BASE_URL + "/c3api/search/results"

RESULTS_PER_PAGE = 24
REQUEST_DELAY = 0.5

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

SUPPORTED_CARATS = {
    9: 0.375,
    14: 0.585,
    18: 0.750,
    22: 0.916,
    24: 0.999,
}


# ============================================================
# EXTRACT CARAT
# ============================================================

def extract_carat(title):
    """
    Examples:
        9ct Yellow Gold Chain
        18CT Gold Ring
        14ct White Gold Pendant
    """

    match = re.search(
        r"\b(9|14|18|22|24)\s*ct\b",
        title,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


# ============================================================
# EXTRACT WEIGHT
# ============================================================

def extract_weight(title):
    """
    Examples:
        Gold Bangle - 8.99G
        Gold Pendant 2.3G
        Gold Chain 12G
    """

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*[gG]\b",
        title,
    )

    if not matches:
        return None

    return float(matches[-1])


# ============================================================
# CASHIES SEARCH API
# ============================================================

def search_cashies(
    session,
    query,
    page,
    number_of_results=RESULTS_PER_PAGE,
):
    params = {
        "query": query,
        "page": page,
        "NumberOfResults": number_of_results,
    }

    response = session.get(
        SEARCH_ENDPOINT,
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

    product_list = data["Value"]["ProductList"]

    products = product_list.get(
        "ProductListItems",
        [],
    )

    total = product_list.get(
        "ProductListItemCount",
        0,
    )

    return products, total


# ============================================================
# CONVERT API PRODUCT INTO GOLD CANDIDATE
# ============================================================

def create_candidate(product):
    code = product.get("Code")

    if not code:
        return None

    title = product.get(
        "Title",
        "",
    )

    carat = extract_carat(title)
    weight = extract_weight(title)

    if carat not in SUPPORTED_CARATS:
        return None

    if weight is None:
        return None

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    try:
        price = float(
            product.get("Sp")
            or product.get("Rrp")
        )

    except (TypeError, ValueError):
        return None

    # --------------------------------------------------------
    # SHIPPING
    # --------------------------------------------------------

    try:
        shipping = float(
            product.get("ShippingCost")
            or 0
        )

    except (TypeError, ValueError):
        shipping = 0.0

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    url = product.get("Url")

    if url and url.startswith("/"):
        url = BASE_URL + url

    return {
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
    }


# ============================================================
# SCAN FULL CASHIES RESULT SET
# ============================================================

def find_gold_candidates(
    query="9ct gold",
    results_per_page=RESULTS_PER_PAGE,
):
    candidates = []
    seen_codes = set()

    session = requests.Session()
    session.headers.update(HEADERS)

    print()
    print("=" * 70)
    print("              CASHIES FULL GOLD SCANNER")
    print("=" * 70)

    print()
    print(f"Search: {query}")
    print("Checking catalogue size...")

    # --------------------------------------------------------
    # FIRST REQUEST
    # --------------------------------------------------------

    first_products, total = search_cashies(
        session=session,
        query=query,
        page=1,
        number_of_results=results_per_page,
    )

    total_pages = (
        total + results_per_page - 1
    ) // results_per_page

    print()
    print(
        f"Catalogue results: "
        f"{total:,}"
    )

    print(
        f"Results per page:  "
        f"{results_per_page}"
    )

    print(
        f"Pages required:    "
        f"{total_pages:,}"
    )

    print()

    # --------------------------------------------------------
    # SCAN EVERY PAGE
    # --------------------------------------------------------

    for page in range(
        1,
        total_pages + 1,
    ):
        try:
            if page == 1:
                products = first_products

            else:
                products, _ = search_cashies(
                    session=session,
                    query=query,
                    page=page,
                    number_of_results=results_per_page,
                )

        except Exception as error:
            print(
                f"[{page:,}/{total_pages:,}] "
                f"ERROR: {error}"
            )

            time.sleep(2)
            continue

        # Stop if Cashies stops returning products
        if not products:
            print(
                f"[{page:,}/{total_pages:,}] "
                "No products returned."
            )

            print(
                "Stopping scan."
            )

            break

        new_products = 0
        new_candidates = 0

        for product in products:
            code = product.get("Code")

            if not code:
                continue

            # Duplicate protection
            if code in seen_codes:
                continue

            seen_codes.add(code)
            new_products += 1

            candidate = create_candidate(
                product
            )

            if candidate is None:
                continue

            candidates.append(candidate)
            new_candidates += 1

        print(
            f"[{page:,}/{total_pages:,}] "
            f"{len(products)} returned | "
            f"{new_products} new | "
            f"+{new_candidates} usable | "
            f"{len(candidates):,} total usable"
        )

        # Don't hammer the API
        time.sleep(REQUEST_DELAY)

    print()
    print("=" * 70)

    print(
        f"Unique catalogue products scanned: "
        f"{len(seen_codes):,}"
    )

    print(
        f"Products with usable carat + weight: "
        f"{len(candidates):,}"
    )

    print("=" * 70)

    return candidates


# ============================================================
# CALCULATE GOLD VALUES
# ============================================================

def analyse_products(
    products,
    gold_price,
):
    analysed_products = []

    for product in products:
        carat = product["carat"]
        weight = product["weight"]
        price = product["price"]
        shipping = product["shipping"]

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

        if theoretical_gold_value <= 0:
            continue

        # ----------------------------------------------------
        # TOTAL PURCHASE COST
        # ----------------------------------------------------

        total_price = (
            price
            + shipping
        )

        # ----------------------------------------------------
        # DIFFERENCE
        # ----------------------------------------------------

        difference = (
            total_price
            - theoretical_gold_value
        )

        # ----------------------------------------------------
        # PRICE VS THEORETICAL GOLD VALUE
        # ----------------------------------------------------

        price_vs_gold_pct = (
            (
                total_price
                / theoretical_gold_value
            )
            - 1
        ) * 100

        # ----------------------------------------------------
        # PURE GOLD EQUIVALENT
        # ----------------------------------------------------

        pure_gold_equivalent = (
            weight
            * purity
        )

        # ----------------------------------------------------
        # STORE RESULTS
        # ----------------------------------------------------

        product["purity"] = purity

        product[
            "pure_gold_equivalent"
        ] = pure_gold_equivalent

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
    # BEST -> WORST
    # --------------------------------------------------------

    analysed_products.sort(
        key=lambda product:
        product["price_vs_gold_pct"]
    )

    return analysed_products


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_results(
    products,
    gold_price,
    number_to_show=20,
):
    print()
    print()

    print("=" * 72)
    print("                    BEST GOLD DEALS")
    print("=" * 72)

    print()

    print(
        f"24ct Spot Price:       "
        f"${gold_price:.2f} AUD/g"
    )

    print(
        f"9ct Gold Value:        "
        f"${gold_price * 0.375:.2f}/g"
    )

    print(
        f"14ct Gold Value:       "
        f"${gold_price * 0.585:.2f}/g"
    )

    print(
        f"18ct Gold Value:       "
        f"${gold_price * 0.750:.2f}/g"
    )

    print()

    print(
        f"Products Analysed:     "
        f"{len(products):,}"
    )

    print(
        f"Showing Best:          "
        f"{min(number_to_show, len(products))}"
    )

    # --------------------------------------------------------
    # TOP DEALS
    # --------------------------------------------------------

    for rank, product in enumerate(
        products[:number_to_show],
        start=1,
    ):
        print()
        print("=" * 72)

        print(
            f"#{rank}  "
            f"{product['title']}"
        )

        print("-" * 72)

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

        print(
            f"Pure Gold Equivalent:"
            f" {product['pure_gold_equivalent']:.2f}g"
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

        print("URL:")
        print(product["url"])


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    try:
        # ----------------------------------------------------
        # STEP 1
        # SCAN THE FULL CASHIES SEARCH
        # ----------------------------------------------------

        products = find_gold_candidates(
            query="9ct gold",
            results_per_page=24,
        )

        if not products:
            print(
                "\nNo usable gold "
                "products were found."
            )

            raise SystemExit

        # ----------------------------------------------------
        # STEP 2
        # GET LIVE GOLD PRICE
        # ----------------------------------------------------

        print()
        print(
            "Fetching live gold price..."
        )

        gold_price = (
            get_gold_price_per_gram()
        )

        print(
            f"Current 24ct spot price: "
            f"${gold_price:.2f} AUD/g"
        )

        # ----------------------------------------------------
        # STEP 3
        # CALCULATE VALUES
        # ----------------------------------------------------

        print()
        print(
            "Calculating theoretical "
            "gold values..."
        )

        analysed_products = (
            analyse_products(
                products,
                gold_price,
            )
        )

        # ----------------------------------------------------
        # STEP 4
        # DISPLAY TOP 20
        # ----------------------------------------------------

        display_results(
            analysed_products,
            gold_price,
            number_to_show=20,
        )

    except KeyboardInterrupt:
        print()
        print()
        print(
            "Scan cancelled by user."
        )

    except Exception as error:
        print()
        print(
            f"Fatal error: {error}"
        )