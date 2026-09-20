from agent_core import SiteBrief, run_agent
from report import plan_to_markdown, layout_figure, carbon_figure, export_files
from species_db import PURPOSES, SOILS

cases = [
    SiteBrief("Campus north lawn", "Vidarbha / Central India", 800, "black_cotton", 1100, "campus_shade", "monsoon_only", True, True, False, 0, 3),
    SiteBrief("Miyawaki patch", "Konkan / West Coast", 300, "red_laterite", 2400, "miyawaki", "drip", False, False, False, 150000, 3),
    SiteBrief("Canal bund", "Marathwada / Dry Deccan", 2000, "rocky_murrum", 620, "soil_water", "monsoon_only", False, False, True, 0, 2),
]
for b in cases:
    st = run_agent(b)
    lay = st.plan["layout"]
    print(f"\n=== {b.name} | passes={st.iteration} steps={len(st.trace)}")
    print("  trees", lay["total"], "species", len(lay["allocation"]), "evenness", lay["evenness"])
    print("  ", [(a["common"], a["count"]) for a in lay["allocation"]])
    print("  CO2 20yr t:", st.plan["carbon"]["total_20yr_t"], "cost:", st.plan["budget"]["total"])
    print("  findings:", st.plan["findings"][:2])
    layout_figure(st); carbon_figure(st)
    print("  md len", len(plan_to_markdown(st)), "files", export_files(st))

# stress: every purpose x every soil must not crash
import itertools
n=0
for p, s in itertools.product(PURPOSES, SOILS):
    for rain in (400, 900, 2000):
        st = run_agent(SiteBrief("x", "Vidarbha / Central India", 500, s, rain, p, "monsoon_only", True, True, True, 10000, 3))
        assert st.plan["layout"]["total"] >= 0
        n+=1
print("\nstress ok:", n, "combos")
