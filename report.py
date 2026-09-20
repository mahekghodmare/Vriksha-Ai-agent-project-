"""
report.py
---------
Turns the agent's plan object into the things a human can use:
a markdown brief, a planting-layout drawing, a carbon curve and a CSV indent.
"""

from __future__ import annotations

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from agent_core import AgentState
from species_db import BY_KEY

OUT = "outputs"

LAYER_COLOR = {
    "canopy": "#1f5c3a",
    "sub_canopy": "#4e8b4a",
    "understory": "#8fb25c",
    "shrub": "#c2a23e",
}


# --------------------------------------------------------------------------
def layout_figure(state: AgentState):
    lay = state.plan["layout"]
    w, h = lay["extent"]
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=120)

    for x, y, key in lay["positions"]:
        sp = BY_KEY[key]
        r = max(sp["canopy_r"] * 0.45, 0.35)
        ax.add_patch(Circle((x, y), r, facecolor=LAYER_COLOR[sp["layer"]],
                            edgecolor="white", linewidth=0.6, alpha=0.78))

    ax.set_xlim(-3, max(w, 5) + 3)
    ax.set_ylim(-3, max(h, 5) + 3)
    ax.set_aspect("equal")
    ax.set_xlabel("metres")
    ax.set_ylabel("metres")
    ax.set_title(f"{state.brief.name} — planting layout ({lay['total']} saplings, "
                 f"{lay['spacing']} m spacing)", fontsize=10)
    ax.grid(alpha=0.15, linestyle=":")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                          markerfacecolor=c, markeredgecolor="white",
                          label=l.replace("_", " ").title())
               for l, c in LAYER_COLOR.items()]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.18),
              ncol=4, frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def carbon_figure(state: AgentState):
    c = state.plan["carbon"]
    yrs = [r[0] for r in c["curve"]]
    annual = [r[1] for r in c["curve"]]
    cum = [r[2] / 1000 for r in c["curve"]]

    fig, ax1 = plt.subplots(figsize=(7.2, 4.0), dpi=120)
    ax1.bar(yrs, annual, color="#4e8b4a", alpha=0.75, label="Annual CO₂ (kg)")
    ax1.set_xlabel("Year after planting")
    ax1.set_ylabel("kg CO₂ absorbed per year")
    ax2 = ax1.twinx()
    ax2.plot(yrs, cum, color="#1f5c3a", linewidth=2.2, marker="o",
             markersize=3, label="Cumulative (tonnes)")
    ax2.set_ylabel("Cumulative tonnes CO₂")
    ax1.set_title("Carbon uptake follows an S-curve, not a straight line", fontsize=10)
    ax1.grid(alpha=0.15, axis="y", linestyle=":")
    for spine in ("top",):
        ax1.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
