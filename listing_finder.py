import re
import time
import csv
import requests

from concurrent.futures import ThreadPoolExecutor, as_completed
from gold_price import get_gold_price_per_gram


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.cashconverters.com.au"
SEARCH_ENDPOINT = BASE_URL + "/c3api/search/results"

RESULTS_PER_PAGE = 24
MAX_WORKERS = 5
MAX_RETRIES = 4

CSV_FILENAME = "gold_deals.csv"

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

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*[gG]\b",
        title,
    )

    if not matches:
        return None

    return float(matches[-1])


# ============================================================
# EXTRACT IMAGE
# ============================================================

def extract_image_url(product):

    # Cash Converters gives us a complete absolute image URL.
    image_url = product.get("AbsoluteImageUrl")

    # Fall back to relative ImageUrl if required.
    if not image_url:
        image_url = product.get("ImageUrl")

    if not image_url:
        return None

    image_url = str(image_url).strip()

    if not image_url:
        return None

    if image_url.startswith("//"):
        return "https:" + image_url

    if image_url.startswith("/"):
        return BASE_URL + image_url

    if (
        image_url.startswith("http://")
        or image_url.startswith("https://")
    ):
        return image_url

    return None


# ============================================================
# CONSERVATIVE GOLD FILTER
# ============================================================

def is_solid_gold_candidate(title):

    title_lower = title.lower()

    excluded_phrases = [

        # Plated
        "gold plated",
        "gold plate",
        "gold-plated",
        "gold-plate",
        "electroplated",
        "electro plated",
        "electro-plated",

        # Filled
        "gold filled",
        "gold fill",
        "gold-filled",
        "gold-fill",
        "goldfilled",

        "silver filled",
        "silver-filled",
        "silverfilled",

        "copper filled",
        "copper-filled",
        "copperfilled",

        # Bonded / overlay / rolled
        "gold bonded",
        "gold-bonded",
        "gold overlay",
        "gold-overlay",
        "rolled gold",
        "rolled-gold",

        # Vermeil
        "gold vermeil",
        "vermeil",

        # Gold coloured
        "gold tone",
        "gold-tone",
        "gold toned",
        "gold-toned",
        "gold coloured",
        "gold-coloured",
        "gold colored",
        "gold-colored",

        # Other metals
        "copper",
        "sterling silver",
        "silver and gold",
        "silver & gold",

        # Pearls
        "pearl",
        "pearls",

        # Diamonds
        "diamond",
        "diamonds",

        # Gemstones
        "sapphire",
        "sapphires",
        "ruby",
        "rubies",
        "emerald",
        "emeralds",
        "topaz",
        "amethyst",
        "garnet",
        "agate",
        "quartz",
        "turquoise",

        # CZ
        "cubic zirconia",
        "zirconia",
        "zircon",

        # Opals
        "opal",
        "opals",
        "andamooka",

        # Cameos
        "cameo",
        "cameos",
    ]

    for phrase in excluded_phrases:

        if phrase in title_lower:
            return False

    excluded_patterns = [
        r"\bGP\b",
        r"\bGEP\b",
        r"\bHGE\b",
        r"\bHGP\b",
        r"\bRGP\b",
        r"\bGF\b",
        r"\bCZ\b",
    ]

    for pattern in excluded_patterns:

        if re.search(
            pattern,
            title,
            re.IGNORECASE,
        ):
            return False

    return True


# ============================================================
# FETCH PAGE
# ============================================================

