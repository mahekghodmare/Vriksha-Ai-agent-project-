"""
species_db.py
-------------
Knowledge base for the Vriksha plantation agent.

This is the agent's "world model": a curated table of trees that grow well in
Indian conditions, with the traits the planning tools actually reason over.

All numeric values are planning-grade estimates compiled from forestry and
urban-greening literature (CO2 figures are per mature tree per year, and vary
with site quality). They are good enough for a design decision, not for a
carbon credit filing.

Field notes
-----------
layer          canopy | sub_canopy | understory | shrub   (used for Miyawaki layering)
water          1 = very drought hardy ... 5 = needs assured water
root_risk      0 = safe near paving ... 3 = lifts kerbs, avoid near buildings/pipes
pollinator     0..5  value to bees, butterflies and birds
air_score      0..5  dust capture / pollution tolerance on roadsides
shade          0..5  usable shade for people sitting or walking under it
"""

SOILS = ["black_cotton", "red_laterite", "alluvial", "sandy", "rocky_murrum", "clay_loam"]

PURPOSES = {
    "urban_avenue": "Roadside / avenue planting",
    "campus_shade": "Campus, school or park shade",
    "miyawaki": "Miyawaki dense native forest patch",
    "carbon_sink": "Carbon sequestration plot",
    "biodiversity": "Biodiversity and bird habitat",
    "food_forest": "Fruit and food forest",
    "soil_water": "Soil conservation / water recharge",
    "pollution_barrier": "Industrial or highway pollution barrier",
}

