import re
import time
import csv
import requests
from bs4 import BeautifulSoup
from io import BytesIO

# ML imports are lazy-loaded later so the normal catalogue scan can start
# without loading PyTorch/Transformers into memory.

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
IMAGE_REJECTED_CSV_FILENAME = "image_rejected.csv"

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

        # Mixed metals / non-solid-gold wording
        # Reject these anywhere in the title. This intentionally sacrifices
        # some mixed-metal jewellery so gross weight is not valued as gold.
        "silver",
        "sterling",
        "copper",
        "plated",
        "plate",
        "pandora",

        # Set / decorative / non-gold materials
        "paste",
        "jade",
        "jadeite",
        "mother of pearl",
        "mother-of-pearl",

        # Generic stones / gems
        # We deliberately reject any listing that advertises a stone because
        # the stated gross weight may not represent gold weight alone.
        "stone",
        "stones",
        "srone",      # Common Cashies typo observed in listings
        "gem",
        "gemstone",
        "crystal",
        "crystals",
        "moissanite",
        "moissanites",
        "jet",

        # Non-gold decorative materials / inlays
        "glass",
        "coral",
        "plastic",
        "resin",
        "enamel",
        "shell",
        "mother of pearl",
        "mother-of-pearl",

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

        # Gem / diamond abbreviations
        r"\bTDW\b",
        r"\bCTW\b",
        r"\bDIA\b",
        r"\bDIAS\b",
        r"\bMOP\b",
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
# DETAIL-PAGE VERIFICATION
# ============================================================

DETAIL_VERIFY_THRESHOLD_PCT = -10.0
DETAIL_VERIFY_MAX_PRODUCTS = 150

DETAIL_REJECT_TERMS = [
    "pearl", "pearls", "diamond", "diamonds", "stone", "stones",
    "gemstone", "gemstones", "cubic zirconia", "zirconia", "opal",
    "sapphire", "ruby", "emerald", "jade", "jadeite", "coral",
    "glass", "crystal", "resin", "plastic", "enamel", "shell",
    "mother of pearl", "mother-of-pearl", "sterling silver",
    "silver and gold", "silver & gold", "gold plated", "gold-plated",
    "gold filled", "gold-filled", "vermeil", "paste set",
]


def fetch_product_detail_text(product):
    """Return product-specific text from a Cash Converters detail page.

    We deliberately avoid scanning navigation/footer text because words such as
    'silver' can appear elsewhere on the site and create false rejections.
    """
    url = product.get("url")
    if not url:
        return ""

    response = requests.get(
        url,
        headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    chunks = []

    # Metadata often contains the actual listing description.
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"property": "og:title"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            chunks.append(tag.get("content"))

    # Product structured data can contain description/material information.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if script.string:
            chunks.append(script.string)

    # Restrict visible text to likely product-content containers.
    for selector in (
        "main",
        "article",
        "[class*='product-detail']",
        "[class*='productDetail']",
        "[class*='description']",
        "[id*='description']",
    ):
        for node in soup.select(selector):
            chunks.append(node.get_text(" ", strip=True))

    return " ".join(chunks)


def find_detail_reject_terms(text):
    text_lower = text.lower()
    return sorted({term for term in DETAIL_REJECT_TERMS if term in text_lower})


def verify_suspicious_products(products):
    """Detail-check unusually cheap listings before allowing them to rank.

    Only products at least 10% below theoretical gold value are checked.
    A failed page request does NOT silently delete the product; it is retained
    with an 'unverified' status so the app never mistakes a network error for
    evidence that an item is mixed material.
    """
    targets = [
        product for product in products
        if product.get("price_vs_gold_pct", 999) <= DETAIL_VERIFY_THRESHOLD_PCT
    ][:DETAIL_VERIFY_MAX_PRODUCTS]

    if not targets:
        return products

    print()
    print("=" * 72)
    print("                 DETAIL-PAGE VERIFICATION")
    print("=" * 72)
    print(
        f"Checking {len(targets)} suspicious bargains "
        f"({DETAIL_VERIFY_THRESHOLD_PCT:.0f}% or lower vs gold)..."
    )

    rejected_codes = set()

    def check(product):
        try:
            text = fetch_product_detail_text(product)
            if not text.strip():
                return product, "unverified", []
            flags = find_detail_reject_terms(text)
            if flags:
                return product, "rejected_mixed_material", flags
            return product, "text_checked", []
        except Exception as error:
            return product, "unverified", [type(error).__name__]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check, product) for product in targets]
        completed = 0
        for future in as_completed(futures):
            product, status, flags = future.result()
            completed += 1
            product["verification_status"] = status
            product["detail_flags"] = ", ".join(flags)
            if status == "rejected_mixed_material":
                rejected_codes.add(product["code"])
                print(
                    f"[{completed}/{len(targets)}] REJECT "
                    f"{product['title']} | {', '.join(flags)}"
                )
            else:
                print(
                    f"[{completed}/{len(targets)}] {status.upper()} | "
                    f"{product['title']}"
                )

    for product in products:
        product.setdefault("verification_status", "title_only")
        product.setdefault("detail_flags", "")

    cleaned = [p for p in products if p["code"] not in rejected_codes]
    cleaned.sort(key=lambda p: p["price_vs_gold_pct"])

    print("-" * 72)
    print(f"Detail pages checked: {len(targets)}")
    print(f"Mixed-material listings removed: {len(rejected_codes)}")
    print(f"Listings remaining: {len(cleaned):,}")
    print("=" * 72)

    return cleaned



