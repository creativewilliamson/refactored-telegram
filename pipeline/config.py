"""Paths and constants shared by the pipeline."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = DATA / "seed" / "offers-2026.json"
CACHE = DATA / "cache"
DIST = ROOT / "dist"
TEMPLATES = Path(__file__).resolve().parent / "templates"
STATIC = Path(__file__).resolve().parent / "static"

SITE_NAME = "Vet Day Deals"
SITE_URL = "https://vetdaydeals.pages.dev"
EVENT_DATE = "2026-11-11"

# Sources that are offer roundups, not the business's own page. Their links
# say "opens the offer list where we found this".
ROUNDUP_HOSTS = {"military.com", "news.va.gov", "legion.org"}
# "Find the nearest X" with none in range names X's states when it has
# stores in this many or fewer.
MAX_STATES_LISTED = 12

# A generic client name for downloads; no personal contact details.
USER_AGENT = "VetDayDeals-build/1.0 (static site data pipeline)"

# Cloudflare Pages limits (fail the build if exceeded).
MAX_FILES = 20_000
MAX_FILE_BYTES = 25 * 1024 * 1024

# 56 places that get a state page: 50 states, DC and five territories.
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands",
    "AS": "American Samoa", "MP": "Northern Mariana Islands",
}
TERRITORIES = {"PR", "GU", "VI", "AS", "MP"}
