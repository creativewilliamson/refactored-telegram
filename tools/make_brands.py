"""One-time research helper that wrote data/brands.json.

The brand -> spider / Q-id table below came from research on 2026-11-07:
- the All The Places run index (data.alltheplaces.xyz/runs/history.json),
- each run's stats/_results.json (spider names and feature counts),
- the 2026-10-24 run's stats/_insights.json (Wikidata Q-id -> ATP spiders),
- then each Q-id checked on wikidata.org (pipeline/wikidata.py).
Q-ids left empty here are filled from the spider's own brand:wikidata after
checking it on wikidata.org (see data/wikidata-check.json).

Run: python tools/make_brands.py   (only if you need to regenerate)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (brand slug, display name, offer slugs, Q-ids, ATP spiders, approx. US count)
WITH_SPIDER = [
    ("applebees", "Applebee's", ["applebee-s"], ["Q621532"], ["applebees"], 1500),
    ("bjs-restaurant", "BJ's Restaurant & Brewhouse", ["bj-s-restaurant-and-brewhouse"], ["Q4835755"], ["bj_restaurant_us"], 215),
    ("blaze-pizza", "Blaze Pizza", ["blaze-pizza"], ["Q23016666"], ["blaze_pizza"], 300),
    ("bob-evans", "Bob Evans", ["bob-evans"], ["Q4932386"], ["bob_evans_us"], 430),
    ("bonefish-grill", "Bonefish Grill", ["bonefish-grill"], ["Q4941599"], ["bonefish_grill"], 170),
    ("bravo-italian-kitchen", "BRAVO! Italian Kitchen", ["bravo-italian-kitchen"], ["Q64055574"], ["bravo_italian_us"], 15),
    ("buffalo-wild-wings", "Buffalo Wild Wings", ["buffalo-wild-wings"], ["Q509255"], ["buffalo_wild_wings_us"], 1200),
    ("california-pizza-kitchen", "California Pizza Kitchen", ["california-pizza-kitchen"], ["Q15109854"], ["california_pizza_kitchen"], 130),
    ("charleys", "Charleys Cheesesteaks", ["charleys-cheesesteaks"], ["Q1066777"], ["charleys_philly_steaks"], 600),
    ("chilis", "Chili's", ["chili-s"], ["Q1072948"], ["chilis"], 1200),
    ("dennys", "Denny's", ["denny-s"], ["Q1189695"], ["dennys_us"], 1400),
    ("farmer-boys", "Farmer Boys", ["farmer-boys"], ["Q5435711"], ["farmer_boys"], 100),
    ("freddys", "Freddy's Frozen Custard & Steakburgers", ["freddy-s-frozen-custard-and-steakburgers"], ["Q5496837"], ["freddys_us"], 530),
    ("golden-corral", "Golden Corral", ["golden-corral"], ["Q4039560"], ["golden_corral"], 350),
    ("hard-rock-cafe", "Hard Rock Cafe", ["hard-rock-cafe"], ["Q918151"], ["hard_rock"], 30),
    ("hopdoddy", "Hopdoddy Burger Bar", ["hopdoddy-burger-bar"], ["Q123689179"], ["hopdoddy_burger_bar_us"], 40),
    ("hy-vee", "Hy-Vee", ["hy-vee", "hy-vee-groceries"], ["Q1639719"], ["hy_vee_us"], 290),
    ("ihop", "IHOP", ["ihop"], ["Q1185675"], ["ihop"], 1600),
    ("in-n-out", "In-N-Out Burger", ["in-n-out-burger"], ["Q1205312"], ["innout"], 400),
    ("kekes", "Keke's Breakfast Cafe", ["keke-s-breakfast-cafe"], ["Q115930150"], ["keke"], 70),
    ("little-caesars", "Little Caesars", ["little-caesars"], ["Q1393809"], ["little_caesars_us"], 4000),
    ("logans-roadhouse", "Logan's Roadhouse", ["logan-s-roadhouse"], ["Q6666872"], ["logans_roadhouse_us"], 100),
    ("lucilles", "Lucille's Smokehouse BBQ", ["lucille-s-smokehouse-bbq"], ["Q17019306"], ["lucilles_smokehouse_bar_b_que_us"], 20),
    ("main-event", "Main Event", ["main-event"], ["Q56062981"], ["main_event"], 60),
    ("olive-garden", "Olive Garden", ["olive-garden"], ["Q3045312"], ["olive_garden"], 900),
    ("outback", "Outback Steakhouse", ["outback-steakhouse"], ["Q1064893"], ["outback_steakhouse"], 690),
    ("piada", "Piada Italian Street Food", ["piada-italian-street-food"], ["Q7190020"], ["piada_us"], 50),
    ("pilot-flying-j", "Pilot & Flying J", ["pilot-and-flying-j"], ["Q64128179", "Q64130592"], ["pilot_flying_j"], 750),
    ("red-lobster", "Red Lobster", ["red-lobster"], ["Q846301"], ["red_lobster_us"], 550),
    ("red-robin", "Red Robin", ["red-robin"], ["Q7304886"], ["red_robin"], 500),
    ("ruby-tuesday", "Ruby Tuesday", ["ruby-tuesday"], ["Q7376400"], ["ruby_tuesday_us"], 200),
    ("shake-shack", "Shake Shack", ["shake-shack"], ["Q1058722"], ["shake_shack"], 330),
    ("sheetz", "Sheetz", ["sheetz"], ["Q7492551"], ["sheetz"], 750),
    ("shoneys", "Shoney's", ["shoney-s"], ["Q7500392"], ["shoneys_us"], 100),
    ("sizzler", "Sizzler", ["sizzler"], ["Q1848822"], ["sizzler_us"], 70),
    ("smashburger", "Smashburger", ["smashburger"], ["Q17061332"], ["smashburger"], 200),
    ("texas-roadhouse", "Texas Roadhouse", ["texas-roadhouse"], ["Q7707945"], ["texas_roadhouse"], 650),
    ("tgi-fridays", "TGI Fridays", ["tgi-fridays"], ["Q1524184"], ["tgi_fridays_us"], 90),
    ("torchys", "Torchy's Tacos", ["torchy-s-tacos"], ["Q106769573"], ["torchys_tacos_us"], 130),
    ("twin-peaks", "Twin Peaks", ["twin-peaks"], ["Q7858255"], ["twin_peaks"], 110),
    ("wendys", "Wendy's", ["wendy-s"], ["Q550258"], ["wendys"], 6000),
    ("white-castle", "White Castle", ["white-castle"], ["Q1244034"], ["white_castle"], 340),
    ("yard-house", "Yard House", ["yard-house"], ["Q21189156"], ["yard_house"], 90),
    ("benihana", "Benihana", ["benihana"], ["Q4887996"], ["benihana"], 75),
    ("carrabbas", "Carrabba's Italian Grill", ["carrabba-s-italian-grill"], ["Q5045999"], ["carrabbas_italian_grill"], 200),
    ("chipotle", "Chipotle", ["chipotle"], ["Q465751"], ["chipotle"], 3600),
    ("firehouse-subs", "Firehouse Subs", ["firehouse-subs"], ["Q5451873"], ["firehouse_subs"], 1200),
    ("hooters", "Hooters", ["hooters"], ["Q1025921"], ["hooters"], 250),
    ("longhorn", "LongHorn Steakhouse", ["longhorn-steakhouse"], ["Q3259007"], ["longhorn_steakhouse"], 580),
    ("rubios", "Rubio's Coastal Grill", ["rubio-s-coastal-grill"], ["Q7376154"], ["rubios_us"], 80),
    ("eatn-park", "Eat'n Park", ["eat-n-park"], ["Q5331211"], ["eatn_park_us"], 50),
    ("fogo-de-chao", "Fogo de Chão", ["fogo-de-ch-o"], ["Q5464133"], ["fogo_de_chao"], 60),
    ("joes-crab-shack", "Joe's Crab Shack", ["joe-s-crab-shack"], ["Q6208210"], ["joes_crab_shack_us"], 15),
    ("mccormick-schmicks", "McCormick & Schmick's", ["mccormick-and-schmick-s"], ["Q6800562"], ["mccormick_and_schmicks_us"], 12),
    ("playa-bowls", "Playa Bowls", ["playa-bowls"], ["Q114618507"], ["playa_bowls_us"], 280),
    ("biggby", "Biggby Coffee", ["biggby-coffee"], ["Q4906876"], ["biggby_coffee_us"], 300),
    ("brueggers", "Bruegger's Bagels", ["bruegger-s-bagels"], ["Q4978656"], ["brueggers"], 200),
    ("caseys", "Casey's", ["casey-s"], ["Q2940968"], ["caseys_general_store_us"], 2900),
    ("dunkin", "Dunkin'", ["dunkin"], ["Q847743"], ["dunkin_us"], 9500),
    ("einstein-bros", "Einstein Bros. Bagels", ["einstein-bros-bagels"], ["Q5349788"], ["einstein_bros_us"], 650),
    ("7-brew", "7 Brew", ["7-brew"], ["Q131838275", "Q127688691"], ["7_brew_us"], 400),
    ("starbucks", "Starbucks", ["starbucks"], ["Q37158"], ["starbucks_us"], 16000),
    ("tcby", "TCBY", ["tcby"], ["Q7669631"], ["tcby"], 200),
    ("waba-grill", "WaBa Grill", ["waba-grill"], ["Q113163467"], ["waba_grill_us"], 200),
    ("kohls", "Kohl's", ["kohl-s"], ["Q967265"], ["kohls_us"], 1150),
    ("walgreens", "Walgreens", ["walgreens"], ["Q1591889"], ["walgreens"], 8000),
    ("publix", "Publix", ["publix"], ["Q672170"], ["publix_us"], 1400),
    ("food-lion", "Food Lion", ["food-lion"], ["Q1435950"], ["food_lion_us"], 1100),
    ("great-clips", "Great Clips", ["great-clips"], ["Q5598967"], ["great_clips"], 4200),
    ("sport-clips", "Sport Clips", ["sport-clips"], ["Q7579310"], ["sport_clips_us"], 1800),
    ("dave-and-busters", "Dave & Buster's", ["dave-and-buster-s"], ["Q5228205"], ["dave_and_busters"], 230),
    ("tractor-supply", "Tractor Supply", ["tractor-supply"], ["Q15109925"], ["tractor_supply"], 2250),
]

# No All The Places spider found (searched spider names across the last 7
# runs and the 2026-10-24 Wikidata insights file).
NO_SPIDER = [
    ("bar-louie", "Bar Louie", ["bar-louie"], ["Q16935493"]),
    ("bombshells", "Bombshells Restaurant & Bar", ["bombshells-restaurant-and-bar"], []),
    ("brio", "Brio Italian Grille", ["brio-italian-grille"], ["Q64055835"]),
    ("claim-jumper", "Claim Jumper", ["claim-jumper"], ["Q5125081"]),
    ("cotton-patch", "Cotton Patch Cafe", ["cotton-patch-cafe"], ["Q5175713"]),
    ("hacienda", "Hacienda Mexican Restaurant", ["hacienda-mexican-restaurant"], []),
    ("haven-hot-chicken", "Haven Hot Chicken", ["haven-hot-chicken"], []),
    ("hofs-hut", "Hof's Hut", ["hof-s-hut"], []),
    ("hoss-s", "Hoss's Steak & Sea House", ["hoss-s-steak-and-sea-house"], ["Q5908897"]),
    ("lazy-dog", "Lazy Dog Restaurants", ["lazy-dog-restaurants"], ["Q111304278"]),
    ("mission-bbq", "Mission BBQ", ["mission-bbq"], ["Q85785905"]),
    ("newks", "Newk's Eatery", ["newk-s-eatery"], []),
    ("paisanos", "Paisano's Pizza", ["paisano-s-pizza"], []),
    ("pluckers", "Pluckers Wing Bar", ["pluckers-wing-bar"], []),
    ("rock-and-brews", "Rock & Brews", ["rock-and-brews"], []),
    ("tuscan-brands", "Tuscan Brands", ["tuscan-brands"], []),
    ("110-grill", "110 Grill", ["110-grill"], ["Q121292194"]),
    ("capriottis", "Capriotti's Sandwich Shop", ["capriotti-s-sandwich-shop"], ["Q5036283"]),
    ("firebirds", "Firebirds Wood Fired Grill", ["firebirds-wood-fired-grill"], []),
    ("stk", "STK Steakhouse", ["stk-steakhouse"], []),
    ("carolina-ale-house", "Carolina Ale House", ["carolina-ale-house"], []),
    ("54th-street", "54th Street Grill", ["54th-street-grill"], ["Q131290500"]),
    ("centraarchy", "CentraArchy Restaurants", ["centraarchy-restaurants"], []),
    ("chicken-salad-chick", "Chicken Salad Chick", ["chicken-salad-chick"], ["Q19720749"]),
    ("margaritas", "Margaritas Mexican Restaurant", ["margaritas-mexican-restaurant"], ["Q6760185"]),
    ("tocaya", "Tocaya", ["tocaya"], []),
    ("151-coffee", "151 Coffee", ["151-coffee"], []),
    ("marzonis", "Marzoni's Brick Oven & Brewing", ["marzoni-s-brick-oven-and-brewing"], []),
    ("teds-bulletin", "Ted's Bulletin", ["ted-s-bulletin"], []),
    ("rack-room-shoes", "Rack Room Shoes", ["rack-room-shoes"], ["Q17109937"]),
    ("the-exchange", "The Exchange (AAFES)", ["the-exchange-aafes"], []),
    ("autonation", "AutoNation", ["autonation"], ["Q784804"]),
]

# An ATP spider exists, but its stores carry no brand:wikidata, so the brand
# match can't be proven (SPEC 6.2 keeps only features whose brand:wikidata
# matches). Treated like NO_SPIDER: the site shows a "Find nearest" map link.
SPIDER_WITHOUT_WIKIDATA = [
    ("aspen-creek-grill", "Aspen Creek Grill", ["aspen-creek-grill"], "aspen_creek_grill_us"),
    ("biscuit-belly", "Biscuit Belly", ["biscuit-belly"], "biscuit_belly_us"),
    ("eddie-merlots", "Eddie Merlot's", ["eddie-merlot-s"], "eddie_merlots_us"),
    ("el-chico", "El Chico", ["el-chico"], "el_chico_us"),
    ("eureka", "Eureka!", ["eureka"], "eureka_us"),
    ("veterans-canteen", "Veterans Canteen Service (VA medical centers)", ["veterans-canteen-service"], "department_veterans_affairs"),
    ("wob", "WOB Bar & Kitchen (World of Beer)", ["wob-bar-and-kitchen"], "world_of_beer_us"),
    ("perrys", "Perry's Steakhouse & Grille", ["perry-s-steakhouse-and-grille"], "perrys_steakhouse_and_grille_us"),
    ("viva-chicken", "Viva Chicken", ["viva-chicken"], "viva_chicken"),
    ("pollys-pies", "Polly's Pies", ["polly-s-pies"], "pollys_pies_us"),
]

# Offers with no store at all: shown in the "Everywhere" section.
NO_STORE = ["national-parks", "grace-for-vets"]


def main() -> None:
    seed = {o["slug"]: o for o in json.loads((ROOT / "data/seed/offers-2026.json").read_text(encoding="utf-8"))["offers"]}
    brands = {}
    for slug, name, offers, qids, spiders, expected in WITH_SPIDER:
        brands[slug] = {"name": name, "offers": offers, "brand_wikidata": qids,
                        "atp_spiders": spiders, "expected_us": expected}
    for slug, name, offers, qids in NO_SPIDER:
        entry = {"name": name, "offers": offers, "brand_wikidata": qids,
                 "atp_spiders": [], "status": "no_spider"}
        if not qids:
            entry["wikidata"] = "unknown"
        brands[slug] = entry
    for slug, name, offers, spider in SPIDER_WITHOUT_WIKIDATA:
        brands[slug] = {"name": name, "offers": offers, "brand_wikidata": [],
                        "atp_spiders": [], "status": "no_spider", "wikidata": "unknown",
                        "atp_spider_without_wikidata": spider}
    # 7 Brew's spider gives no address fields for most stores, only the store
    # page URL (locations.7brew.com/{state}/{city}/{street}). The address is
    # read from that URL and kept only if the Census Geocoder matches it.
    brands["7-brew"]["ref_address_pattern"] = (
        r"locations\.7brew\.com/(?P<s>[a-z]{2})/(?P<c>[^/]+)/(?P<a>[^/?#]+)")
    covered = {o for b in brands.values() for o in b["offers"]} | set(NO_STORE)
    need = {s for s, o in seed.items() if o["scope"] != "single_location"}
    assert need == covered, (need - covered, covered - need)
    out = {
        "_readme": (
            "Brand -> All The Places spiders and Wikidata Q-ids, found by research "
            "(see tools/make_brands.py). Q-ids are checked on wikidata.org by "
            "pipeline/wikidata.py; results in data/wikidata-check.json. expected_us is an "
            "approximate public U.S. store count used only to flag low coverage in "
            "data/coverage.md; it is never shown to visitors. status 'no_spider' means "
            "All The Places has no data for the brand: the site shows a 'Find nearest' "
            "map link instead of stores."
        ),
        "no_store_offers": NO_STORE,
        "brands": brands,
    }
    (ROOT / "data/brands.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    print(len(brands), "brands;", sum(1 for b in brands.values() if b["atp_spiders"]), "with spiders")


if __name__ == "__main__":
    main()