# ============================================================
# IMAGE VERIFICATION (CLIP ZERO-SHOT)
# ============================================================

IMAGE_VERIFY_THRESHOLD_PCT = -10.0
IMAGE_VERIFY_MAX_PRODUCTS = 50

# A deliberately conservative automatic-rejection threshold.
# Lower-confidence results are retained as "image_uncertain".
IMAGE_REJECT_CONFIDENCE = 0.60

IMAGE_LABELS = [
    "plain solid gold jewellery with no pearls, gemstones, stones or decorative inserts",
    "pearl jewellery or jewellery containing pearls",
    "gemstone, diamond or stone set jewellery",
    "mixed material jewellery containing non-gold decorative material",
    "gold plated, costume or imitation jewellery",
]

IMAGE_SAFE_LABEL = IMAGE_LABELS[0]

_IMAGE_CLASSIFIER = None


def get_image_classifier():
    """Lazy-load CLIP only when suspicious listings actually need image checks."""
    global _IMAGE_CLASSIFIER

    if _IMAGE_CLASSIFIER is not None:
        return _IMAGE_CLASSIFIER

    print()
    print("Loading CLIP image model...")

    try:
        from transformers import pipeline
    except ImportError as error:
        raise RuntimeError(
            "Image verification requires transformers, torch and Pillow. "
            "Install them with: pip install transformers torch Pillow"
        ) from error

    # Explicit model avoids relying on a changing pipeline default.
    _IMAGE_CLASSIFIER = pipeline(
        task="zero-shot-image-classification",
        model="openai/clip-vit-base-patch32",
    )

    return _IMAGE_CLASSIFIER


def fetch_product_image(product):
    """Download a candidate's catalogue image and return a PIL RGB image."""
    image_url = product.get("image_url")

    if not image_url:
        raise ValueError("missing_image_url")

    response = requests.get(
        image_url,
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
        timeout=20,
    )
    response.raise_for_status()

    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Image verification requires Pillow. "
            "Install it with: pip install Pillow"
        ) from error

    image = Image.open(BytesIO(response.content))
    return image.convert("RGB")


def classify_product_image(product, classifier):
    """Classify one listing image using CLIP zero-shot labels."""
    image = fetch_product_image(product)

    predictions = classifier(
        image,
        candidate_labels=IMAGE_LABELS,
    )

    if not predictions:
        return "image_unverified", "", 0.0

    best = predictions[0]
    label = str(best.get("label", ""))
    confidence = float(best.get("score", 0.0))

    if label == IMAGE_SAFE_LABEL:
        return "image_gold_likely", label, confidence

    if confidence >= IMAGE_REJECT_CONFIDENCE:
        return "rejected_image_mixed_material", label, confidence

    return "image_uncertain", label, confidence


