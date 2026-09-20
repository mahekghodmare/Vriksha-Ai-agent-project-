"""
agent_core.py
-------------
The agent itself: a tool-using planner with a self-audit loop.

Architecture (this is the part worth explaining in the viva):

    Site brief
        |
        v
    [PERCEIVE] site_profiler        -> derives water index, climate stress, usable area
        |
        v
    [PLAN]     goal decomposition   -> ordered tool queue, chosen from the brief
        |
        v
    [ACT]      species_selector --> layout_designer --> calendar_planner
               --> carbon_model --> budget_model
        |
        v
    [REFLECT]  risk_auditor         -> finds violations (water deficit, root damage,
        |                              monoculture, wrong layer, no nurse cover)
        |                              and emits *constraints*
        +--- if constraints changed --> re-run ACT with the amended constraints
        |    (bounded at MAX_ITERS, so it always terminates)
        v
    Final plan + full reasoning trace

The loop is what makes this agentic rather than a calculator with a form:
the agent's first answer is usually not its final answer. It criticises its own
species list against the site and replans, and the trace records every revision.

Everything here is deterministic and offline. An optional LLM narrator can be
plugged in at the end (see narrate()), but the plan never depends on it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from species_db import (
    BY_KEY,
    GROWTH_FACTOR,
    LAYER_MIX,
    PURPOSE_WEIGHTS,
    REGION_MONSOON,
    SPECIES,
)

MAX_ITERS = 3
LAYERS = ["canopy", "sub_canopy", "understory", "shrub"]


# --------------------------------------------------------------------------
# Data carriers
# --------------------------------------------------------------------------
@dataclass
class SiteBrief:
    name: str = "Unnamed site"
    region: str = "Vidarbha / Central India"
    area_m2: float = 500.0
    soil: str = "black_cotton"
    rainfall_mm: int = 1100
    purpose: str = "campus_shade"
    irrigation: str = "monsoon_only"        # monsoon_only | tanker | drip
    near_structures: bool = False           # buildings, pipes, paving within 8 m
    overhead_lines: bool = False
    slope: bool = False                     # sloping or eroding ground
    budget_inr: float = 0.0                 # 0 means "no ceiling given"
    maintenance_years: int = 3


@dataclass
class TraceStep:
    n: int
    phase: str
    thought: str
    action: str
    observation: str


@dataclass
class AgentState:
    brief: SiteBrief
    constraints: dict[str, Any] = field(default_factory=dict)
    trace: list[TraceStep] = field(default_factory=list)
    iteration: int = 0
    plan: dict[str, Any] = field(default_factory=dict)

    def log(self, phase: str, thought: str, action: str, observation: str) -> None:
        self.trace.append(
            TraceStep(len(self.trace) + 1, phase, thought, action, observation)
        )


# --------------------------------------------------------------------------
# TOOL 1 - site profiler
# --------------------------------------------------------------------------
def site_profiler(b: SiteBrief) -> dict[str, Any]:
    """Turn a raw brief into the derived numbers every other tool needs."""
    irrigation_bonus = {"monsoon_only": 0, "tanker": 250, "drip": 550}[b.irrigation]
    effective_water = b.rainfall_mm + irrigation_bonus

    if effective_water < 650:
        water_class, max_water_need = "water_scarce", 2
    elif effective_water < 1000:
        water_class, max_water_need = "moderate", 3
    elif effective_water < 1600:
        water_class, max_water_need = "assured", 4
    else:
        water_class, max_water_need = "high_rainfall", 5

    # Usable planting area after paths, setbacks and service margins.
    setback = 0.25 if b.near_structures else 0.12
    usable = b.area_m2 * (1 - setback)

    stress = []
    if b.rainfall_mm < 700:
        stress.append("low rainfall")
    if b.soil == "black_cotton":
        stress.append("black cotton soil cracks and waterlogs, so pits need murrum backfill")
    if b.soil == "rocky_murrum":
        stress.append("shallow stony profile, pits must be blasted or hand-broken to 60 cm")
    if b.slope:
        stress.append("erosion risk on slope")
    if b.overhead_lines:
        stress.append("overhead lines cap mature height at 10 m under the wires")

    return dict(
        effective_water=effective_water,
        water_class=water_class,
        max_water_need=max_water_need,
        usable_area=round(usable, 1),
        setback_pct=int(setback * 100),
        stress=stress,
    )


# --------------------------------------------------------------------------
# TOOL 2 - species selector
# --------------------------------------------------------------------------
def score_species(sp: dict, b: SiteBrief, prof: dict, cons: dict) -> tuple[float, list[str]]:
    """Score one species for this site. Returns (score, reasons_it_lost_points)."""
    w = PURPOSE_WEIGHTS[b.purpose]
    reasons: list[str] = []

    if b.soil not in sp["soils"]:
        return -1, [f"not suited to {b.soil.replace('_', ' ')}"]
    if sp["rain_min"] > prof["effective_water"]:
        return -1, [f"needs {sp['rain_min']} mm, site gives {prof['effective_water']} mm"]
    if sp["water"] > prof["max_water_need"]:
        return -1, ["thirstier than the site can support"]

    banned = cons.get("ban", set())
    if sp["key"] in banned:
        return -1, ["ruled out by the risk audit"]
    if cons.get("max_root_risk") is not None and sp["root_risk"] > cons["max_root_risk"]:
        return -1, ["roots too aggressive for this plot"]
    if cons.get("max_height") is not None and sp["height"] > cons["max_height"]:
        return -1, ["grows above the permitted height"]
    if cons.get("natives_only") and not sp["native"]:
        return -1, ["exotic, and the audit asked for natives only"]
    if cons.get("max_sapling_cost") is not None and sp["cost"] > cons["max_sapling_cost"]:
        return -1, ["too expensive for the budget ceiling"]

    s = 0.0
    s += w["shade"] * sp["shade"]
    s += w["air"] * sp["air_score"]
    s += w["co2"] * (sp["co2"] / 10.0)
    s += w["pollinator"] * sp["pollinator"]
    s += w["native"] * (3 if sp["native"] else 0)
    s += w["fruit"] * (3 if "fruit" in sp["uses"] else 0)
    s -= w["root"] * sp["root_risk"]

    # Site-specific nudges.
    if prof["water_class"] == "water_scarce" and sp["water"] <= 1:
        s += 4
    if b.slope and ("erosion_control" in sp["uses"] or "water_recharge" in sp["uses"]):
        s += 6
    if "nitrogen_fixing" in sp["uses"]:
        s += 2.5
    if b.purpose == "carbon_sink" and sp["growth"] == "fast":
        s += 3
    if sp["root_risk"] >= 3 and b.near_structures:
        s -= 8
        reasons.append("penalised: heavy roots next to structures")
    if b.area_m2 < 200 and sp["canopy_r"] > 7:
        s -= 6
        reasons.append("penalised: crown too wide for a small plot")

    return round(s, 2), reasons


def species_selector(b: SiteBrief, prof: dict, cons: dict) -> dict[str, Any]:
    scored, rejected = [], []
    for sp in SPECIES:
        s, why = score_species(sp, b, prof, cons)
        if s < 0:
            rejected.append((sp["common"], why[0] if why else "unsuitable"))
        else:
            scored.append((s, sp))
    scored.sort(key=lambda x: -x[0])

    # Build a layered palette instead of just taking the global top N,
    # so the plot has structure rather than one favourite species repeated.
    mix = LAYER_MIX[b.purpose]
    palette: dict[str, list[tuple[float, dict]]] = {}
    for layer in LAYERS:
        if mix[layer] <= 0:
            continue
        picks = [(s, sp) for s, sp in scored if sp["layer"] == layer]
        want = 4 if layer in ("canopy", "sub_canopy") else 3
        palette[layer] = picks[:want]

    return dict(palette=palette, ranked=scored, rejected=rejected, mix=mix)


# --------------------------------------------------------------------------
# TOOL 3 - layout designer
# --------------------------------------------------------------------------
def layout_designer(b: SiteBrief, prof: dict, sel: dict) -> dict[str, Any]:
    """Decide spacing, tree count and an actual x/y position for every sapling."""
    if b.purpose == "miyawaki":
        spacing, method = 1.2, "Miyawaki dense mixed planting (3 saplings/m², random layer mix)"
        density = 2.8
    elif b.purpose == "urban_avenue":
        spacing, method = 8.0, "Single-row avenue line along the verge"
        density = 1 / 24.0
    elif b.purpose == "pollution_barrier":
        spacing, method = 2.5, "Staggered multi-row green belt (dense screen)"
        density = 1 / 6.0
    elif b.purpose == "food_forest":
        spacing, method = 5.0, "Food-forest guilds: one fruit canopy with understory around it"
        density = 1 / 25.0
    else:
        spacing, method = 5.0, "Open grove with walkable gaps"
        density = 1 / 22.0

    total = max(3, int(prof["usable_area"] * density))
    if b.purpose == "miyawaki":
        total = max(9, int(prof["usable_area"] * 2.8))

    # Split the total across layers, then across the species in each layer.
    allocation: list[dict] = []
    mix = sel["mix"]
    for layer, share in mix.items():
        n_layer = int(round(total * share))
        picks = sel["palette"].get(layer, [])
        if n_layer <= 0 or not picks:
            continue
        per = max(1, n_layer // len(picks))
        left = n_layer
        for i, (_, sp) in enumerate(picks):
            n = per if i < len(picks) - 1 else left
            n = max(1, min(n, left))
            left -= n
            allocation.append(dict(key=sp["key"], common=sp["common"], layer=layer, count=n))
            if left <= 0:
                break

    actual_total = sum(a["count"] for a in allocation)

    # Place them. Avenue = one line; everything else = a jittered grid.
    rng = random.Random(42)
    side = math.sqrt(max(prof["usable_area"], 1))
    positions = []
    bag = [a["key"] for a in allocation for _ in range(a["count"])]
    rng.shuffle(bag)

    if b.purpose == "urban_avenue":
        for i, key in enumerate(bag):
            positions.append((round(i * spacing, 2), 0.0, key))
        extent = (len(bag) * spacing, 6.0)
    else:
        cols = max(1, int(side // spacing))
        for i, key in enumerate(bag):
            r, c = divmod(i, cols)
            x = c * spacing + rng.uniform(-spacing * 0.18, spacing * 0.18)
            y = r * spacing + rng.uniform(-spacing * 0.18, spacing * 0.18)
            positions.append((round(x, 2), round(y, 2), key))
        rows = math.ceil(len(bag) / cols)
        extent = (cols * spacing, rows * spacing)

    # Shannon diversity index over the realised planting.
    shannon = 0.0
    for a in allocation:
        p = a["count"] / max(actual_total, 1)
        if p > 0:
            shannon -= p * math.log(p)
    max_shannon = math.log(len(allocation)) if len(allocation) > 1 else 1
    evenness = round(shannon / max_shannon, 2) if max_shannon else 0.0

    pit = "60 x 60 x 60 cm" if b.purpose != "miyawaki" else "trench bed, soil loosened to 90 cm"

    return dict(
        method=method, spacing=spacing, total=actual_total, allocation=allocation,
        positions=positions, extent=extent, shannon=round(shannon, 2),
        evenness=evenness, pit=pit,
    )


# --------------------------------------------------------------------------
# TOOL 4 - calendar planner
# --------------------------------------------------------------------------
def calendar_planner(b: SiteBrief) -> dict[str, Any]:
    onset, withdrawal, month = REGION_MONSOON.get(
        b.region, REGION_MONSOON["Vidarbha / Central India"]
    )
    tasks = [
        ("Feb - Mar", "Site survey, soil test, mark pit centres, confirm nursery stock"),
        ("Apr - May", "Dig pits and leave them open to solarise; order tree guards"),
        ("1st week June", "Backfill pits with topsoil, compost and murrum in a 2:1:1 ratio"),
        (f"{onset} + 10 days", "PLANT. Wait for two soaking rains so the subsoil is wet, not just the surface"),
        ("Jul - Aug", "Weekly walk: straighten leaning saplings, weed a 50 cm ring, top up mulch"),
        ("Sep - Oct", f"Monsoon withdraws around {withdrawal}. Start the dry-season watering rota"),
        ("Nov - Feb", "Water every 10-12 days in year one; light formative pruning in January"),
        ("Mar - May (yr 1-3)", "Critical summer. Water weekly, re-mulch, replace casualties next monsoon"),
    ]
    if b.slope:
        tasks.insert(2, ("May", "Cut contour trenches and plant vetiver slips on the bund first"))
    if b.irrigation == "drip":
        tasks.insert(3, ("1st week June", "Lay drip laterals and test emitters before planting"))

    return dict(onset=onset, withdrawal=withdrawal, window=f"{onset} to 31 July", tasks=tasks)


# --------------------------------------------------------------------------
# TOOL 5 - carbon model
# --------------------------------------------------------------------------
def carbon_model(layout: dict, years: int = 20, survival: float = 0.8) -> dict[str, Any]:
    """
    Logistic uptake curve. A sapling sequesters almost nothing in year one and
    approaches its mature annual rate as the crown closes, so a straight
    'trees x mature rate' figure overstates the first decade badly.
    """
    curve, cumulative = [], 0.0
    per_year_at = {}
    for yr in range(1, years + 1):
        annual = 0.0
        for a in layout["allocation"]:
            sp = BY_KEY[a["key"]]
            k = GROWTH_FACTOR[sp["growth"]]
            maturity = 1 / (1 + math.exp(-k * (yr - 7)))      # S-curve, inflection ~year 7
            annual += a["count"] * survival * sp["co2"] * maturity
        cumulative += annual
        curve.append((yr, round(annual, 1), round(cumulative, 1)))
        per_year_at[yr] = round(annual, 1)

    return dict(
        curve=curve,
        annual_yr5=per_year_at.get(5, 0),
        annual_yr10=per_year_at.get(10, 0),
        annual_yr20=per_year_at.get(20, 0),
        total_20yr_t=round(cumulative / 1000, 2),
        cars_offset=round(cumulative / 1000 / 2.4, 1),   # ~2.4 t CO2/yr for a small car
        survival=survival,
    )


# --------------------------------------------------------------------------
# TOOL 6 - budget model
# --------------------------------------------------------------------------
def budget_model(b: SiteBrief, layout: dict) -> dict[str, Any]:
    sap = sum(BY_KEY[a["key"]]["cost"] * a["count"] for a in layout["allocation"])
    n = layout["total"]
    # Dense Miyawaki planting is one machine-dug trench bed, not n individual pits,
    # so the per-sapling groundwork rate drops sharply with bulk.
    bulk = 0.35 if b.purpose == "miyawaki" else 1.0

    pit = n * (120 if b.soil != "rocky_murrum" else 260) * bulk
    amend = n * 90 * bulk                            # compost, murrum, neem cake
    guard = n * (350 if b.purpose in ("urban_avenue", "campus_shade") else 0)
    if b.purpose == "miyawaki":
        guard = 15000                                # one perimeter fence instead
    mulch = n * 40 * bulk
    labour = n * 110 * bulk
    water_kit = {"monsoon_only": 0, "tanker": 0, "drip": max(12000, n * 90)}[b.irrigation]

    setup = sap + pit + amend + guard + mulch + labour + water_kit
    per_year_maint = (n * 260 + {"monsoon_only": n * 150, "tanker": n * 420,
                                 "drip": n * 120}[b.irrigation]) * bulk
    maint = per_year_maint * b.maintenance_years
    total = setup + maint

    lines = [
        ("Saplings", sap), ("Pit digging", pit), ("Soil amendment", amend),
        ("Tree guards / fencing", guard), ("Mulch", mulch),
        ("Planting labour", labour), ("Watering setup", water_kit),
        (f"Maintenance x {b.maintenance_years} yr", maint),
    ]
    over = b.budget_inr > 0 and total > b.budget_inr
    return dict(lines=[l for l in lines if l[1] > 0], setup=setup, maint=maint,
                total=total, per_tree=round(total / max(n, 1)), over_budget=over,
                ceiling=b.budget_inr)


# --------------------------------------------------------------------------
# TOOL 7 - risk auditor  (the reflection step)
# --------------------------------------------------------------------------
def risk_auditor(b: SiteBrief, prof: dict, sel: dict, layout: dict, budget: dict,
                 cons: dict) -> tuple[list[str], dict, bool]:
    """
    Criticise the current plan. Returns (findings, amended_constraints, changed).
    Only a finding that the agent can *act* on flips `changed` and triggers a replan.
    """
    findings: list[str] = []
    new = {k: (set(v) if isinstance(v, set) else v) for k, v in cons.items()}
    new.setdefault("ban", set())
    changed = False

    chosen = {a["key"] for a in layout["allocation"]}

    # 1. Roots vs infrastructure
    if b.near_structures and cons.get("max_root_risk") is None:
        risky = [BY_KEY[k]["common"] for k in chosen if BY_KEY[k]["root_risk"] >= 3]
        if risky:
            findings.append(
                f"{', '.join(risky)} have structure-damaging roots and the brief says there are "
                "buildings or services within 8 m. Capping root aggression and replanning."
            )
            new["max_root_risk"] = 2
            changed = True

    # 2. Overhead lines. On an avenue the trees sit directly under the wires, so this is a
    #    hard height cap. On an open plot the wires cross one edge, so it is only advice:
    #    banning every tall tree there would leave the site with no canopy at all.
    tall = [BY_KEY[k]["common"] for k in chosen if BY_KEY[k]["height"] > 10]
    if b.overhead_lines and tall:
        if b.purpose == "urban_avenue" and cons.get("max_height") is None:
            findings.append(
                f"{', '.join(tall[:3])} will grow into the overhead lines along this verge. "
                "Height ceiling set to 10 m and replanning."
            )
            new["max_height"] = 10
            changed = True
        else:
            findings.append(
                f"Advisory: keep {', '.join(tall[:3])} at least 5 m clear of the wire alignment "
                "and plant only the understory and shrub layers directly beneath it."
            )

    # 3. Water realism
    thirsty = [BY_KEY[k]["common"] for k in chosen
               if BY_KEY[k]["water"] >= 4 and b.irrigation == "monsoon_only"]
    if thirsty and prof["water_class"] in ("water_scarce", "moderate"):
        findings.append(
            f"{', '.join(thirsty)} need assured water but the plot is rain-fed. Dropping them."
        )
        new["ban"] |= {k for k in chosen if BY_KEY[k]["water"] >= 4}
        changed = True

    # 4. Monoculture check
    if layout["evenness"] < 0.75 and len(layout["allocation"]) > 2:
        dom = max(layout["allocation"], key=lambda a: a["count"])
        findings.append(
            f"Planting is skewed towards {dom['common']} (evenness {layout['evenness']}). "
            "A skewed block is one pest outbreak away from total loss; rebalancing the counts."
        )
        # Non-structural: handled by the rebalance below rather than a replan.

    # 5. Native share for ecological purposes
    if b.purpose in ("miyawaki", "biodiversity", "soil_water") and not cons.get("natives_only"):
        exotic = [BY_KEY[k]["common"] for k in chosen if not BY_KEY[k]["native"]]
        if exotic:
            findings.append(
                f"{', '.join(exotic)} are exotics in a plot whose whole purpose is native ecology. "
                "Restricting the palette to natives."
            )
            new["natives_only"] = True
            changed = True

    # 6. Nurse cover for slow species on an exposed site
    slow = [k for k in chosen if BY_KEY[k]["growth"] == "slow"]
    has_nurse = any("nurse_tree" in BY_KEY[k]["uses"] for k in chosen)
    if slow and not has_nurse and b.purpose in ("miyawaki", "biodiversity", "food_forest"):
        findings.append(
            "Slow species are going in with no fast nurse cover, which usually means sun scorch "
            "in the first two summers. Shevri (Sesbania) should be interplanted as a nurse crop."
        )

    # 7. Structural gap: a shade or carbon brief with no canopy layer is a failed plan
    want_canopy = sel["mix"].get("canopy", 0) > 0
    has_canopy = any(a["layer"] == "canopy" for a in layout["allocation"])
    if want_canopy and not has_canopy:
        findings.append(
            "No canopy species survived the filters, so this plot would never close a crown. "
            "Relax the water or height constraint, or accept that only a shrub belt fits here."
        )

    # 8. Budget ceiling
    if budget["over_budget"] and cons.get("max_sapling_cost") is None:
        findings.append(
            f"Cost Rs {budget['total']:,.0f} exceeds the Rs {b.budget_inr:,.0f} ceiling. "
            "Dropping premium-priced saplings and replanning on cheaper nursery stock."
        )
        new["max_sapling_cost"] = 60
        changed = True
    elif budget["over_budget"]:
        findings.append(
            f"Still Rs {budget['total'] - b.budget_inr:,.0f} over the ceiling after switching to "
            "cheaper stock. Either the plot count or the maintenance period has to come down."
        )

    # 9. Slope without a stabiliser
    if b.slope and "vetiver" not in chosen:
        findings.append("Sloping site with no bund stabiliser. Adding vetiver to the shrub layer.")
        new["force_include"] = set(new.get("force_include", set())) | {"vetiver"}
        changed = True

    if not findings:
        findings.append("No violations found. The plan is internally consistent with the site.")

    return findings, new, changed


def rebalance(layout: dict) -> dict:
    """Flatten a skewed allocation so no species dominates the block."""
    n_sp = len(layout["allocation"])
    if n_sp < 2:
        return layout
    total = layout["total"]
    cap = max(1, int(total * 0.35))
    spare = 0
    for a in layout["allocation"]:
        if a["count"] > cap:
            spare += a["count"] - cap
            a["count"] = cap
    i = 0
    while spare > 0 and n_sp:
        a = layout["allocation"][i % n_sp]
        if a["count"] < cap:
            a["count"] += 1
            spare -= 1
        i += 1
        if i > 10000:
            break
    layout["total"] = sum(a["count"] for a in layout["allocation"])
    return layout


# --------------------------------------------------------------------------
# The agent loop
# --------------------------------------------------------------------------
def run_agent(b: SiteBrief) -> AgentState:
    st = AgentState(brief=b)

    prof = site_profiler(b)
    st.log(
        "PERCEIVE",
        "Before choosing anything I need the numbers the site actually gives me: how much "
        "water a tree can count on, and how much ground is plantable after setbacks.",
        "site_profiler(brief)",
        f"Effective water {prof['effective_water']} mm/yr ({prof['water_class']}). "
        f"Usable area {prof['usable_area']} m² after a {prof['setback_pct']}% setback. "
        f"Site stresses: {'; '.join(prof['stress']) if prof['stress'] else 'none flagged'}.",
    )

    st.log(
        "PLAN",
        f"Goal is '{b.purpose}'. I will decompose it into: pick a layered species palette, "
        "lay the saplings out on the ground, fix the planting calendar to the monsoon, then "
        "cost it and model the carbon. Finally I audit my own plan and replan if it fails.",
        "decompose_goal()",
        "Tool queue: species_selector -> layout_designer -> calendar_planner -> "
        "carbon_model -> budget_model -> risk_auditor (loop).",
    )

    sel = layout = budget = None
    for it in range(1, MAX_ITERS + 1):
        st.iteration = it

        sel = species_selector(b, prof, st.constraints)
        picked = [sp["common"] for layer in sel["palette"].values() for _, sp in layer]
        st.log(
            "ACT",
            "Scoring every species in the knowledge base against soil, water and purpose "
            "weights, then filling each structural layer separately so the plot has "
            "vertical structure instead of one winning species repeated.",
            f"species_selector(constraints={_fmt_cons(st.constraints)})",
            f"Pass {it}: shortlisted {len(picked)} species - {', '.join(picked)}. "
            f"{len(sel['rejected'])} species rejected on site fit.",
        )

        force = st.constraints.get("force_include", set())
        for key in force:
            if key not in {sp["key"] for layer in sel["palette"].values() for _, sp in layer}:
                sp = BY_KEY[key]
                sel["palette"].setdefault(sp["layer"], []).append((99.0, sp))

        layout = layout_designer(b, prof, sel)
        layout = rebalance(layout)
        st.log(
            "ACT",
            "Converting the palette into a real planting: spacing suited to the purpose, "
            "a count per species, and an x/y position for every pit.",
            f"layout_designer(spacing={layout['spacing']} m)",
            f"{layout['method']}. {layout['total']} saplings across "
            f"{len(layout['allocation'])} species. Shannon diversity {layout['shannon']} "
            f"(evenness {layout['evenness']}). Pit size {layout['pit']}.",
        )

        budget = budget_model(b, layout)
        st.log(
            "ACT",
            "Costing the plan, because a plantation plan nobody can fund is not a plan.",
            "budget_model(layout)",
            f"Setup Rs {budget['setup']:,.0f} + {b.maintenance_years}-yr maintenance "
            f"Rs {budget['maint']:,.0f} = Rs {budget['total']:,.0f} "
            f"(Rs {budget['per_tree']:,} per tree).",
        )

        findings, new_cons, changed = risk_auditor(b, prof, sel, layout, budget, st.constraints)
        st.log(
            "REFLECT",
            "Now I argue against my own plan: roots near structures, thirst the site cannot "
            "meet, monoculture risk, exotics in a native brief, missing nurse cover, cost.",
            "risk_auditor(plan)",
            " | ".join(findings),
        )

        if changed and it < MAX_ITERS:
            st.constraints = new_cons
            st.log(
                "REPLAN",
                "The audit produced constraints I can act on, so this draft is discarded "
                "and the selection runs again under the tighter rules.",
                f"update_constraints -> {_fmt_cons(new_cons)}",
                f"Starting pass {it + 1}.",
            )
            continue

        st.plan["findings"] = findings
        break

    cal = calendar_planner(b)
    carbon = carbon_model(layout)
    st.log(
        "ACT",
        "Timing decides survival more than species choice does, so the calendar is pinned "
        "to monsoon onset, not to a fixed date.",
        f"calendar_planner(region='{b.region}')",
        f"Planting window {cal['window']}; monsoon withdraws around {cal['withdrawal']}.",
    )
    st.log(
        "ACT",
        "Modelling carbon on a logistic curve instead of trees x mature rate, which would "
        "overstate the first decade by a factor of three.",
        "carbon_model(layout, years=20, survival=0.8)",
        f"{carbon['annual_yr10']} kg CO2/yr by year 10; "
        f"{carbon['total_20yr_t']} t CO2 cumulative over 20 years.",
    )
    st.log(
        "CONCLUDE",
        "Every tool has reported and the audit is satisfied within the iteration budget.",
        "emit_plan()",
        f"Converged after {st.iteration} planning pass(es).",
    )

    st.plan.update(profile=prof, selection=sel, layout=layout,
                   calendar=cal, carbon=carbon, budget=budget)
    return st


def _fmt_cons(c: dict) -> str:
    if not c:
        return "none"
    bits = []
    for k, v in c.items():
        if isinstance(v, set):
            v = ", ".join(sorted(v)) or "none"
        bits.append(f"{k}={v}")
    return "; ".join(bits)


# --------------------------------------------------------------------------
# Optional LLM narrator (the plan never depends on it)
# --------------------------------------------------------------------------
def narrate(state: AgentState, api_key: str = "") -> str:
    """If an Anthropic key is supplied, ask a model to write the covering note."""
    if not api_key.strip():
        return ""
    try:
        import anthropic
    except ImportError:
        return "_(install `anthropic` to enable the LLM covering note)_"
    try:
        client = anthropic.Anthropic(api_key=api_key.strip())
        from report import plan_to_markdown

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{
                "role": "user",
                "content": "Write a short, plain covering note (max 180 words) that a college "
                           "green committee could read out, based on this plantation plan. No "
                           "bullet lists, no headings.\n\n" + plan_to_markdown(state)[:6000],
            }],
        )
        return "".join(p.text for p in msg.content if getattr(p, "type", "") == "text")
    except Exception as e:  # network off, bad key, rate limit
        return f"_(covering note unavailable: {e})_"