def plan_to_markdown(state: AgentState) -> str:
    b, p = state.brief, state.plan
    lay, cal, car, bud, prof = p["layout"], p["calendar"], p["carbon"], p["budget"], p["profile"]

    md = [f"# Plantation plan — {b.name}", ""]
    md += [
        f"**Purpose:** {b.purpose.replace('_', ' ')}  |  **Region:** {b.region}  ",
        f"**Area:** {b.area_m2:,.0f} m² ({prof['usable_area']:,.0f} m² plantable)  |  "
        f"**Soil:** {b.soil.replace('_', ' ')}  ",
        f"**Rainfall:** {b.rainfall_mm} mm + irrigation = {prof['effective_water']} mm effective "
        f"({prof['water_class'].replace('_', ' ')})",
        "",
        f"The agent converged after **{state.iteration} planning pass(es)** and "
        f"**{len(state.trace)} reasoning steps**.",
        "",
        "## 1. What to plant", "",
        "| Species | Botanical | Layer | Count | Why it is here |",
        "|---|---|---|---|---|",
    ]
    for a in sorted(lay["allocation"], key=lambda x: (x["layer"], -x["count"])):
        sp = BY_KEY[a["key"]]
        md.append(f"| {sp['common']} | *{sp['botanical']}* | {a['layer'].replace('_', ' ')} "
                  f"| {a['count']} | {sp['note']} |")

    md += [
        "", f"**Total saplings:** {lay['total']}  |  **Species:** {len(lay['allocation'])}  |  "
        f"**Shannon diversity:** {lay['shannon']} (evenness {lay['evenness']})",
        "",
        "## 2. How to lay it out", "",
        f"- Method: {lay['method']}",
        f"- Spacing: {lay['spacing']} m",
        f"- Pit specification: {lay['pit']}",
        f"- Setback applied: {prof['setback_pct']}% of the plot left unplanted for access and services",
    ]
    if prof["stress"]:
        md += ["", "**Site stresses the plan had to work around:**"]
        md += [f"- {s}" for s in prof["stress"]]

    md += ["", "## 3. When to do it", "",
           f"Planting window: **{cal['window']}** (monsoon onset {cal['onset']}, "
           f"withdrawal {cal['withdrawal']}).", "",
           "| Period | Task |", "|---|---|"]
    md += [f"| {w} | {t} |" for w, t in cal["tasks"]]

    md += ["", "## 4. What it captures", "",
           f"- Year 5: ~{car['annual_yr5']:,.0f} kg CO₂/yr",
           f"- Year 10: ~{car['annual_yr10']:,.0f} kg CO₂/yr",
           f"- Year 20: ~{car['annual_yr20']:,.0f} kg CO₂/yr",
           f"- **Cumulative over 20 years: {car['total_20yr_t']} tonnes CO₂**, roughly the "
           f"lifetime output of {car['cars_offset']} small cars running for a year each.",
           f"- Modelled at {int(car['survival'] * 100)}% survival on a logistic growth curve.",
           "", "## 5. What it costs", "", "| Item | Rs |", "|---|---|"]
    md += [f"| {n} | {v:,.0f} |" for n, v in bud["lines"]]
    md += [f"| **Total** | **{bud['total']:,.0f}** |", "",
           f"Roughly **Rs {bud['per_tree']:,} per established tree** including "
           f"{b.maintenance_years} years of maintenance."]

    md += ["", "## 6. What the agent flagged about its own plan", ""]
    md += [f"- {f}" for f in p.get("findings", [])]

    md += ["", "## 7. Reasoning trace", "",
           "| # | Phase | Action | Observation |", "|---|---|---|---|"]
    for s in state.trace:
        md.append(f"| {s.n} | {s.phase} | `{s.action}` | {s.observation} |")

    md += ["", "---", "",
           "*Generated by Vriksha, an agentic planner. Carbon and cost figures are "
           "planning-grade estimates; confirm nursery rates and species availability locally.*"]
    return "\n".join(md)


# --------------------------------------------------------------------------
def export_files(state: AgentState) -> list[str]:
    os.makedirs(OUT, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "_" for ch in state.brief.name).strip("_") or "site"

    md_path = os.path.join(OUT, f"{slug}_plan.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(plan_to_markdown(state))

    csv_path = os.path.join(OUT, f"{slug}_indent.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Species", "Botanical", "Layer", "Count",
                    "Rate (Rs)", "Amount (Rs)", "Mature height (m)", "CO2 kg/yr"])
        for a in state.plan["layout"]["allocation"]:
            sp = BY_KEY[a["key"]]
            w.writerow([sp["common"], sp["botanical"], a["layer"], a["count"],
                        sp["cost"], sp["cost"] * a["count"], sp["height"], sp["co2"]])

    trace_path = os.path.join(OUT, f"{slug}_trace.csv")
    with open(trace_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Step", "Phase", "Thought", "Action", "Observation"])
        for s in state.trace:
            w.writerow([s.n, s.phase, s.thought, s.action, s.observation])

    return [md_path, csv_path, trace_path]