def export_image_rejections(products, filename=IMAGE_REJECTED_CSV_FILENAME):
    """Save CLIP-rejected listings separately for manual validation."""
    fieldnames = [
        "code", "title", "carat", "weight", "price", "shipping",
        "total_price", "theoretical_gold_value", "difference",
        "price_vs_gold_pct", "store", "category", "verification_status",
        "detail_flags", "image_verification_status", "image_label",
        "image_confidence", "image_url", "url",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for product in products:
            writer.writerow({
                "code": product.get("code", ""),
                "title": product.get("title", ""),
                "carat": product.get("carat", ""),
                "weight": round(product.get("weight", 0), 2),
                "price": round(product.get("price", 0), 2),
                "shipping": round(product.get("shipping", 0), 2),
                "total_price": round(product.get("total_price", 0), 2),
                "theoretical_gold_value": round(
                    product.get("theoretical_gold_value", 0), 2
                ),
                "difference": round(product.get("difference", 0), 2),
                "price_vs_gold_pct": round(
                    product.get("price_vs_gold_pct", 0), 2
                ),
                "store": product.get("store") or "",
                "category": product.get("category") or "",
                "verification_status": product.get(
                    "verification_status", "title_only"
                ),
                "detail_flags": product.get("detail_flags", ""),
                "image_verification_status": product.get(
                    "image_verification_status", ""
                ),
                "image_label": product.get("image_label", ""),
                "image_confidence": product.get("image_confidence", ""),
                "image_url": product.get("image_url") or "",
                "url": product.get("url") or "",
            })

    print(
        f"Saved {len(products):,} image-rejected "
        f"listing(s) to {filename}"
    )


def verify_product_images(products):
    """Image-check suspicious bargains that survived the detail-page filter.

    Only listings at least 10% below theoretical contained-gold value are sent
    to CLIP. The image model is used as a conservative screening layer rather
    than proof of composition. Network/model failures retain the listing and
    mark it unverified.
    """
    targets = [
        product
        for product in products
        if product.get("price_vs_gold_pct", 999) <= IMAGE_VERIFY_THRESHOLD_PCT
    ][:IMAGE_VERIFY_MAX_PRODUCTS]

    for product in products:
        product.setdefault("image_verification_status", "not_checked")
        product.setdefault("image_label", "")
        product.setdefault("image_confidence", "")

    if not targets:
        export_image_rejections([])
        return products

    print()
    print("=" * 72)
    print("                    IMAGE VERIFICATION")
    print("=" * 72)
    print(
        f"Checking {len(targets)} suspicious images with CLIP "
        f"({IMAGE_VERIFY_THRESHOLD_PCT:.0f}% or lower vs gold)..."
    )

    try:
        classifier = get_image_classifier()
    except Exception as error:
        print()
        print(
            "Image verification unavailable: "
            f"{type(error).__name__}: {error}"
        )
        print("Listings retained as image_unverified.")

        for product in targets:
            product["image_verification_status"] = "image_unverified"

        export_image_rejections([])
        print("=" * 72)
        return products

    rejected_codes = set()
    checked = 0
    uncertain = 0
    gold_likely = 0
    failed = 0

    # Run model inference sequentially. This avoids multiple worker threads
    # trying to use the same PyTorch model simultaneously.
    for index, product in enumerate(targets, start=1):
        try:
            status, label, confidence = classify_product_image(
                product,
                classifier,
            )

            product["image_verification_status"] = status
            product["image_label"] = label
            product["image_confidence"] = round(confidence, 4)
            checked += 1

            if status == "rejected_image_mixed_material":
                rejected_codes.add(product["code"])
                print(
                    f"[{index}/{len(targets)}] IMAGE REJECT | "
                    f"{product['title']} | "
                    f"{label} | {confidence:.1%}"
                )

            elif status == "image_gold_likely":
                gold_likely += 1
                print(
                    f"[{index}/{len(targets)}] GOLD-LIKELY | "
                    f"{product['title']} | "
                    f"{confidence:.1%}"
                )

            else:
                uncertain += 1
                print(
                    f"[{index}/{len(targets)}] UNCERTAIN | "
                    f"{product['title']} | "
                    f"{label} | {confidence:.1%}"
                )

        except Exception as error:
            failed += 1
            product["image_verification_status"] = "image_unverified"
            product["image_label"] = type(error).__name__
            product["image_confidence"] = ""

            print(
                f"[{index}/{len(targets)}] IMAGE FAILED | "
                f"{product['title']} | "
                f"{type(error).__name__}: {error}"
            )

    rejected_products = [
        product
        for product in products
        if product["code"] in rejected_codes
    ]
    rejected_products.sort(key=lambda product: product["price_vs_gold_pct"])

    cleaned = [
        product
        for product in products
        if product["code"] not in rejected_codes
    ]
    cleaned.sort(key=lambda product: product["price_vs_gold_pct"])

    export_image_rejections(rejected_products)

    print("-" * 72)
    print(f"Images checked: {checked}")
    print(f"Gold-looking: {gold_likely}")
    print(f"Uncertain retained: {uncertain}")
    print(f"Image checks failed: {failed}")
    print(f"Image-rejected listings removed: {len(rejected_codes)}")
    print(f"Listings remaining: {len(cleaned):,}")
    print("=" * 72)

    return cleaned


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
        "verification_status",
        "detail_flags",
        "image_verification_status",
        "image_label",
        "image_confidence",
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

                "verification_status":
                    product.get(
                        "verification_status",
                        "title_only",
                    ),

                "detail_flags":
                    product.get(
                        "detail_flags",
                        "",
                    ),

                "image_verification_status":
                    product.get(
                        "image_verification_status",
                        "not_checked",
                    ),

                "image_label":
                    product.get(
                        "image_label",
                        "",
                    ),

                "image_confidence":
                    product.get(
                        "image_confidence",
                        "",
                    ),
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

        # Search every supported carat, then merge and deduplicate by item code.
        search_queries = [
            "9ct gold",
            "14ct gold",
            "18ct gold",
            "22ct gold",
            "24ct gold",
        ]

        products_by_code = {}

        for search_number, query in enumerate(search_queries, start=1):
            print()
            print("#" * 72)
            print(
                f"CARAT SEARCH {search_number}/{len(search_queries)}: "
                f"{query.upper()}"
            )
            print("#" * 72)

            query_products = find_gold_candidates(
                query=query,
                results_per_page=RESULTS_PER_PAGE,
            )

            before = len(products_by_code)

            for product in query_products:
                products_by_code[product["code"]] = product

            added = len(products_by_code) - before

            print()
            print(
                f"{query}: {len(query_products):,} usable returned | "
                f"{added:,} new unique | "
                f"{len(products_by_code):,} unique combined"
            )

        products = list(products_by_code.values())

        print()
        print("=" * 72)
        print("                    ALL-CARAT SCAN COMPLETE")
        print("=" * 72)
        print(f"Unique usable products: {len(products):,}")

        for carat in SUPPORTED_CARATS:
            count = sum(
                1 for product in products
                if product["carat"] == carat
            )
            print(f"{carat}ct: {count:,}")

        print("=" * 72)

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
        # 4. VERIFY SUSPICIOUS BARGAINS FROM DETAIL PAGES
        # ====================================================

        analysed_products = verify_suspicious_products(
            analysed_products
        )

        # ====================================================
        # 5. IMAGE-VERIFY SUSPICIOUS BARGAINS
        # ====================================================

        analysed_products = verify_product_images(
            analysed_products
        )

        # ====================================================
        # 6. EXPORT
        # ====================================================

        export_to_csv(
            analysed_products,
            filename=CSV_FILENAME,
        )

        # ====================================================
        # 7. DISPLAY
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