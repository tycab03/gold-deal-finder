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
    initial_sidebar_state="collapsed",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1500px;
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

    .no-image {
        width: 220px;
        height: 200px;
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 10px;
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
        opacity: 0.5;
    }

    .stButton button,
    .stLinkButton a {
        min-height: 46px;
        border-radius: 10px;
        font-weight: 600;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 0.75rem !important;
            padding-bottom: 3rem !important;
        }

        .main-header {
            padding: 16px 14px;
            border-radius: 14px;
            margin-bottom: 14px;
        }

        .main-title {
            font-size: 27px;
            line-height: 1.15;
        }

        .main-subtitle {
            font-size: 14px;
            line-height: 1.4;
            margin-top: 7px;
        }

        h3 {
            font-size: 19px !important;
            line-height: 1.25 !important;
        }

        .stButton button,
        .stLinkButton a {
            width: 100% !important;
            min-height: 50px !important;
            font-size: 16px !important;
        }

        input {
            font-size: 16px !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 21px !important;
        }

        [data-testid="stMetricLabel"] {
            font-size: 12px !important;
        }

        [data-testid="stImage"] img {
            max-width: 100% !important;
            height: auto !important;
            border-radius: 12px;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
        }

        [data-testid="stSidebar"] {
            min-width: unset;
        }

        .no-image {
            max-width: 100%;
            height: 180px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FUNCTIONS
# ============================================================

@st.cache_data
def load_data():

    df = pd.read_csv(
        CSV_FILE,
        dtype={
            "code": str,
            "image_url": str,
            "url": str,
        },
    )

    # Clean image URLs
    if "image_url" not in df.columns:
        df["image_url"] = ""

    df["image_url"] = (
        df["image_url"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["image_url"].str.lower() == "nan",
        "image_url",
    ] = ""

    # Clean listing URLs
    if "url" not in df.columns:
        df["url"] = ""

    df["url"] = (
        df["url"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["url"].str.lower() == "nan",
        "url",
    ] = ""

    return df


def get_last_updated():

    if not CSV_FILE.exists():
        return None

    timestamp = CSV_FILE.stat().st_mtime

    return datetime.fromtimestamp(
        timestamp
    )


def refresh_listings():

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
            purchase price with their theoretical contained-gold value.
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

    if st.button(
        "🔄 Scan Cash Converters",
        type="primary",
    ):

        with st.spinner(
            "Scanning Cash Converters..."
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
                "Scanner error."
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

    if len(df) > 0:

        gold_price = (
            df[
                "gold_value_per_gram"
            ].iloc[0]
            /
            df[
                "purity"
            ].iloc[0]
        )

    else:

        gold_price = 0


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "Gold Deal Finder"
    )

    st.caption(
        "Narrow the catalogue to the listings "
        "you're interested in."
    )

    st.divider()

    # --------------------------------------------------------
    # LAST SCAN
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

    # --------------------------------------------------------
    # REFRESH
    # --------------------------------------------------------

    if st.button(
        "🔄 Refresh Listings",
        type="primary",
        use_container_width=True,
    ):

        message = st.empty()

        message.info(
            "Scanning Cash Converters..."
        )

        with st.spinner(
            "Scanning catalogue. "
            "This may take 1–2 minutes."
        ):

            result = refresh_listings()

        if result.returncode == 0:

            message.success(
                "Catalogue updated."
            )

            st.cache_data.clear()

            st.rerun()

        else:

            message.error(
                "Scanner failed."
            )

            with st.expander(
                "Scanner error"
            ):

                st.code(
                    result.stderr
                    or result.stdout
                )

    st.divider()

    st.subheader(
        "Filters"
    )

    # --------------------------------------------------------
    # CARAT
    # --------------------------------------------------------

    available_carats = sorted(
        df["carat"]
        .dropna()
        .astype(int)
        .unique()
    )

    selected_carats = (
        st.multiselect(
            "Gold carat",
            options=available_carats,
            default=available_carats,
            format_func=lambda x:
                f"{x}ct",
        )
    )

    # --------------------------------------------------------
    # MAXIMUM % VS GOLD
    # --------------------------------------------------------

    max_markup = st.slider(
        "Maximum % vs gold value",
        min_value=-50,
        max_value=200,
        value=25,
        step=5,
    )

    # --------------------------------------------------------
    # MAXIMUM SPEND
    # --------------------------------------------------------

    maximum_price = int(
        max(
            100,
            df[
                "total_price"
            ].max(),
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

    minimum_weight = (
        st.number_input(
            "Minimum weight (g)",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )
    )

    # --------------------------------------------------------
    # JEWELLERY TYPE
    # --------------------------------------------------------

    categories = sorted(
        df["category"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_categories = (
        st.multiselect(
            "Jewellery type",
            options=categories,
            default=[],
            placeholder="All types",
        )
    )

    # --------------------------------------------------------
    # STORE / LOCATION
    # --------------------------------------------------------

    store_search = (
        st.text_input(
            "Store / location",
            placeholder="e.g. Townsville",
        )
    )

    # --------------------------------------------------------
    # BELOW THEORETICAL VALUE
    # --------------------------------------------------------

    below_only = st.toggle(
        "Only below theoretical value",
        value=False,
    )

    # --------------------------------------------------------
    # IMAGES ONLY
    # --------------------------------------------------------

    images_only = st.toggle(
        "Only listings with images",
        value=False,
    )


# ============================================================
# TOP METRICS
# ============================================================

below_gold_count = len(
    df[
        df[
            "price_vs_gold_pct"
        ] < 0
    ]
)

image_count = (
    df[
        "image_url"
    ]
    .fillna("")
    .astype(str)
    .str.strip()
    .ne("")
    .sum()
)


(
    metric1,
    metric2,
    metric3,
    metric4,
) = st.columns(4)


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
# SEARCH / SORT
# ============================================================

st.divider()

search_col, sort_col = (
    st.columns(
        [3, 1]
    )
)


with search_col:

    search = st.text_input(
        "Search listings",
        placeholder=(
            "Search chain, bracelet, necklace, pendant..."
        ),
        label_visibility="collapsed",
    )


with sort_col:

    sort_option = (
        st.selectbox(
            "Sort",
            [
                "Best value",
                "Lowest price",
                "Highest weight",
                "Highest gold value",
            ],
            label_visibility="collapsed",
        )
    )


# ============================================================
# FILTER DATA
# ============================================================

filtered_df = df.copy()


# ------------------------------------------------------------
# CARAT
# ------------------------------------------------------------

if selected_carats:

    filtered_df = (
        filtered_df[
            filtered_df[
                "carat"
            ].isin(
                selected_carats
            )
        ]
    )


# ------------------------------------------------------------
# MAXIMUM % VS GOLD
# ------------------------------------------------------------

filtered_df = (
    filtered_df[
        filtered_df[
            "price_vs_gold_pct"
        ] <= max_markup
    ]
)


# ------------------------------------------------------------
# MAXIMUM PRICE
# ------------------------------------------------------------

filtered_df = (
    filtered_df[
        filtered_df[
            "total_price"
        ] <= max_price
    ]
)


# ------------------------------------------------------------
# MINIMUM WEIGHT
# ------------------------------------------------------------

filtered_df = (
    filtered_df[
        filtered_df[
            "weight"
        ] >= minimum_weight
    ]
)


# ------------------------------------------------------------
# CATEGORY
# ------------------------------------------------------------

if selected_categories:

    filtered_df = (
        filtered_df[
            filtered_df[
                "category"
            ].isin(
                selected_categories
            )
        ]
    )


# ------------------------------------------------------------
# STORE
# ------------------------------------------------------------

if store_search:

    filtered_df = (
        filtered_df[
            filtered_df[
                "store"
            ]
            .fillna("")
            .str.contains(
                store_search,
                case=False,
                na=False,
            )
        ]
    )


# ------------------------------------------------------------
# BELOW VALUE
# ------------------------------------------------------------

if below_only:

    filtered_df = (
        filtered_df[
            filtered_df[
                "price_vs_gold_pct"
            ] < 0
        ]
    )


# ------------------------------------------------------------
# IMAGES ONLY
# ------------------------------------------------------------

if images_only:

    filtered_df = (
        filtered_df[
            filtered_df[
                "image_url"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ]
    )


# ------------------------------------------------------------
# SEARCH
# ------------------------------------------------------------

if search:

    filtered_df = (
        filtered_df[
            filtered_df[
                "title"
            ]
            .fillna("")
            .str.contains(
                search,
                case=False,
                na=False,
            )
        ]
    )


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

result_col, show_col = (
    st.columns(
        [4, 1]
    )
)


with result_col:

    st.subheader(
        f"{len(filtered_df):,} "
        f"listings found"
    )


with show_col:

    number_to_show = (
        st.selectbox(
            "Results shown",
            [
                10,
                25,
                50,
                100,
            ],
            index=1,
        )
    )


# ============================================================
# NO RESULTS
# ============================================================

if len(filtered_df) == 0:

    st.info(
        "No listings match your filters."
    )

    st.stop()


# ============================================================
# PRODUCT CARDS
# ============================================================

for position, (_, row) in enumerate(
    filtered_df.head(
        number_to_show
    ).iterrows(),
    start=1,
):

    percent = float(
        row[
            "price_vs_gold_pct"
        ]
    )

    difference = float(
        row[
            "difference"
        ]
    )

    # --------------------------------------------------------
    # COMPARISON TEXT
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
    # IMAGE URL
    # --------------------------------------------------------

    image_url = str(
        row.get(
            "image_url",
            "",
        )
    ).strip()

    if image_url.lower() == "nan":
        image_url = ""

    # --------------------------------------------------------
    # LISTING URL
    # --------------------------------------------------------

    listing_url = str(
        row.get(
            "url",
            "",
        )
    ).strip()

    if listing_url.lower() == "nan":
        listing_url = ""

    # --------------------------------------------------------
    # STORE
    # --------------------------------------------------------

    store = (
        row["store"]
        if pd.notna(
            row["store"]
        )
        else "Store unavailable"
    )

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category = (
        row["category"]
        if pd.notna(
            row["category"]
        )
        else "Jewellery"
    )

    # ========================================================
    # CARD
    # ========================================================

    with st.container(
        border=True
    ):

        # Slightly wider image column prevents overlap
        image_col, info_col = (
            st.columns(
                [1.25, 4],
                gap="large",
            )
        )

        # ====================================================
        # LEFT SIDE - IMAGE
        # ====================================================

        with image_col:

            if image_url:

                # IMPORTANT:
                # This Streamlit version requires integer width.
                st.image(
                    image_url,
                    width=220,
                )

            else:

                st.markdown(
                    """
                    <div class="no-image">
                        No product image
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ====================================================
        # RIGHT SIDE - INFORMATION
        # ====================================================

        with info_col:

            # ------------------------------------------------
            # TITLE + PERCENTAGE
            # ------------------------------------------------

            title_col, percentage_col = (
                st.columns(
                    [4, 1],
                    gap="medium",
                )
            )


            with title_col:

                st.markdown(
                    f"### #{position} "
                    f"{row['title']}"
                )

                st.caption(
                    f"📍 {store}  •  "
                    f"{category}"
                )


            with percentage_col:

                st.caption(
                    "PRICE VS GOLD"
                )

                st.markdown(
                    f"### {percent:+.1f}%"
                )


            # ------------------------------------------------
            # METRICS
            # ------------------------------------------------

            (
                cost_col,
                gold_col,
                diff_col,
                weight_col,
                carat_col,
            ) = st.columns(5)


            with cost_col:

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


            # ------------------------------------------------
            # VALUE DESCRIPTION
            # ------------------------------------------------

            st.markdown(
                f"**{comparison_text}**"
            )


            # ------------------------------------------------
            # SECONDARY INFORMATION
            # ------------------------------------------------

            st.caption(
                f"Pure gold equivalent: "
                f"{row['pure_gold_equivalent']:.2f}g"
                f"  •  "
                f"Listing: "
                f"${row['price']:,.2f}"
                f"  •  "
                f"Shipping: "
                f"${row['shipping']:,.2f}"
                f"  •  "
                f"Item #{row['code']}"
            )


            # ------------------------------------------------
            # CASH CONVERTERS BUTTON
            # ------------------------------------------------

            if listing_url:

                st.link_button(
                    "View Cash Converters Listing →",
                    listing_url,
                    use_container_width=True,
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Theoretical contained-gold values are estimates based "
    "on the stated item weight, stated carat and current or "
    "cached gold spot price. Actual recoverable gold value "
    "may differ because of stones, non-gold components, "
    "solder, clasps, assay results, refining costs and "
    "other deductions."
)