# fmt: off
SPECIES = [
    dict(key="neem", common="Neem", botanical="Azadirachta indica", local="Kadunimb / Neem",
         layer="canopy", height=18, canopy_r=6.0, growth="medium", water=1, evergreen=True,
         soils=["black_cotton", "red_laterite", "sandy", "rocky_murrum", "alluvial", "clay_loam"],
         rain_min=400, co2=32, pollinator=4, air_score=5, shade=4, root_risk=1, cost=45,
         uses=["medicinal", "pest_repellent"], native=True,
         note="The default hardy street tree of central India. Tolerates heat, dust and poor soil."),

    dict(key="arjun", common="Arjun", botanical="Terminalia arjuna", local="Arjun",
         layer="canopy", height=22, canopy_r=7.0, growth="medium", water=3, evergreen=True,
         soils=["alluvial", "clay_loam", "black_cotton"], rain_min=750, co2=45,
         pollinator=4, air_score=4, shade=5, root_risk=2, cost=50,
         uses=["medicinal", "riverbank"], native=True,
         note="Riverbank specialist, heavy carbon fixer, host tree for tasar silk moths."),

    dict(key="banyan", common="Banyan", botanical="Ficus benghalensis", local="Vad",
         layer="canopy", height=25, canopy_r=12.0, growth="slow", water=2, evergreen=True,
         soils=["black_cotton", "alluvial", "clay_loam", "rocky_murrum"], rain_min=600, co2=55,
         pollinator=5, air_score=4, shade=5, root_risk=3, cost=60,
         uses=["keystone", "bird_habitat"], native=True,
         note="Keystone bird species. Needs open ground; never plant near buildings or drains."),

    dict(key="peepal", common="Peepal", botanical="Ficus religiosa", local="Pimpal",
         layer="canopy", height=24, canopy_r=9.0, growth="medium", water=2, evergreen=False,
         soils=["black_cotton", "alluvial", "rocky_murrum", "clay_loam"], rain_min=500, co2=50,
         pollinator=5, air_score=5, shade=5, root_risk=3, cost=50,
         uses=["keystone", "bird_habitat"], native=True,
         note="High oxygen output and fig crop for birds; aggressive roots, keep 8 m off structures."),

    dict(key="karanj", common="Karanj", botanical="Pongamia pinnata", local="Karanj",
         layer="canopy", height=15, canopy_r=6.0, growth="medium", water=2, evergreen=True,
         soils=["black_cotton", "sandy", "alluvial", "clay_loam", "rocky_murrum"], rain_min=500, co2=30,
         pollinator=5, air_score=5, shade=4, root_risk=1, cost=45,
         uses=["biodiesel", "nitrogen_fixing", "medicinal"], native=True,
         note="Nitrogen fixer that improves the soil around it. Excellent low-maintenance avenue tree."),

    dict(key="jamun", common="Jamun", botanical="Syzygium cumini", local="Jambhul",
         layer="canopy", height=20, canopy_r=6.5, growth="medium", water=3, evergreen=True,
         soils=["alluvial", "clay_loam", "black_cotton"], rain_min=700, co2=38,
         pollinator=5, air_score=4, shade=5, root_risk=2, cost=55,
         uses=["fruit", "medicinal", "bird_habitat"], native=True,
         note="Fruit for people and birds; tolerates waterlogging better than most canopy trees."),

    dict(key="mango", common="Mango", botanical="Mangifera indica", local="Amba",
         layer="canopy", height=18, canopy_r=7.0, growth="medium", water=3, evergreen=True,
         soils=["alluvial", "clay_loam", "red_laterite"], rain_min=700, co2=36,
         pollinator=4, air_score=3, shade=5, root_risk=2, cost=90,
         uses=["fruit"], native=True,
         note="Grafted saplings fruit in 4-5 years. Keep away from dusty roadsides."),

    dict(key="tamarind", common="Tamarind", botanical="Tamarindus indica", local="Chinch",
         layer="canopy", height=20, canopy_r=8.0, growth="slow", water=1, evergreen=True,
         soils=["black_cotton", "red_laterite", "rocky_murrum", "sandy"], rain_min=500, co2=40,
         pollinator=4, air_score=4, shade=5, root_risk=1, cost=55,
         uses=["fruit", "windbreak"], native=True,
         note="Extremely long lived and drought hardy; slow to establish but nearly permanent."),

    dict(key="kadamb", common="Kadamb", botanical="Neolamarckia cadamba", local="Kadamb",
         layer="canopy", height=20, canopy_r=6.0, growth="fast", water=4, evergreen=False,
         soils=["alluvial", "clay_loam"], rain_min=900, co2=42,
         pollinator=5, air_score=3, shade=4, root_risk=1, cost=50,
         uses=["fast_cover", "fragrance"], native=True,
         note="Fastest native canopy filler where water is assured; poor choice in dry plots."),

    dict(key="gulmohar", common="Gulmohar", botanical="Delonix regia", local="Gulmohar",
         layer="sub_canopy", height=12, canopy_r=6.0, growth="fast", water=2, evergreen=False,
         soils=["black_cotton", "sandy", "red_laterite", "rocky_murrum"], rain_min=500, co2=22,
         pollinator=3, air_score=3, shade=4, root_risk=2, cost=40,
         uses=["ornamental"], native=False,
         note="Exotic ornamental. Brittle branches; use sparingly and never as the backbone species."),

    dict(key="amla", common="Amla", botanical="Phyllanthus emblica", local="Awla",
         layer="sub_canopy", height=10, canopy_r=3.5, growth="medium", water=2, evergreen=False,
         soils=["red_laterite", "rocky_murrum", "black_cotton", "sandy"], rain_min=500, co2=18,
         pollinator=4, air_score=3, shade=3, root_risk=0, cost=60,
         uses=["fruit", "medicinal"], native=True,
         note="Hardy medicinal fruit tree, fits in narrow strips under 4 m wide."),

    dict(key="bel", common="Bel", botanical="Aegle marmelos", local="Bel",
         layer="sub_canopy", height=10, canopy_r=3.5, growth="slow", water=1, evergreen=False,
         soils=["rocky_murrum", "red_laterite", "black_cotton"], rain_min=450, co2=16,
         pollinator=4, air_score=3, shade=3, root_risk=0, cost=55,
         uses=["fruit", "medicinal", "temple"], native=True,
         note="Thrives on stony, shallow, degraded ground where most species fail."),

    dict(key="bahava", common="Amaltas", botanical="Cassia fistula", local="Bahava",
         layer="sub_canopy", height=12, canopy_r=4.5, growth="medium", water=1, evergreen=False,
         soils=["black_cotton", "rocky_murrum", "red_laterite", "sandy"], rain_min=450, co2=20,
         pollinator=4, air_score=3, shade=3, root_risk=0, cost=40,
         uses=["ornamental", "medicinal"], native=True,
         note="Drought proof flowering tree; its summer bloom is the classic pre-monsoon signal."),

    dict(key="putranjiva", common="Putranjiva", botanical="Putranjiva roxburghii", local="Putranjiva",
         layer="sub_canopy", height=12, canopy_r=4.0, growth="slow", water=2, evergreen=True,
         soils=["alluvial", "clay_loam", "black_cotton"], rain_min=600, co2=20,
         pollinator=3, air_score=5, shade=4, root_risk=0, cost=65,
         uses=["dust_screen", "evergreen_screen"], native=True,
         note="Dense evergreen foliage, one of the best dust and noise screens for narrow verges."),

    dict(key="ashoka", common="Sita Ashoka", botanical="Saraca asoca", local="Ashok",
         layer="understory", height=8, canopy_r=2.5, growth="slow", water=4, evergreen=True,
         soils=["alluvial", "clay_loam", "red_laterite"], rain_min=900, co2=12,
         pollinator=5, air_score=3, shade=3, root_risk=0, cost=85,
         uses=["ornamental", "medicinal"], native=True,
         note="Shade loving understory tree; plant only under an existing or planned canopy."),

    dict(key="curry", common="Curry Leaf", botanical="Murraya koenigii", local="Kadipatta",
         layer="understory", height=5, canopy_r=1.5, growth="fast", water=2, evergreen=True,
         soils=["alluvial", "clay_loam", "red_laterite", "sandy", "black_cotton"], rain_min=500, co2=7,
         pollinator=4, air_score=2, shade=1, root_risk=0, cost=25,
         uses=["kitchen", "butterfly_host"], native=True,
         note="Host plant for common lime butterflies and a kitchen crop in the same footprint."),

    dict(key="custard", common="Custard Apple", botanical="Annona squamosa", local="Sitaphal",
         layer="understory", height=6, canopy_r=2.0, growth="medium", water=1, evergreen=False,
         soils=["rocky_murrum", "red_laterite", "black_cotton", "sandy"], rain_min=450, co2=9,
         pollinator=3, air_score=2, shade=2, root_risk=0, cost=45,
         uses=["fruit"], native=False,
         note="Naturalised fruit tree for dry, stony plots; fruits from year three."),

    dict(key="jasvand", common="Hibiscus", botanical="Hibiscus rosa-sinensis", local="Jaswand",
         layer="shrub", height=3, canopy_r=1.2, growth="fast", water=3, evergreen=True,
         soils=["alluvial", "clay_loam", "red_laterite", "sandy"], rain_min=600, co2=4,
         pollinator=5, air_score=2, shade=0, root_risk=0, cost=20,
         uses=["nectar", "hedge"], native=False,
         note="Year-round nectar for sunbirds; fills the shrub layer of a Miyawaki block cheaply."),

    dict(key="adulsa", common="Adulsa", botanical="Justicia adhatoda", local="Adulsa",
         layer="shrub", height=2.5, canopy_r=1.0, growth="fast", water=1, evergreen=True,
         soils=["black_cotton", "rocky_murrum", "red_laterite", "sandy", "clay_loam"], rain_min=400, co2=3,
         pollinator=4, air_score=3, shade=0, root_risk=0, cost=18,
         uses=["medicinal", "hedge"], native=True,
         note="Unpalatable to cattle, so it doubles as a living guard hedge around a new plot."),

    dict(key="vetiver", common="Vetiver", botanical="Chrysopogon zizanioides", local="Vala / Khus",
         layer="shrub", height=1.5, canopy_r=0.5, growth="fast", water=2, evergreen=True,
         soils=["black_cotton", "red_laterite", "sandy", "alluvial", "clay_loam", "rocky_murrum"],
         rain_min=400, co2=2, pollinator=1, air_score=2, shade=0, root_risk=0, cost=8,
         uses=["erosion_control", "water_recharge"], native=True,
         note="Roots go 2-3 m straight down. The standard bund and slope stabiliser before tree planting."),

    dict(key="bamboo", common="Bamboo (Manga)", botanical="Bambusa balcooa", local="Bambu",
         layer="sub_canopy", height=15, canopy_r=2.5, growth="fast", water=3, evergreen=True,
         soils=["alluvial", "clay_loam", "red_laterite", "black_cotton"], rain_min=700, co2=48,
         pollinator=1, air_score=4, shade=3, root_risk=1, cost=70,
         uses=["fast_carbon", "windbreak", "livelihood"], native=True,
         note="Highest short-term carbon capture per hectare and harvestable from year five."),

    dict(key="shisham", common="Shisham", botanical="Dalbergia sissoo", local="Shisav",
         layer="canopy", height=18, canopy_r=5.5, growth="fast", water=2, evergreen=False,
         soils=["alluvial", "sandy", "clay_loam"], rain_min=600, co2=35,
         pollinator=3, air_score=4, shade=4, root_risk=2, cost=45,
         uses=["nitrogen_fixing", "timber"], native=True,
         note="Nitrogen fixing fast grower for riverine and sandy ground; suckers freely."),

    dict(key="saptaparni", common="Saptaparni", botanical="Alstonia scholaris", local="Saptaparni",
         layer="canopy", height=18, canopy_r=5.0, growth="fast", water=3, evergreen=True,
         soils=["alluvial", "clay_loam", "red_laterite"], rain_min=800, co2=34,
         pollinator=3, air_score=5, shade=4, root_risk=1, cost=50,
         uses=["dust_screen"], native=True,
         note="Dense evergreen crown for pollution screening. Strong autumn flower scent, so keep it off hospital frontage."),

    dict(key="sesbania", common="Shevri", botanical="Sesbania grandiflora", local="Hadga",
         layer="sub_canopy", height=8, canopy_r=2.5, growth="fast", water=3, evergreen=False,
         soils=["alluvial", "clay_loam", "black_cotton"], rain_min=700, co2=15,
         pollinator=4, air_score=2, shade=2, root_risk=0, cost=15,
         uses=["nitrogen_fixing", "nurse_tree", "fodder"], native=True,
         note="Short lived nurse tree: shelters slow species for 4-5 years, then makes way for them."),
]
# fmt: on

