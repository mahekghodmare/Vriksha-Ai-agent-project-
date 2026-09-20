"""
app.py
------
Vriksha — Gradio front end for the tree plantation planning agent.

Run:
    pip install -r requirements.txt
    python app.py
Then open the local URL Gradio prints (http://127.0.0.1:7860).
"""

from __future__ import annotations

import random

import gradio as gr
import folium
import os
from dotenv import load_dotenv
load_dotenv()

from agent_core import SiteBrief, narrate, run_agent
from report import carbon_figure, export_files, layout_figure, plan_to_markdown
from species_db import BY_KEY, PURPOSES, REGION_MONSOON, SOILS, SPECIES


PURPOSE_CHOICES = [(v, k) for k, v in PURPOSES.items()]
SOIL_CHOICES = [(s.replace("_", " ").title(), s) for s in SOILS]
IRRIGATION_CHOICES = [
    ("Rain-fed only", "monsoon_only"),
    ("Tanker / manual watering", "tanker"),
    ("Drip irrigation", "drip"),
]

CSS = """
.gradio-container {max-width: 1180px !important;}
#hero {
  background: linear-gradient(135deg, #12351f 0%, #2f6b3d 55%, #7a8b34 100%);
  color: #f2f6ec; padding: 26px 30px; border-radius: 14px; margin-bottom: 6px;
}
#hero h1 {margin: 0 0 6px 0; font-size: 30px; letter-spacing: -0.4px;}
#hero p {margin: 0; opacity: .88; font-size: 15px; line-height: 1.5;}
.card {border: 1px solid #dfe4d8; border-radius: 12px; padding: 14px 16px; background: #fbfcf8;}
.trace-step {border-left: 3px solid #4e8b4a; padding: 8px 0 8px 14px; margin-bottom: 14px;}
.trace-step .ph {font-weight: 700; color: #1f5c3a; letter-spacing: .5px;}
.trace-step .th {color: #4a5548; font-style: italic;}
.trace-step .ac {font-family: ui-monospace, Menlo, monospace; font-size: 12.5px; color: #6b4e1f;}
footer {visibility: hidden;}
"""
def update_map(latitude, longitude):

    m = folium.Map(
        location=[latitude, longitude],
        zoom_start=13
    )

    folium.Marker(
        [latitude, longitude],
        tooltip="Plantation Site",
        popup=f"Lat: {latitude}, Lon: {longitude}"
    ).add_to(m)

    return m._repr_html_()
# --------------------------------------------------------------------------
def trace_to_html(state) -> str:
    rows = []
    for s in state.trace:
        rows.append(
            f"<div class='trace-step'>"
            f"<div class='ph'>{s.n}. {s.phase}</div>"
            f"<div class='th'>{s.thought}</div>"
            f"<div class='ac'>&gt; {s.action}</div>"
            f"<div>{s.observation}</div></div>"
        )
    header = (
        f"<p><b>{len(state.trace)} steps · {state.iteration} planning pass(es).</b> "
        "Every ACT block below is a tool call; every REPLAN means the agent rejected "
        "its own draft and started the selection again under tighter constraints.</p>"
    )
    return header + "".join(rows)


def headline_html(state) -> str:
    p = state.plan
    lay, car, bud = p["layout"], p["carbon"], p["budget"]
    cells = [
        ("Saplings", f"{lay['total']}"),
        ("Species", f"{len(lay['allocation'])}"),
        ("CO₂ / 20 yr", f"{car['total_20yr_t']} t"),
        ("Total cost", f"Rs {bud['total']:,.0f}"),
        ("Planting window", p["calendar"]["window"].split(" to ")[0]),
    ]
    inner = "".join(
        f"<div style='flex:1;min-width:140px'><div style='font-size:12px;opacity:.7'>{k}</div>"
        f"<div style='font-size:22px;font-weight:700;color:#1f5c3a'>{v}</div></div>"
        for k, v in cells
    )
    return f"<div class='card' style='display:flex;gap:18px;flex-wrap:wrap'>{inner}</div>"


