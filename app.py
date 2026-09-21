from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from gold_price import get_gold_price_per_gram


# ============================================================
# CONFIG
# ============================================================

CSV_FILE = Path("gold_deals.csv")

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

    .verification-badge {
        display: inline-block;
        padding: 5px 10px;
        margin-top: 4px;
        margin-bottom: 10px;
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        line-height: 1.2;
    }

    .gold-metrics-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.8rem;
        margin-bottom: 0.8rem;
    }

    .summary-metrics-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.8rem;
        margin-bottom: 1rem;
    }

    .custom-metric {
        min-width: 0;
        padding: 0.85rem 0.95rem;
        border: 1px solid rgba(128,128,128,0.20);
        border-radius: 12px;
    }

    .custom-metric-label {
        font-size: 0.88rem;
        opacity: 0.72;
        margin-bottom: 0.2rem;
    }

    .custom-metric-value {
        font-size: 1.45rem;
        font-weight: 600;
        line-height: 1.2;
        white-space: nowrap;
    }

    @media (max-width: 768px) {
        .gold-metrics-grid,
        .summary-metrics-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
        }

        .custom-metric {
            padding: 0.7rem 0.75rem;
        }

        .custom-metric-label {
            font-size: 0.78rem;
        }

        .custom-metric-value {
            font-size: 1.12rem;
        }

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


def get_verification_badge(row):
    """Return a short, user-facing verification badge for a listing."""
    image_status = str(
        row.get("image_verification_status", "")
    ).strip().lower()

    text_status = str(
        row.get("verification_status", "")
    ).strip().lower()

    if image_status == "image_gold_likely":
        return "🟢 Image checked"

    if image_status == "image_uncertain":
        return "🟡 Image uncertain"

    if image_status == "image_unverified":
        return "🟠 Image check unavailable"

    if text_status == "text_checked":
        return "🔵 Text checked"

    if text_status == "unverified":
        return "🟠 Text check unavailable"

    return "⚪ Title only"


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-header">'
    '<div class="main-title">🟡 Gold Deal Finder</div>'
    '<div class="main-subtitle">'
    'Find second-hand gold listings and compare their purchase price '
    'with their theoretical contained-gold value.'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# CHECK DATA FILE
# ============================================================

if not CSV_FILE.exists():
    st.warning("No catalogue data has been generated yet.")
    st.stop()


# ============================================================
# LOAD DATA
# ============================================================

df = load_data()

