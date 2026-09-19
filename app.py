import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from gold_price import get_gold_price_per_gram


# ============================================================
# CONFIG
# ============================================================

CSV_FILE = Path("gold_deals.csv")
SCANNER_FILE = Path("listing_finder.py")

st.set_page_config(
    page_title="Gold Deal Finder",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1450px;
        padding-top: 1.5rem;
        padding-bottom: 4rem;
    }

    [data-testid="stSidebar"] {
        min-width: 300px;
    }

    .main-header {
        padding: 25px 30px;
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 18px;
        margin-bottom: 25px;
    }

    .main-title {
        font-size: 38px;
        font-weight: 800;
        margin: 0;
    }

    .main-subtitle {
        font-size: 16px;
        opacity: 0.7;
        margin-top: 5px;
    }

    .section-label {
        font-size: 13px;
        font-weight: 700;
        opacity: 0.6;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .below-value {
        font-size: 26px;
        font-weight: 800;
    }

    .above-value {
        font-size: 26px;
        font-weight: 800;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATA FUNCTIONS
# ============================================================

@st.cache_data
def load_data():
    return pd.read_csv(
        CSV_FILE,
        dtype={
            "code": str,
        },
    )


def get_last_updated():
    if not CSV_FILE.exists():
        return None

    timestamp = CSV_FILE.stat().st_mtime

    return datetime.fromtimestamp(
        timestamp
    )


def refresh_listings():
    """
    Run listing_finder.py using the same Python interpreter
    that is currently running Streamlit.
    """

    result = subprocess.run(
        [
            sys.executable,
            str(SCANNER_FILE),
        ],
        capture_output=True,
        text=True,
    )

    return result


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="main-header">
        <div class="main-title">
            🟡 Gold Deal Finder
        </div>

        <div class="main-subtitle">
            Find second-hand gold listings and compare their
            purchase price with estimated contained-gold value.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CHECK FILES
# ============================================================

if not SCANNER_FILE.exists():
    st.error(
        "listing_finder.py could not be found."
    )
    st.stop()


if not CSV_FILE.exists():

    st.warning(
        "No catalogue data has been generated yet."
    )

    st.write(
        "Run the scanner to generate your first dataset."
    )

    if st.button(
        "🔄 Scan Cash Converters",
        type="primary",
    ):

        with st.spinner(
            "Scanning Cash Converters. "
            "This may take around 1–2 minutes..."
        ):

            result = refresh_listings()

        if result.returncode == 0:

            st.success(
                "Scan complete."
            )

            st.cache_data.clear()
            st.rerun()

        else:

            st.error(
                "The scanner encountered an error."
            )

            st.code(
                result.stderr
                or result.stdout
            )

    st.stop()


# ============================================================
# LOAD DATA
# ============================================================

df = load_data()


# ============================================================
# GOLD PRICE
# ============================================================

try:

    gold_price = (
        get_gold_price_per_gram()
    )

except Exception:

    # Fall back to the spot price represented in the CSV.

    if len(df) > 0:

        gold_price = (
            df[
                "gold_value_per_gram"
            ].iloc[0]
            /
            df["purity"].iloc[0]
        )

    else:

        gold_price = 0


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("Filters")

    st.caption(
        "Narrow the catalogue to the "
        "listings you're interested in."
    )

    st.divider()

    # --------------------------------------------------------
    # REFRESH
    # --------------------------------------------------------

    last_updated = get_last_updated()

    if last_updated:

        st.caption(
            "Last catalogue scan"
        )

        st.write(
            last_updated.strftime(
                "%d %b %Y • %I:%M %p"
            )
        )

    if st.button(
        "🔄 Refresh Listings",
        type="primary",
        use_container_width=True,
    ):

        progress_text = st.empty()

        progress_text.info(
            "Scanning Cash Converters..."
        )

        with st.spinner(
            "Scanning the catalogue. "
            "This may take around 1–2 minutes."
        ):

            result = refresh_listings()

        if result.returncode == 0:

            progress_text.success(
                "Catalogue updated."
            )

            st.cache_data.clear()

            st.rerun()

        else:

            progress_text.error(
                "Scanner failed."
            )

            with st.expander(
                "Show scanner error"
            ):

                st.code(
                    result.stderr
                    or result.stdout
                )

    st.divider()

    # --------------------------------------------------------
    # CARAT
    # --------------------------------------------------------

    available_carats = sorted(
        df["carat"]
        .dropna()
        .astype(int)
        .unique()
    )

    selected_carats = st.multiselect(
        "Gold carat",
        options=available_carats,
        default=available_carats,
        format_func=lambda x: f"{x}ct",
    )

    # --------------------------------------------------------
    # MAX % VS GOLD
    # --------------------------------------------------------

    max_markup = st.slider(
        "Maximum % vs gold value",
        min_value=-50,
        max_value=200,
        value=25,
        step=5,
    )

    # --------------------------------------------------------
    # MAXIMUM PRICE
    # --------------------------------------------------------

    maximum_price = int(
        max(
            100,
            df["total_price"].max(),
        )
    )

    max_price = st.number_input(
        "Maximum spend ($)",
        min_value=0,
        max_value=maximum_price,
        value=min(
            5000,
            maximum_price,
        ),
        step=100,
    )

    # --------------------------------------------------------
    # MINIMUM WEIGHT
    # --------------------------------------------------------

    minimum_weight = st.number_input(
        "Minimum weight (g)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    categories = sorted(
        df["category"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_categories = st.multiselect(
        "Jewellery type",
        options=categories,
        default=[],
        placeholder="All types",
    )

    # --------------------------------------------------------
    # STORE SEARCH
    # --------------------------------------------------------

    store_search = st.text_input(
        "Store / location",
        placeholder="e.g. Townsville",
    )

    st.divider()

    # --------------------------------------------------------
    # ONLY BELOW THEORETICAL
    # --------------------------------------------------------

    below_only = st.toggle(
        "Only below theoretical value",
        value=False,
    )


# ============================================================
# METRICS
# ============================================================

below_gold_count = len(
    df[
        df["price_vs_gold_pct"] < 0
    ]
)

metric1, metric2, metric3, metric4 = (
    st.columns(4)
)


with metric1:

    st.metric(
        "24ct Spot",
        f"${gold_price:,.2f}/g",
    )


with metric2:

    st.metric(
        "9ct Gold",
        f"${gold_price * 0.375:,.2f}/g",
    )


with metric3:

    st.metric(
        "Gold Listings",
        f"{len(df):,}",
    )


with metric4:

    st.metric(
        "Below Theoretical",
        f"{below_gold_count:,}",
    )


# ============================================================
# SEARCH BAR
# ============================================================

st.divider()

search_col, sort_col = st.columns(
    [3, 1]
)


with search_col:

    search = st.text_input(
        "Search",
        placeholder=(
            "Search chain, bracelet, "
            "necklace, pendant..."
        ),
        label_visibility="collapsed",
    )


with sort_col:

    sort_option = st.selectbox(
        "Sort",
        [
            "Best value",
            "Lowest price",
            "Highest weight",
            "Highest gold value",
        ],
        label_visibility="collapsed",
    )


# ============================================================
# APPLY FILTERS
# ============================================================

filtered_df = df.copy()


if selected_carats:

    filtered_df = filtered_df[
        filtered_df["carat"].isin(
            selected_carats
        )
    ]


filtered_df = filtered_df[
    filtered_df[
        "price_vs_gold_pct"
    ] <= max_markup
]


filtered_df = filtered_df[
    filtered_df[
        "total_price"
    ] <= max_price
]


filtered_df = filtered_df[
    filtered_df[
        "weight"
    ] >= minimum_weight
]


if selected_categories:

    filtered_df = filtered_df[
        filtered_df[
            "category"
        ].isin(
            selected_categories
        )
    ]


if store_search:

    filtered_df = filtered_df[
        filtered_df["store"]
        .fillna("")
        .str.contains(
            store_search,
            case=False,
            na=False,
        )
    ]


if below_only:

    filtered_df = filtered_df[
        filtered_df[
            "price_vs_gold_pct"
        ] < 0
    ]


if search:

    filtered_df = filtered_df[
        filtered_df["title"]
        .fillna("")
        .str.contains(
            search,
            case=False,
            na=False,
        )
    ]


# ============================================================
# SORT
# ============================================================

if sort_option == "Best value":

    filtered_df = (
        filtered_df.sort_values(
            "price_vs_gold_pct",
            ascending=True,
        )
    )


elif sort_option == "Lowest price":

    filtered_df = (
        filtered_df.sort_values(
            "total_price",
            ascending=True,
        )
    )


elif sort_option == "Highest weight":

    filtered_df = (
        filtered_df.sort_values(
            "weight",
            ascending=False,
        )
    )


elif sort_option == "Highest gold value":

    filtered_df = (
        filtered_df.sort_values(
            "theoretical_gold_value",
            ascending=False,
        )
    )


# ============================================================
# RESULTS HEADER
# ============================================================

st.divider()

result_col, show_col = st.columns(
    [4, 1]
)


with result_col:

    st.subheader(
        f"{len(filtered_df):,} listings found"
    )


with show_col:

    number_to_show = st.selectbox(
        "Results shown",
        [
            10,
            25,
            50,
            100,
        ],
        index=1,
    )


# ============================================================
# NO RESULTS
# ============================================================

if len(filtered_df) == 0:

    st.info(
        "No listings match your current filters."
    )

    st.stop()


# ============================================================
# DEAL CARDS
# ============================================================

for position, (_, row) in enumerate(
    filtered_df.head(
        number_to_show
    ).iterrows(),
    start=1,
):

    percent = float(
        row["price_vs_gold_pct"]
    )

    difference = float(
        row["difference"]
    )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    if percent < 0:

        comparison_text = (
            f"{abs(percent):.1f}% below "
            f"theoretical gold value"
        )

    elif percent == 0:

        comparison_text = (
            "At theoretical gold value"
        )

    else:

        comparison_text = (
            f"{percent:.1f}% above "
            f"theoretical gold value"
        )

    # --------------------------------------------------------
    # CARD
    # --------------------------------------------------------

    with st.container(
        border=True
    ):

        title_col, percentage_col = (
            st.columns(
                [4, 1]
            )
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        with title_col:

            st.markdown(
                f"### #{position} "
                f"{row['title']}"
            )

            store = (
                row["store"]
                if pd.notna(row["store"])
                else "Store unavailable"
            )

            category = (
                row["category"]
                if pd.notna(row["category"])
                else "Jewellery"
            )

            st.caption(
                f"📍 {store}  •  {category}"
            )

        # ----------------------------------------------------
        # BIG %
        # ----------------------------------------------------

        with percentage_col:

            st.markdown(
                '<div class="section-label">'
                'PRICE VS GOLD'
                '</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f"## {percent:+.1f}%"
            )

        # ----------------------------------------------------
        # MAIN VALUES
        # ----------------------------------------------------

        (
            price_col,
            gold_col,
            diff_col,
            weight_col,
            carat_col,
        ) = st.columns(5)


        with price_col:

            st.metric(
                "Total Cost",
                f"${row['total_price']:,.2f}",
            )


        with gold_col:

            st.metric(
                "Theoretical Gold",
                f"${row['theoretical_gold_value']:,.2f}",
            )


        with diff_col:

            st.metric(
                "Difference",
                f"${difference:+,.2f}",
            )


        with weight_col:

            st.metric(
                "Weight",
                f"{row['weight']:.2f}g",
            )


        with carat_col:

            st.metric(
                "Carat",
                f"{int(row['carat'])}ct",
            )


        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        st.write(
            f"**{comparison_text}**"
        )


        # ----------------------------------------------------
        # SECONDARY INFORMATION
        # ----------------------------------------------------

        st.caption(
            f"Listing price: "
            f"${row['price']:,.2f}"
            f"   •   "
            f"Shipping: "
            f"${row['shipping']:,.2f}"
            f"   •   "
            f"Pure gold equivalent: "
            f"{row['pure_gold_equivalent']:.2f}g"
            f"   •   "
            f"Item #{row['code']}"
        )


        # ----------------------------------------------------
        # BUTTON
        # ----------------------------------------------------

        if (
            pd.notna(row["url"])
            and str(row["url"]).strip()
        ):

            st.link_button(
                "View Cash Converters Listing →",
                str(row["url"]),
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Gold Deal Finder compares listing prices with an "
    "estimated theoretical contained-gold value. The estimate "
    "is based on stated weight, stated carat and gold spot "
    "price. Actual recoverable value can differ because of "
    "stones, non-gold components, assay results, refining "
    "costs and other factors."
)