BY_KEY = {s["key"]: s for s in SPECIES}

GROWTH_FACTOR = {"fast": 1.25, "medium": 1.0, "slow": 0.75}

# Purpose -> weights the selector uses when scoring a species.
PURPOSE_WEIGHTS = {
    "urban_avenue":      dict(shade=3.0, air=2.5, root=3.0, co2=1.0, pollinator=0.8, native=1.0, fruit=-0.5),
    "campus_shade":      dict(shade=3.0, air=1.0, root=1.5, co2=1.2, pollinator=1.5, native=1.2, fruit=1.0),
    "miyawaki":          dict(shade=0.8, air=1.0, root=0.2, co2=2.0, pollinator=2.0, native=3.0, fruit=0.5),
    "carbon_sink":       dict(shade=0.5, air=0.5, root=0.2, co2=3.5, pollinator=0.5, native=1.5, fruit=0.2),
    "biodiversity":      dict(shade=1.0, air=0.5, root=0.2, co2=1.0, pollinator=3.5, native=3.0, fruit=1.5),
    "food_forest":       dict(shade=1.0, air=0.3, root=0.5, co2=0.8, pollinator=2.0, native=1.0, fruit=3.5),
    "soil_water":        dict(shade=0.5, air=0.5, root=0.0, co2=1.5, pollinator=1.0, native=2.5, fruit=0.5),
    "pollution_barrier": dict(shade=1.0, air=3.5, root=1.0, co2=1.5, pollinator=0.5, native=1.5, fruit=-1.0),
}