# Normalise carat values so Streamlit always works with integer carats.
df["carat"] = pd.to_numeric(
    df["carat"],
    errors="coerce",
).astype("Int64")


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

    st.divider()

    st.caption(
        "Catalogue updates are published from the verified scanner data."
    )

    st.divider()

    st.subheader(
        "Filters"
    )

    # --------------------------------------------------------
    # CARAT
    # --------------------------------------------------------

    supported_carats = [9, 14, 18, 22, 24]

    carats_in_data = set(
        df["carat"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    available_carats = [
        carat
        for carat in supported_carats
        if carat in carats_in_data
    ]

    # Use an explicit key so we can clean stale selections left over from
    # an older 9ct-only Streamlit session.
    if "gold_carat_filter" in st.session_state:
        current_selection = st.session_state["gold_carat_filter"]

        if not isinstance(current_selection, list):
            current_selection = list(current_selection)

        cleaned_selection = [
            int(carat)
            for carat in current_selection
            if int(carat) in available_carats
        ]

        # If the old session only knew about 9ct, reset to all available
        # carats when the catalogue now contains additional carats.
        if (
            cleaned_selection == [9]
            and len(available_carats) > 1
        ):
            del st.session_state["gold_carat_filter"]

        else:
            st.session_state["gold_carat_filter"] = cleaned_selection

    selected_carats = st.multiselect(
        "Gold carat",
        options=available_carats,
        default=available_carats,
        format_func=lambda x: f"{x}ct",
        key="gold_carat_filter",
    )

    # --------------------------------------------------------
    # % VS GOLD RANGE
    # --------------------------------------------------------

    min_markup, max_markup = st.slider(
        "% vs gold value range",
        min_value=-100,
        max_value=200,
        value=(-50, 25),
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


st.markdown(
    f"""
    <div class="gold-metrics-grid">
        <div class="custom-metric">
            <div class="custom-metric-label">24ct Gold</div>
            <div class="custom-metric-value">${gold_price * 0.999:,.2f}/g</div>
        </div>
        <div class="custom-metric">
            <div class="custom-metric-label">22ct Gold</div>
            <div class="custom-metric-value">${gold_price * 0.916:,.2f}/g</div>
        </div>
        <div class="custom-metric">
            <div class="custom-metric-label">18ct Gold</div>
            <div class="custom-metric-value">${gold_price * 0.750:,.2f}/g</div>
        </div>
        <div class="custom-metric">
            <div class="custom-metric-label">14ct Gold</div>
            <div class="custom-metric-value">${gold_price * 0.585:,.2f}/g</div>
        </div>
        <div class="custom-metric">
            <div class="custom-metric-label">9ct Gold</div>
            <div class="custom-metric-value">${gold_price * 0.375:,.2f}/g</div>
        </div>
    </div>

    <div class="summary-metrics-grid">
        <div class="custom-metric">
            <div class="custom-metric-label">Gold Listings</div>
            <div class="custom-metric-value">{len(df):,}</div>
        </div>
        <div class="custom-metric">
            <div class="custom-metric-label">Below Theoretical</div>
            <div class="custom-metric-value">{below_gold_count:,}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
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
# % VS GOLD RANGE
# ------------------------------------------------------------

filtered_df = (
    filtered_df[
        (
            filtered_df[
                "price_vs_gold_pct"
            ] >= min_markup
        )
        &
        (
            filtered_df[
                "price_vs_gold_pct"
            ] <= max_markup
        )
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

RESULTS_PER_PAGE = 25

total_results = len(filtered_df)
total_pages = max(
    1,
    (total_results + RESULTS_PER_PAGE - 1)
    // RESULTS_PER_PAGE,
)

if "results_page" not in st.session_state:
    st.session_state.results_page = 1

if st.session_state.results_page > total_pages:
    st.session_state.results_page = total_pages

if st.session_state.results_page < 1:
    st.session_state.results_page = 1

st.subheader(
    f"{total_results:,} listings found"
)

page_start = (
    (st.session_state.results_page - 1)
    * RESULTS_PER_PAGE
)

page_end = min(
    page_start + RESULTS_PER_PAGE,
    total_results,
)

if total_results > 0:
    st.caption(
        f"Showing {page_start + 1:,}–{page_end:,} "
        f"of {total_results:,}"
    )


def pagination_controls(key_prefix):
    previous_col, page_col, next_col = st.columns(
        [1, 2, 1]
    )

    with previous_col:
        if st.button(
            "← Previous",
            key=f"{key_prefix}_previous",
            disabled=st.session_state.results_page <= 1,
            use_container_width=True,
        ):
            st.session_state.results_page -= 1
            st.rerun()

    with page_col:
        st.markdown(
            f"<div style='text-align:center; padding-top:0.65rem;'>"
            f"<strong>Page {st.session_state.results_page:,} "
            f"of {total_pages:,}</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with next_col:
        if st.button(
            "Next →",
            key=f"{key_prefix}_next",
            disabled=st.session_state.results_page >= total_pages,
            use_container_width=True,
        ):
            st.session_state.results_page += 1
            st.rerun()


pagination_controls("top")


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

page_df = filtered_df.iloc[
    page_start:page_end
]

for position, (_, row) in enumerate(
    page_df.iterrows(),
    start=page_start + 1,
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

                verification_badge = get_verification_badge(row)

                st.markdown(
                    f'<span class="verification-badge">'
                    f'{verification_badge}'
                    f'</span>',
                    unsafe_allow_html=True,
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
                    f"${row['total_price']:,.0f}",
                )


            with gold_col:

                st.metric(
                    "Theoretical Gold",
                    f"${row['theoretical_gold_value']:,.0f}",
                )


            with diff_col:

                st.metric(
                    "Difference",
                    f"{'-' if difference < 0 else '+' if difference > 0 else ''}${abs(difference):,.0f}",
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
# BOTTOM PAGINATION
# ============================================================

if total_results > 0:
    st.divider()
    pagination_controls("bottom")


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