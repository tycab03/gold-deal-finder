# Gold Deal Finder

Gold Deal Finder is a Python and Streamlit application that scans Cash
Converters jewellery listings and compares each item's purchase price with its
estimated contained-gold value.

The project makes it easier to search a large catalogue and identify listings
that may be priced favourably compared with the current gold spot price.

## Features

- Scans Cash Converters jewellery listings
- Supports 9ct, 14ct, 18ct, 22ct and 24ct gold
- Extracts the stated carat and weight from listing titles
- Includes shipping in the total purchase cost
- Calculates estimated contained-gold value
- Compares listing cost with theoretical gold value
- Filters out many plated, filled, mixed-material and stone-set items
- Uses listing-page text and image checks for suspicious bargains
- Exports analysed listings to CSV
- Provides a responsive Streamlit interface
- Filters results by carat, price, weight, category and store
- Sorts listings by value, price, weight or theoretical gold value

## How the valuation works

The application calculates the pure-gold equivalent using the item's stated
weight and carat purity. It then multiplies that amount by the current gold
spot price.

```text
Pure gold equivalent = item weight × gold purity
Theoretical gold value = pure gold equivalent × gold price per gram
Total cost = listing price + shipping
```

| Carat | Purity used |
| --- | ---: |
| 9ct | 37.5% |
| 14ct | 58.5% |
| 18ct | 75.0% |
| 22ct | 91.6% |
| 24ct | 99.9% |

## Installation

1. Clone the repository:

```bash
git clone https://github.com/tycab03/gold-deal-finder.git
cd gold-deal-finder
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install the required packages:

```bash
pip install -r requirements.txt
```

## Running the project

Run the scanner to update the catalogue data:

```bash
python listing_finder.py
```

Then launch the Streamlit interface:

```bash
streamlit run app.py
```

## Main files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit user interface |
| `listing_finder.py` | Catalogue scanner and listing analysis |
| `gold_price.py` | Retrieves and caches the gold spot price |
| `gold_deals.csv` | Analysed listings displayed by the app |
| `image_rejected.csv` | Listings rejected during image verification |
| `requirements.txt` | Python dependencies |

## Important limitations

The values produced by this application are estimates only. A listing's stated
weight may include stones, clasps, solder, non-gold components or other
materials. Actual gold purity, recoverable weight, buyer payouts, refining fees
and resale results may differ.

Listings should be inspected and independently verified before making a
purchase. This project is an analysis tool and does not provide financial or
investment advice.

## Author

Developed by [Ty Cabassi](https://github.com/tycab03).
