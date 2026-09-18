import requests
import re

BASE_URL = "https://www.cashconverters.com.au"

SEARCH_JS = (
    BASE_URL +
    "/dist/js/search.3.212.0.js"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    )
}


def inspect_search_javascript():

    print("=== CASHIES SEARCH JS INSPECTOR ===\n")

    response = requests.get(
        SEARCH_JS,
        headers=HEADERS,
        timeout=15
    )

    print(f"Status: {response.status_code}")

    response.raise_for_status()

    javascript = response.text

    print(
        f"JavaScript size: "
        f"{len(javascript):,} characters"
    )

    # Save a local copy
    with open(
        "cashies_search.js",
        "w",
        encoding="utf-8"
    ) as file:
        file.write(javascript)

    print("Saved as cashies_search.js")

    # Things likely to reveal the search endpoint
    keywords = [
        "ajax",
        "$.get",
        "$.post",
        "$.ajax",
        "fetch(",
        "/api/",
        "search",
        "url:",
        "endpoint",
        "page=",
        "category",
    ]

    print("\n--- KEYWORD RESULTS ---")

    for keyword in keywords:

        count = javascript.lower().count(
            keyword.lower()
        )

        print(f"{keyword}: {count}")

    print("\n--- INTERESTING CONTEXT ---")

    patterns = [
        r"\$\.ajax",
        r"\$\.get",
        r"\$\.post",
        r"fetch\(",
        r"url\s*:",
        r"/api/",
    ]

    found = 0

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            javascript,
            re.IGNORECASE
        ):

            found += 1

            start = max(
                0,
                match.start() - 300
            )

            end = min(
                len(javascript),
                match.end() + 500
            )

            context = javascript[start:end]

            # Make minified JS easier to read
            context = re.sub(
                r"\s+",
                " ",
                context
            )

            print(
                f"\n--- MATCH {found} ---"
            )

            print(context)

            # Prevent insane terminal output
            if found >= 20:
                return


if __name__ == "__main__":
    inspect_search_javascript()