def allocation_rows(state):
    out = []
    for a in sorted(state.plan["layout"]["allocation"], key=lambda x: (x["layer"], -x["count"])):
        sp = BY_KEY[a["key"]]
        out.append([sp["common"], sp["botanical"], a["layer"].replace("_", " "),
                    a["count"], f"{sp['height']} m", sp["co2"],
                    f"{sp['cost'] * a['count']:,}"])
    return out


def budget_rows(state):
    b = state.plan["budget"]
    rows = [[n, f"{v:,.0f}"] for n, v in b["lines"]]
    rows.append(["TOTAL", f"{b['total']:,.0f}"])
    rows.append(["Per established tree", f"{b['per_tree']:,.0f}"])
    return rows


def rejected_rows(state):
    return [[n, w] for n, w in state.plan["selection"]["rejected"]]

def create_map_for_region(region):

    coords = {
        "Vidarbha / Central India": (21.1458, 79.0882),
        "East India / Bengal": (22.9868, 87.8550),
        "Konkan / West Coast": (18.5204, 73.8567),
        "Marathwada / Dry Deccan": (19.8762, 75.3433)
    }

    lat, lon = coords.get(region, (20.5937, 78.9629))

    m = folium.Map(location=[lat, lon], zoom_start=8)

    folium.Marker(
        [lat, lon],
        tooltip=region,
        popup=region
    ).add_to(m)

    return m._repr_html_()

def create_map_for_region(region):

    coords = {
        "Vidarbha / Central India": (21.1458, 79.0882),
        "East India / Bengal": (22.9868, 87.8550),
        "Konkan / West Coast": (18.5204, 73.8567),
        "Marathwada / Dry Deccan": (19.8762, 75.3433),
    }

    lat, lon = coords.get(region, (20.5937, 78.9629))

    m = folium.Map(location=[lat, lon], zoom_start=8)

    folium.Marker(
        [lat, lon],
        tooltip=region,
        popup=region
    ).add_to(m)

    return m._repr_html_()
# --------------------------------------------------------------------------
def plan_site(name, region, area, soil, rainfall, purpose, irrigation,
              near_structures, overhead, slope, budget, maint_years, api_key):
    brief = SiteBrief(
        name=name or "Unnamed site", region=region, area_m2=float(area), soil=soil,
        rainfall_mm=int(rainfall), purpose=purpose, irrigation=irrigation,
        near_structures=bool(near_structures), overhead_lines=bool(overhead),
        slope=bool(slope), budget_inr=float(budget or 0),
        maintenance_years=int(maint_years),
    )
    state = run_agent(brief)
    # Use textbox key if provided, otherwise use .env
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    note = narrate(state, api_key)
    md = plan_to_markdown(state)
    if note:
        md = md.split("## 1.")[0] + "> " + note.strip().replace("\n", "\n> ") + "\n\n## 1." + md.split("## 1.", 1)[1]

    files = export_files(state)
    findings = "\n".join(f"- {f}" for f in state.plan.get("findings", []))
    gis_map = create_map_for_region(region)
    return (
        headline_html(state),
        md,
        trace_to_html(state),
        layout_figure(state),
        carbon_figure(state),
        allocation_rows(state),
        budget_rows(state),
        rejected_rows(state),
        f"### What the agent flagged about its own plan\n{findings}",
        files, gis_map
    ) 


def surprise():
    rng = random.Random()
    region = rng.choice(list(REGION_MONSOON))
    return (
        rng.choice(["Ward 14 road verge", "Hostel back lawn", "Old quarry edge",
                    "Canal bund stretch", "Factory boundary strip", "Temple grove plot"]),
        region,
        rng.choice([180, 400, 750, 1200, 2500]),
        rng.choice(SOILS),
        rng.choice([450, 700, 950, 1250, 1900]),
        rng.choice(list(PURPOSES)),
        rng.choice(["monsoon_only", "tanker", "drip"]),
        rng.random() < 0.5, rng.random() < 0.3, rng.random() < 0.35,
        rng.choice([0, 50000, 120000]), rng.choice([2, 3, 5]),
    )


