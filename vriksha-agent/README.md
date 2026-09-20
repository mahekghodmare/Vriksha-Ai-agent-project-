# Vriksha — an AI agent for tree plantation planning

**CA3 mini project · Agentic AI and Automation (flexi credit)**
GUI: Gradio · Language: Python · Runs fully offline

---

## 1. The problem

Plantation drives fail quietly. Saplings go in on a convenient Sunday instead of after
the second soaking rain, the species are whatever the nursery had in stock, a Peepal
goes in two metres from a compound wall, and three summers later most of the plot is
dead sticks. The decisions that matter — species, spacing, timing, aftercare money —
are made by whoever is standing there, without a model of the site.

**Vriksha** is an agent that makes those decisions the way a forester would, shows its
reasoning, and then argues against its own first answer.

## 2. Why this is an *agent* and not a form with formulas

The system runs a bounded perceive–plan–act–reflect loop:

```
PERCEIVE   site_profiler          derive effective water, plantable area, site stresses
PLAN       decompose_goal         choose the tool queue from the stated purpose
ACT        species_selector   ->  layout_designer -> calendar_planner
           carbon_model       ->  budget_model
REFLECT    risk_auditor          criticise the draft, emit hard constraints
REPLAN     <-- loops back to ACT with the tighter constraints (max 3 passes)
CONCLUDE   emit_plan             final plan + full trace
```

The reflection step is the point. `risk_auditor` inspects the agent's own output and can
emit constraints that invalidate it:

| What it detects | Constraint it emits | Effect on the replan |
|---|---|---|
| Structure-damaging roots near buildings | `max_root_risk = 2` | Banyan and Peepal are dropped |
| Species thirstier than a rain-fed plot | `ban = {…}` | Kadamb, Ashoka dropped |
| Exotics in a native-ecology brief | `natives_only = True` | Gulmohar, Custard Apple dropped |
| Overhead lines on an avenue | `max_height = 10` | Only low crowns along the verge |
| Cost above the stated ceiling | `max_sapling_cost = 60` | Premium nursery stock dropped |
| Slope with no bund stabiliser | `force_include = {vetiver}` | Vetiver added to the shrub layer |
| Skew towards one species | — | Counts rebalanced, cap 35% per species |

Everything else is advisory and appears in the findings without a replan, so the loop
always terminates. The trace records each pass, so you can watch it change its mind.

Try it: purpose **Biodiversity**, tick **buildings within 8 m** → pass 1 picks exotics,
the audit rejects them, pass 2 comes back all-native.

## 3. Tools the agent calls

| Tool | What it decides |
|---|---|
| `site_profiler` | Rainfall + irrigation → effective water class; usable area after setbacks; soil stresses |
| `species_selector` | Scores all 24 species on soil fit, water fit and purpose weights; fills each forest layer separately |
| `layout_designer` | Spacing by purpose (1.2 m Miyawaki → 8 m avenue), count per species, x/y for every pit, Shannon diversity |
| `calendar_planner` | Pins the planting window to regional monsoon onset, not a fixed date; 8-stage task calendar |
| `carbon_model` | Logistic (S-curve) uptake over 20 years at 80% survival — not `trees × mature rate`, which overstates the first decade roughly threefold |
| `budget_model` | Saplings, pits, amendment, guards, mulch, labour, watering, multi-year maintenance |
| `risk_auditor` | The reflection step described above |

## 4. What makes it different from the usual "plant recommender"

- **It replans.** Most projects score a list once. This one rejects its own draft.
- **It designs in layers.** Canopy / sub-canopy / understory / shrub shares change by
  purpose, so a Miyawaki block is structured and an avenue is a single line.
- **It shows what it rejected and why** — a planner that cannot say *why not* has not
  really chosen.
- **It draws the actual plot** with real crown radii at maturity, so overlap is visible.
- **It costs the plan**, including the aftercare years where drives usually fail.
- **It is deterministic.** Same brief, same plan, gradeable trace. The optional LLM only
  writes a covering note at the end and never touches the plan.

## 5. Running it

```bash
pip install -r requirements.txt
python app.py          # opens http://127.0.0.1:7860
```

Optional: paste an Anthropic API key in the GUI to get an LLM-written covering note.
Everything else works with no key and no internet.

Check the engine without the GUI:

```bash
python test_agent.py   # 3 scenarios + a 144-combination stress run
```

## 6. Files

| File | Role |
|---|---|
| `app.py` | Gradio GUI — inputs, six result tabs, species browser, downloads |
| `agent_core.py` | The agent loop, the seven tools, the constraint system |
| `species_db.py` | Knowledge base: 24 Indian species × 18 traits, purpose weights, layer mixes, monsoon calendar |
| `report.py` | Markdown brief, layout drawing, carbon chart, CSV exports |
| `test_agent.py` | Scenario and stress tests |

## 7. Outputs the GUI produces

Headline metrics · full markdown plan · step-by-step reasoning trace · scale planting
layout · 20-year carbon chart · species and cost tables · rejected-species list ·
downloadable plan (`.md`), nursery indent (`.csv`) and trace (`.csv`).

## 8. Honest limits

Carbon and cost figures are planning-grade estimates from published forestry ranges, not
site-measured values — confirm nursery rates locally. The species base covers 24 trees
suited to peninsular and central India; a different agro-climatic zone needs its own
table. There is no satellite or soil-sensor input; the site brief is trusted as given.

## 9. Possible extensions

Soil-test PDF upload parsed into the brief · live rainfall from IMD by district ·
a shapefile of the actual plot instead of a rectangle · a survival-tracking mode where
year-2 mortality feeds back and the agent replans the replacement planting.
