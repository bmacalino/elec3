"""Country names in the BSP by-country workbook.

Effective 17 July 2023 the BSP adopted the ISO 3166 country list and a
continental grouping. The sheets up to 2022 use the older names, so those are
mapped to the current ones to give each country one series across the study
period. Old entries with no single current equivalent (for example
"Netherlands Antilles" or "Europe, NES") keep their old name.
"""

# Rows that are sums of other rows, not countries. Compared in lower case.
AGGREGATES = frozenset(
    {
        "total",
        "asia",
        "asean",
        "middle east",
        "americas",
        "oceania",
        "europe",
        "european union (eu)",
        "africa",
    }
)

# Name up to 2022 -> name from 2023.
RENAMED = {
    # Asia
    "Brunei": "Brunei Darussalam",
    "China (Mainland)": "China",
    "East Timor": "Timor-Leste",
    "Hong Kong": "Hong Kong, SAR China",
    "Korea, North": "Korea (North)",
    "Korea, Rep. of": "Korea (South)",
    "Laos": "Lao PDR",
    "Macau": "Macao, SAR China",
    "Maldive Islands": "Maldives",
    "Sri-Lanka": "Sri Lanka",
    "Taiwan": "Taiwan, Republic of China",
    "Vietnam": "Viet Nam",
    # Middle East
    "Egypt Arab Republic": "Egypt",
    "Iran": "Iran, Islamic Republic of",
    "Syria": "Syrian Arab Republic (Syria)",
    # Americas
    "Curacao": "Curaçao",
    "Falkland": "Falkland Islands (Malvinas)",
    "Saipan": "Northern Mariana Islands",
    "St. Pierre and Miguelon": "Saint Pierre and Miquelon",
    "U.S.A.": "United States of America",
    "Venezuela": "Venezuela (Bolivarian Republic)",
    # Oceania
    "Comores Archipelago": "Comoros",
    # Europe
    "Armenia, Rep Of": "Armenia",
    "Bosnia": "Bosnia and Herzegovina",
    "Faeroe Island": "Faroe Islands",
    "Macedonia, Republic": "Macedonia, Republic of",
    "Slovak Republic": "Slovakia",
    "Slovenia Republic": "Slovenia",
    # Africa
    "Cape Verde Islands": "Cabo Verde",
    "Central African Rep.": "Central African Republic",
    "Guinea-Bissau, Rep. Of": "Guinea-Bissau",
    "Ivory Coast": "Côte d'Ivoire",
    "Reunion Island": "Réunion",
    "Somali": "Somalia",
    "South Africa, Rep. of": "South Africa",
    "St. Helena and Dep": "Saint Helena",
    "Swaziland": "Eswatini",
    "Tanzania": "Tanzania, United Republic of",
    # Not elsewhere classified
    "OTHERS": "Others",
}


def is_aggregate(area: str) -> bool:
    return area.lower() in AGGREGATES


def current_name(area: str) -> str:
    return RENAMED.get(area, area)