def species_table(layer_filter, soil_filter, max_water):
    rows = []
    for sp in SPECIES:
        if layer_filter != "all" and sp["layer"] != layer_filter:
            continue
        if soil_filter != "all" and soil_filter not in sp["soils"]:
            continue
        if sp["water"] > max_water:
            continue
        rows.append([sp["common"], sp["botanical"], sp["local"],
                     sp["layer"].replace("_", " "), f"{sp['height']} m",
                     sp["growth"], "★" * sp["water"], sp["co2"],
                     "★" * sp["pollinator"], sp["root_risk"], sp["cost"], sp["note"]])
    return rows


# --------------------------------------------------------------------------
theme = gr.themes.Soft(primary_hue="green", secondary_hue="lime", neutral_hue="stone")
def create_map():
    m = folium.Map(
        location=[20.5937, 78.9629],   # India
        zoom_start=5
    )

    folium.Marker(
        [20.5937, 78.9629],
        tooltip="India"
    ).add_to(m)

    return m._repr_html_()


def update_map(latitude, longitude):
    m = folium.Map(
        location=[latitude, longitude],
        zoom_start=13
    )

    folium.Marker(
        [latitude, longitude],
        tooltip="Plantation Site",
        popup=f"Lat: {latitude}, Lon: {longitude}"
    ).add_to(m)

    return m._repr_html_()