def fetch_page(
    page,
    query,
    number_of_results=RESULTS_PER_PAGE,
):

    params = {
        "query": query,
        "page": page,
        "NumberOfResults": number_of_results,
    }

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            response = requests.get(
                SEARCH_ENDPOINT,
                headers=HEADERS,
                params=params,
                timeout=20,
            )

            # -----------------------------------------------
            # RATE LIMIT
            # -----------------------------------------------

            if response.status_code == 429:

                retry_after = response.headers.get(
                    "Retry-After"
                )

                if (
                    retry_after
                    and retry_after.isdigit()
                ):
                    wait_time = int(retry_after)

                else:
                    wait_time = attempt * 3

                print(
                    f"\nPage {page} rate limited. "
                    f"Waiting {wait_time}s..."
                )

                time.sleep(wait_time)

                continue

            # -----------------------------------------------
            # SERVER ERROR
            # -----------------------------------------------

            if response.status_code >= 500:

                wait_time = attempt * 2

                print(
                    f"\nPage {page} server error "
                    f"{response.status_code}. "
                    f"Retrying in {wait_time}s..."
                )

                time.sleep(wait_time)

                continue

            response.raise_for_status()

            data = response.json()

            if not data.get("WasSuccessful"):

                raise RuntimeError(
                    str(data.get("Message"))
                )

            product_list = (
                data["Value"]["ProductList"]
            )

            products = product_list.get(
                "ProductListItems",
                [],
            )

            total = product_list.get(
                "ProductListItemCount",
                0,
            )

            return (
                page,
                products,
                total,
            )

        except requests.RequestException as error:

            if attempt == MAX_RETRIES:
                raise error

            wait_time = attempt * 2

            print(
                f"\nPage {page} request failed. "
                f"Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"Page {page} failed after retries."
    )


# ============================================================
# CREATE CANDIDATE
# ============================================================

