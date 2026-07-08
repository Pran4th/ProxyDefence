ENTITY_ALIASES = {
    "us": "United States",
    "u.s.": "United States",
    "u.s": "United States",
    "usa": "United States",
    "the united states": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "russia's": "Russia",
    "china's": "China",
    "iran's": "Iran",
    "trump": "Donald Trump",
    "central command": "US Central Command",
    "united states of america": "United States",
    "strait of hormuz": "Strait of Hormuz",
    "strait of malacca": "Malacca Strait",
    "strait of bab el-mandeb": "Bab el-Mandeb",
    "bab el mandeb": "Bab el-Mandeb",
    "south china sea": "South China Sea",
    "east china sea": "East China Sea",
    "suez canal": "Suez Canal",
    "russian federation": "Russia",
    "islamic republic of iran": "Iran",
    "kingdom of saudi arabia": "Saudi Arabia",
    "people's republic of china": "China",
    "republic of india": "India",
    "united arab emirates": "UAE",
    "opec": "OPEC",
    "organization of the petroleum exporting countries": "OPEC",
    "international energy agency": "IEA",
    "saudi aramco": "Saudi Aramco",
    "national iranian oil company": "NIOC",
    "abqaiq plant": "Abqaiq",
    "khurais oil field": "Khurais",
    "ghawar oil field": "Ghawar",
}

IGNORE_ENTITIES = {
    "earthquakes",
    "band of brothers",
    "ai generated image",
    "brink of war",
}

EVENT_ENTITY_BLACKLIST = {
    "reuters",
    "ap",
    "associated press",
    "fox news",
    "cnn",
    "bbc",
    "new york times",
    "ai generated image",
    "brink of war",
}


def normalize_entity(name: str) -> str:
    key = name.strip().lower()
    if key in ENTITY_ALIASES:
        return ENTITY_ALIASES[key]
    return name.strip()


def is_ignored_entity(name: str) -> bool:
    return name.strip().lower() in IGNORE_ENTITIES


def is_blacklisted_entity(name: str) -> bool:
    return name.strip().lower() in EVENT_ENTITY_BLACKLIST