with gr.Blocks(title="Vriksha") as demo:

    

    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group():
                name = gr.Textbox(label="Site name", value="College campus — north lawn")
                with gr.Row():
                    region = gr.Dropdown(list(REGION_MONSOON), value="Vidarbha / Central India", label="Region")
                    purpose = gr.Dropdown(PURPOSE_CHOICES, value="campus_shade", label="What is this plantation for?")
                with gr.Row():
                    area = gr.Number(value=800, label="Plot area (m²)")
                    soil = gr.Dropdown(SOIL_CHOICES, value="black_cotton", label="Soil")
                rainfall = gr.Slider(300, 3000, value=1100, step=25,
                                     label="Average annual rainfall (mm)")
                irrigation = gr.Radio(IRRIGATION_CHOICES, value="monsoon_only",
                                      label="Water available after planting")
                gr.Markdown("**Site conditions the agent must respect**")
                with gr.Row():
                    near_structures = gr.Checkbox(label="Buildings, drains or paving within 8 m")
                    overhead = gr.Checkbox(label="Overhead power lines")
                    slope = gr.Checkbox(label="Sloping or eroding ground")
                with gr.Row():
                    budget = gr.Number(value=0, label="Budget ceiling (Rs, 0 = none)")
                    maint_years = gr.Slider(1, 5, value=3, step=1, label="Maintenance years")
                api_key = gr.Textbox(label="Anthropic API key (optional — adds a written "
                                           "covering note; the plan works without it)",
                                     type="password", placeholder="sk-ant-...")
                with gr.Row():
                    run_btn = gr.Button("Plan this site", variant="primary", scale=3)
                    rand_btn = gr.Button("Random site", scale=1)

        with gr.Column(scale=3):
            headline = gr.HTML()
            findings_md = gr.Markdown()
            with gr.Tabs():
                with gr.Tab("Plan"):
                    plan_md = gr.Markdown()
                with gr.Tab("Reasoning trace"):
                    trace_html = gr.HTML()
                with gr.Tab("Layout"):
                    layout_plot = gr.Plot()
                    gr.Markdown("Circle size is the mature crown radius, colour is the forest "
                                "layer. Overlapping circles at year 20 are intentional in a "
                                "Miyawaki block and a mistake in an avenue.")
                with gr.Tab("Carbon"):
                    carbon_plot = gr.Plot()
                with gr.Tab("GIS Map"):
                    gr.Markdown("## Plantation GIS Map")
                    map_view = gr.HTML()
                with gr.Tab("Species & cost"):
                    alloc_df = gr.Dataframe(
                        headers=["Species", "Botanical", "Layer", "Count",
                                 "Mature ht", "CO₂ kg/yr", "Sapling cost Rs"],
                        interactive=False, wrap=True)
                    budget_df = gr.Dataframe(headers=["Item", "Rs"], interactive=False)
                
                with gr.Tab("Rejected"):
                    gr.Markdown("Species the agent considered and ruled out, with its reason. "
                                "A planner who cannot say why *not* has not really chosen.")
                    rej_df = gr.Dataframe(headers=["Species", "Reason rejected"],
                                          interactive=False, wrap=True)
                with gr.Tab("Download"):
                    files_out = gr.Files(label="Plan (markdown), nursery indent (CSV), trace (CSV)")

    with gr.Accordion("Species knowledge base — browse all 24 entries", open=False):
        with gr.Row():
            f_layer = gr.Dropdown(["all", "canopy", "sub_canopy", "understory", "shrub"],
                                  value="all", label="Layer")
            f_soil = gr.Dropdown(["all"] + SOILS, value="all", label="Grows in soil")
            f_water = gr.Slider(1, 5, value=5, step=1, label="Max water need")
        sp_df = gr.Dataframe(
            headers=["Common", "Botanical", "Local", "Layer", "Height", "Growth",
                     "Water", "CO₂ kg/yr", "Pollinator", "Root risk", "Rs", "Note"],
            value=species_table("all", "all", 5), interactive=False, wrap=True)
        for c in (f_layer, f_soil, f_water):
            c.change(species_table, [f_layer, f_soil, f_water], sp_df)

    with gr.Accordion("How this agent works (for the viva)", open=False):
        gr.Markdown(
            """
**Loop:** `PERCEIVE → PLAN → ACT (5 tools) → REFLECT → REPLAN → CONCLUDE`, bounded at
three passes so it always terminates.

**Tools the agent calls:** `site_profiler`, `species_selector`, `layout_designer`,
`calendar_planner`, `carbon_model`, `budget_model`, `risk_auditor`.

**What makes it agentic and not a form:** the `risk_auditor` criticises the agent's own
draft and emits *constraints* — cap root aggression, ban thirsty species, natives only,
force a slope stabiliser. Those constraints feed back into `species_selector` and the
whole plan is rebuilt. Tick *buildings within 8 m* with a biodiversity purpose and you can
watch it drop Banyan and Peepal in pass 2 and explain why.

**Why it is deterministic:** the reasoning is rule- and score-based, so the same brief
always produces the same plan and the trace can be graded. The optional LLM only writes
a covering note at the end; it never touches the plan.
            """
        )

    outputs = outputs = [
    headline,
    plan_md,
    trace_html,
    layout_plot,
    carbon_plot,
    alloc_df,
    budget_df,
    rej_df,
    findings_md,
    files_out,
    map_view
]

    inputs = [name, region, area, soil, rainfall, purpose, irrigation,
              near_structures, overhead, slope, budget, maint_years, api_key]

    

    # AI planner
    run_btn.click(plan_site, inputs, outputs)
    rand_btn.click(surprise, None, inputs[:-1])

    gr.Examples(
        examples=[
            ["MIDC road verge, Butibori", "Vidarbha / Central India", 600, "black_cotton",
             950, "pollution_barrier", "tanker", True, True, False, 0, 3],
            ["Miyawaki patch, campus rear", "Vidarbha / Central India", 300, "black_cotton",
             1100, "miyawaki", "drip", False, False, False, 150000, 3],
            ["Eroding canal bund", "Marathwada / Dry Deccan", 2000, "rocky_murrum",
             620, "soil_water", "monsoon_only", False, False, True, 0, 2],
            ["School food forest", "Konkan / West Coast", 900, "red_laterite",
             2400, "food_forest", "tanker", True, False, False, 80000, 4],
        ],
        inputs=inputs[:-1],
        label="Try a preset site",
    )



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7861))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"

    demo.launch(
        server_name=host,
        server_port=port
    )