def create_candidate(product):

    code = product.get("Code")

    if not code:
        return None

    title = product.get(
        "Title",
        "",
    )

    # -----------------------------------------------
    # GOLD FILTER
    # -----------------------------------------------

    if not is_solid_gold_candidate(title):
        return None

    # -----------------------------------------------
    # CARAT
    # -----------------------------------------------

    carat = extract_carat(title)

    if carat not in SUPPORTED_CARATS:
        return None

    # -----------------------------------------------
    # WEIGHT
    # -----------------------------------------------

    weight = extract_weight(title)

    if (
        weight is None
        or weight <= 0
    ):
        return None

    # -----------------------------------------------
    # PRICE
    # -----------------------------------------------

    try:

        price = float(
            product.get("Sp")
            or product.get("Rrp")
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if price <= 0:
        return None

    # -----------------------------------------------
    # SHIPPING
    # -----------------------------------------------

    try:

        shipping = float(
            product.get("ShippingCost")
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        shipping = 0.0

    # -----------------------------------------------
    # PRODUCT URL
    # -----------------------------------------------

    url = product.get("Url")

    if (
        url
        and url.startswith("/")
    ):
        url = BASE_URL + url

    # -----------------------------------------------
    # PRODUCT IMAGE
    # -----------------------------------------------

    image_url = extract_image_url(
        product
    )

    # -----------------------------------------------
    # RETURN CANDIDATE
    # -----------------------------------------------

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
        "image_url": image_url,
        "url": url,
    }


# ============================================================
# PROCESS PRODUCTS
# ============================================================

def process_products(
    products,
    seen_codes,
):

    candidates = []

    new_products = 0
    rejected_non_solid = 0
    rejected_other = 0

    for product in products:

        code = product.get("Code")

        if not code:
            continue

        if code in seen_codes:
            continue

        seen_codes.add(code)

        new_products += 1

        title = product.get(
            "Title",
            "",
        )

        if not is_solid_gold_candidate(
            title
        ):
            rejected_non_solid += 1
            continue

        candidate = create_candidate(
            product
        )

        if candidate is None:

            rejected_other += 1
            continue

        candidates.append(
            candidate
        )

    return (
        candidates,
        new_products,
        rejected_non_solid,
        rejected_other,
    )


# ============================================================
# SCAN CATALOGUE
# ============================================================

def find_gold_candidates(
    query="9ct gold",
    results_per_page=RESULTS_PER_PAGE,
):

    candidates = []
    seen_codes = set()

    rejected_non_solid = 0
    rejected_other = 0

    print()
    print("=" * 72)
    print(
        "                CASHIES FAST GOLD SCANNER"
    )
    print("=" * 72)

    print()
    print(f"Search: {query}")

    print(
        f"Concurrent workers: "
        f"{MAX_WORKERS}"
    )

    print()
    print(
        "Checking catalogue size..."
    )

    (
        _,
        first_products,
        total,
    ) = fetch_page(
        page=1,
        query=query,
        number_of_results=results_per_page,
    )

    total_pages = (
        total
        + results_per_page
        - 1
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

    # ========================================================
    # PAGE 1
    # ========================================================

    (
        page_candidates,
        new_products,
        page_rejected_non_solid,
        page_rejected_other,
    ) = process_products(
        first_products,
        seen_codes,
    )

    candidates.extend(
        page_candidates
    )

    rejected_non_solid += (
        page_rejected_non_solid
    )

    rejected_other += (
        page_rejected_other
    )

    completed_pages = 1

    print(
        f"[{completed_pages:,}/"
        f"{total_pages:,}] "
        f"Page 1 | "
        f"{new_products} new | "
        f"+{len(page_candidates)} usable | "
        f"{len(candidates):,} total"
    )

    # ========================================================
    # REMAINING PAGES
    # ========================================================

    if total_pages > 1:

        print()
        print(
            "Starting parallel scan..."
        )
        print()

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = {}

            for page in range(
                2,
                total_pages + 1,
            ):

                future = executor.submit(
                    fetch_page,
                    page,
                    query,
                    results_per_page,
                )

                futures[future] = page

            for future in as_completed(
                futures
            ):

                requested_page = (
                    futures[future]
                )

                try:

                    (
                        returned_page,
                        products,
                        _,
                    ) = future.result()

                except Exception as error:

                    completed_pages += 1

                    print(
                        f"[{completed_pages:,}/"
                        f"{total_pages:,}] "
                        f"Page {requested_page} "
                        f"FAILED: {error}"
                    )

                    continue

                (
                    page_candidates,
                    new_products,
                    page_rejected_non_solid,
                    page_rejected_other,
                ) = process_products(
                    products,
                    seen_codes,
                )

                candidates.extend(
                    page_candidates
                )

                rejected_non_solid += (
                    page_rejected_non_solid
                )

                rejected_other += (
                    page_rejected_other
                )

                completed_pages += 1

                print(
                    f"[{completed_pages:,}/"
                    f"{total_pages:,}] "
                    f"Page {returned_page:,} | "
                    f"{len(products)} returned | "
                    f"{new_products} new | "
                    f"+{len(page_candidates)} usable | "
                    f"{len(candidates):,} total"
                )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 72)
    print(
        "                         SCAN SUMMARY"
    )
    print("=" * 72)

    print(
        f"Unique products scanned:        "
        f"{len(seen_codes):,}"
    )

    print(
        f"Rejected mixed/filled/stones:   "
        f"{rejected_non_solid:,}"
    )

    print(
        f"Rejected missing carat/weight:  "
        f"{rejected_other:,}"
    )

    print(
        f"Usable gold candidates:         "
        f"{len(candidates):,}"
    )

    print("=" * 72)

    return candidates


# ============================================================
# ANALYSE PRODUCTS
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

        # -----------------------------------------------
        # PURE GOLD EQUIVALENT
        # -----------------------------------------------

        pure_gold_equivalent = (
            weight * purity
        )

        # -----------------------------------------------
        # GOLD VALUE PER GRAM
        # -----------------------------------------------

        gold_value_per_gram = (
            gold_price * purity
        )

        # -----------------------------------------------
        # THEORETICAL GOLD VALUE
        # -----------------------------------------------

        theoretical_gold_value = (
            weight
            * gold_value_per_gram
        )

        if theoretical_gold_value <= 0:
            continue

        # -----------------------------------------------
        # TOTAL ACQUISITION COST
        # -----------------------------------------------

        total_price = (
            price + shipping
        )

        # -----------------------------------------------
        # DIFFERENCE
        # -----------------------------------------------

        difference = (
            total_price
            - theoretical_gold_value
        )

        # -----------------------------------------------
        # PRICE VS GOLD %
        # -----------------------------------------------

        price_vs_gold_pct = (
            (
                total_price
                / theoretical_gold_value
            )
            - 1
        ) * 100

        product["purity"] = (
            purity
        )

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

    # Cheapest relative to gold value first
    analysed_products.sort(
        key=lambda product:
        product["price_vs_gold_pct"]
    )

    return analysed_products


# ============================================================
# EXPORT CSV
# ============================================================

def export_to_csv(
    products,
    filename=CSV_FILENAME,
):

    if not products:

        print()
        print(
            "No products to export."
        )

        return

    fieldnames = [
        "rank",
        "code",
        "title",
        "carat",
        "weight",
        "purity",
        "pure_gold_equivalent",
        "price",
        "shipping",
        "total_price",
        "gold_value_per_gram",
        "theoretical_gold_value",
        "difference",
        "price_vs_gold_pct",
        "category",
        "store",
        "image_url",
        "url",
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8",
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for rank, product in enumerate(
            products,
            start=1,
        ):

            writer.writerow({

                "rank":
                    rank,

                "code":
                    product["code"],

                "title":
                    product["title"],

                "carat":
                    product["carat"],

                "weight":
                    round(
                        product["weight"],
                        2,
                    ),

                "purity":
                    round(
                        product["purity"],
                        4,
                    ),

                "pure_gold_equivalent":
                    round(
                        product[
                            "pure_gold_equivalent"
                        ],
                        3,
                    ),

                "price":
                    round(
                        product["price"],
                        2,
                    ),

                "shipping":
                    round(
                        product["shipping"],
                        2,
                    ),

                "total_price":
                    round(
                        product["total_price"],
                        2,
                    ),

                "gold_value_per_gram":
                    round(
                        product[
                            "gold_value_per_gram"
                        ],
                        2,
                    ),

                "theoretical_gold_value":
                    round(
                        product[
                            "theoretical_gold_value"
                        ],
                        2,
                    ),

                "difference":
                    round(
                        product["difference"],
                        2,
                    ),

                "price_vs_gold_pct":
                    round(
                        product[
                            "price_vs_gold_pct"
                        ],
                        2,
                    ),

                "category":
                    product["category"]
                    or "",

                "store":
                    product["store"]
                    or "",

                "image_url":
                    product.get(
                        "image_url"
                    )
                    or "",

                "url":
                    product["url"]
                    or "",
            })

    print()
    print("=" * 72)

    print(
        f"Saved "
        f"{len(products):,} "
        f"gold candidates to:"
    )

    print(filename)

    print("=" * 72)


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
    print(
        "                    BEST GOLD DEALS"
    )
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

    print()

    print(
        f"Products Analysed:     "
        f"{len(products):,}"
    )

    print(
        f"Showing Best:          "
        f"{min(number_to_show, len(products))}"
    )

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

        print()

        print(
            f"Theoretical Value:   "
            f"${product['theoretical_gold_value']:,.2f}"
        )

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
            f"Store:               "
            f"{product['store']}"
        )

        print(
            f"Image:               "
            f"{product.get('image_url')}"
        )

        print()

        print(
            product["url"]
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    start_time = time.time()

    try:

        # ====================================================
        # 1. SCAN CASHIES
        # ====================================================

        products = find_gold_candidates(
            query="9ct gold",
            results_per_page=RESULTS_PER_PAGE,
        )

        if not products:

            print()
            print(
                "No usable gold products found."
            )

            raise SystemExit

        # ====================================================
        # 2. GOLD PRICE
        # ====================================================

        print()
        print(
            "Fetching live gold price..."
        )

        gold_price = (
            get_gold_price_per_gram()
        )

        print(
            f"Gold price being used: "
            f"${gold_price:.2f} AUD/g"
        )

        # ====================================================
        # 3. ANALYSE
        # ====================================================

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

        # ====================================================
        # 4. EXPORT
        # ====================================================

        export_to_csv(
            analysed_products,
            filename=CSV_FILENAME,
        )

        # ====================================================
        # 5. DISPLAY
        # ====================================================

        display_results(
            analysed_products,
            gold_price,
            number_to_show=20,
        )

        # ====================================================
        # RUNTIME
        # ====================================================

        elapsed = (
            time.time()
            - start_time
        )

        print()
        print("=" * 72)

        print(
            f"Total runtime: "
            f"{elapsed:.1f} seconds"
        )

        print("=" * 72)

    except KeyboardInterrupt:

        print()
        print(
            "Scan cancelled by user."
        )

    except Exception as error:

        print()
        print(
            f"Fatal error: {error}"
        )