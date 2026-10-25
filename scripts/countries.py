"""Country normalization: raw names from official pages -> ISO 3166-1 alpha-2.

Unknown names raise UnknownCountry. Callers must surface them (the build fails); nothing is silently dropped.
Add aliases here only when the mapping is unambiguous.
"""
import re
import unicodedata

import pycountry

# Names official pages use that pycountry doesn't match directly. Keep this list explicit and reviewed.
ALIASES = {
    "ivory coast": "CI", "cote d'ivoire": "CI", "côte d'ivoire": "CI", "cote divoire": "CI",
    "turkey": "TR", "türkiye": "TR", "turkiye": "TR",
    "south korea": "KR", "korea, republic of": "KR", "republic of korea": "KR", "korea (south)": "KR",
    "north korea": "KP", "korea, democratic people's republic of": "KP",
    "russia": "RU", "russian federation": "RU",
    "vietnam": "VN", "viet nam": "VN",
    "laos": "LA", "lao people's democratic republic": "LA",
    "iran": "IR", "syria": "SY", "moldova": "MD", "tanzania": "TZ", "bolivia": "BO", "venezuela": "VE",
    "taiwan": "TW", "macau": "MO", "macao": "MO", "hong kong sar": "HK", "hong kong sar china": "HK",
    "czech republic": "CZ", "czechia": "CZ",
    "united states of america": "US", "usa": "US", "united states": "US",
    "uk": "GB", "united kingdom": "GB", "great britain": "GB",
    "uae": "AE", "united arab emirates": "AE",
    "the bahamas": "BS", "bahamas": "BS", "the gambia": "GM", "gambia": "GM",
    "cape verde": "CV", "cabo verde": "CV",
    "swaziland": "SZ", "eswatini": "SZ",
    "macedonia": "MK", "north macedonia": "MK",
    "burma": "MM", "burma (myanmar)": "MM", "myanmar": "MM", "myanmar (burma)": "MM",
    "palestine": "PS", "palestinian territories": "PS", "state of palestine": "PS",
    "vatican city": "VA", "holy see": "VA",
    "brunei": "BN", "micronesia": "FM", "federated states of micronesia": "FM",
    "st. kitts and nevis": "KN", "saint kitts and nevis": "KN", "st. lucia": "LC", "saint lucia": "LC",
    "st. vincent and the grenadines": "VC", "saint vincent and the grenadines": "VC",
    "st. helena": "SH", "st. pierre and miquelon": "PM", "saint martin": "MF", "sint maarten": "SX",
    "democratic republic of congo": "CD", "democratic republic of the congo": "CD", "dr congo": "CD",
    "congo (drc)": "CD", "congo - kinshasa": "CD", "republic of the congo": "CG", "congo": "CG",
    "congo - brazzaville": "CG", "congo (republic)": "CG",
    "timor-leste": "TL", "east timor": "TL", "kosovo": "XK", "reunion": "RE", "réunion": "RE",
    "curacao": "CW", "curaçao": "CW", "aland islands": "AX", "åland islands": "AX",
    "falkland islands": "FK", "us virgin islands": "VI", "u.s. virgin islands": "VI",
    "british virgin islands": "VG", "virgin islands (british)": "VG", "virgin islands (u.s.)": "VI",
    "saint barthelemy": "BL", "saint barthélemy": "BL", "st. barthélemy": "BL",
    "sao tome and principe": "ST", "são tomé and príncipe": "ST", "são tomé & príncipe": "ST",
    "trinidad & tobago": "TT", "antigua & barbuda": "AG", "bosnia & herzegovina": "BA",
    "heard & mcdonald islands": "HM", "st. kitts & nevis": "KN", "st. vincent & grenadines": "VC",
    "turks & caicos islands": "TC", "wallis & futuna": "WF", "svalbard & jan mayen": "SJ",
    "south georgia & south sandwich islands": "GS", "u.s. outlying islands": "UM",
    "caribbean netherlands": "BQ", "bonaire, sint eustatius and saba": "BQ",
    "netherlands antilles": "AN",  # historical code; kept so sanctions lists that still use it don't fail
    "pitcairn islands": "PN", "pitcairn": "PN", "saint helena": "SH",
    "u.s. minor outlying islands": "UM", "united states minor outlying islands": "UM",
    "mayotte island": "YT", "reunion island": "RE", "st. pierre & miquelon": "PM",
    "guinea bissau": "GW", "naoero": "NR",
    "kyrgyzstan": "KG", "slovak republic": "SK", "republic of moldova": "MD",
}

# Not ISO 3166-1 countries but appear on official lists (regions/occupied areas). Tracked as region codes.
REGIONS = {
    "crimea": "XC-CRIMEA", "crimea (ukraine)": "XC-CRIMEA", "donetsk": "XC-DONETSK", "donetsk (ukraine)": "XC-DONETSK",
    "luhansk": "XC-LUHANSK", "luhansk (ukraine)": "XC-LUHANSK", "kherson (ukraine)": "XC-KHERSON",
    "zaporizhzhia (ukraine)": "XC-ZAPORIZHZHIA", "antarctica": "AQ",
    "crimea (region of ukraine)": "XC-CRIMEA", "donetsk (region of ukraine)": "XC-DONETSK",
    "luhansk (region of ukraine)": "XC-LUHANSK", "kherson (region of ukraine)": "XC-KHERSON",
    "zaporizhzhia (region of ukraine)": "XC-ZAPORIZHZHIA",
}


class UnknownCountry(ValueError):
    pass


_FLAG = re.compile(r"[\U0001F1E6-\U0001F1FF]")
_index = None


def _key(name):
    name = _FLAG.sub("", name)
    name = unicodedata.normalize("NFKC", name).replace("​", "").replace("’", "'").replace("‘", "'")
    name = name.strip().strip("*").strip()
    return re.sub(r"\s+", " ", name).lower()


def _build():
    idx = {}
    for c in pycountry.countries:
        for attr in ("name", "official_name", "common_name"):
            v = getattr(c, attr, None)
            if v:
                idx[_key(v)] = c.alpha_2
    idx.update({k: v for k, v in ALIASES.items()})
    idx.update(REGIONS)
    return idx


def normalize(raw):
    """Return (code, note). note = text in trailing parentheses, if it isn't part of the name itself."""
    global _index
    if _index is None:
        _index = _build()
    k = _key(raw)
    if k in _index:
        return _index[k], None
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", k)
    if m and m.group(1) in _index:
        return _index[m.group(1)], m.group(2)
    raise UnknownCountry(raw)


def name_of(code):
    c = pycountry.countries.get(alpha_2=code)
    return c.name if c else code


def all_codes():
    return sorted(c.alpha_2 for c in pycountry.countries)