# Layer mix targets (share of total saplings) by purpose.
LAYER_MIX = {
    "urban_avenue":      {"canopy": 0.70, "sub_canopy": 0.30, "understory": 0.0, "shrub": 0.0},
    "campus_shade":      {"canopy": 0.55, "sub_canopy": 0.25, "understory": 0.15, "shrub": 0.05},
    "miyawaki":          {"canopy": 0.30, "sub_canopy": 0.30, "understory": 0.25, "shrub": 0.15},
    "carbon_sink":       {"canopy": 0.70, "sub_canopy": 0.25, "understory": 0.05, "shrub": 0.0},
    "biodiversity":      {"canopy": 0.35, "sub_canopy": 0.25, "understory": 0.25, "shrub": 0.15},
    "food_forest":       {"canopy": 0.35, "sub_canopy": 0.30, "understory": 0.25, "shrub": 0.10},
    "soil_water":        {"canopy": 0.40, "sub_canopy": 0.25, "understory": 0.15, "shrub": 0.20},
    "pollution_barrier": {"canopy": 0.45, "sub_canopy": 0.35, "understory": 0.10, "shrub": 0.10},
}

# Monsoon onset week (approx.) by region, used by the calendar tool.
REGION_MONSOON = {
    "Vidarbha / Central India": ("15 June", "30 September", 6),
    "Konkan / West Coast": ("07 June", "10 October", 6),
    "Marathwada / Dry Deccan": ("18 June", "25 September", 6),
    "North India / Gangetic Plain": ("25 June", "30 September", 6),
    "South India / Deccan Plateau": ("05 June", "15 October", 6),
    "East India / Bengal": ("10 June", "10 October", 6),
    "Northeast India": ("01 June", "30 October", 5),
}
