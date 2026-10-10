"""
generate_geant4_plan_200.py
Generates the balanced execution plan geant4_plan_200.json for 1,711 jobs across 200 runners on 10 GitHub accounts.
Paper 10.1 (PNE 2022) Benchmark:
- 8 Glass Samples (S1 - S8) + S0 (Blank)
- 23 Benchmark Energies (15 keV - 15 MeV)
- 10 Thickness Levels (0.005 cm - 3.0 cm)
Total Jobs: 1,711 jobs
"""
import json
from pathlib import Path

ACCOUNTS = [
    'haoidlemystic1',
    'vuicho',
    'haoidle4zk',
    '67hao',
    'idlemystich',
    'CarwynDuc',
    'laolaolaoma09',
    'Bethwl',
    'coredaohaojack'
]

NUM_RUNNERS_PER_ACC = 20
TOTAL_RUNNERS = len(ACCOUNTS) * NUM_RUNNERS_PER_ACC # 200

ENERGIES_KEV = [
    15, 20, 30, 40, 50, 60, 80, 100, 200, 300, 400, 500,
    600, 800, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 15000
]

SAMPLES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

def get_thicknesses_for_energy(e_kev: int) -> list[float]:
    # 15-40 keV has 0.005 cm thin sample
    if e_kev in [15, 20, 30, 40]:
        return [0.005, 0.10, 0.30, 0.50, 0.80, 1.00, 1.50, 2.00, 2.50, 3.00]
    else:
        return [0.10, 0.30, 0.50, 0.80, 1.00, 1.50, 2.00, 2.50, 3.00]

def build_all_jobs() -> list[dict]:
    jobs = []

    # 1. Blank jobs (S0, vacuum material)
    for e in ENERGIES_KEV:
        jobs.append({
            "job_name": f"blank_{e}kev",
            "sample": "S0",
            "energy_kev": e,
            "energy_mev": round(e / 1000.0, 6),
            "thickness_cm": 0.5,
            "weight": 1.0 # fast
        })

    # 2. Sample jobs (S1 to S8)
    for s in SAMPLES:
        s_idx = int(s[1:])
        for e in ENERGIES_KEV:
            th_list = get_thicknesses_for_energy(e)
            for th in th_list:
                th_str = f"{th:.4f}".rstrip('0').rstrip('.')
                job_name = f"{s.lower()}_{e}kev_th{th_str}cm"
                # Estimate computational weight
                weight = 1.0 + (s_idx * 0.2) + (th * 0.5) + (e / 5000.0)
                jobs.append({
                    "job_name": job_name,
                    "sample": s,
                    "energy_kev": e,
                    "energy_mev": round(e / 1000.0, 6),
                    "thickness_cm": th,
                    "weight": round(weight, 2)
                })

    return jobs

def partition_jobs(jobs: list[dict]) -> dict:
    # Sort jobs by weight descending (Longest Processing Time First heuristic)
    jobs_sorted = sorted(jobs, key=lambda x: x["weight"], reverse=True)

    # Initialize 200 runner bins
    runner_list = []
    for acc in ACCOUNTS:
        for r_id in range(1, NUM_RUNNERS_PER_ACC + 1):
            runner_list.append({
                "account": acc,
                "runner_id": r_id,
                "jobs": [],
                "total_weight": 0.0
            })

    # Greedy allocation to least loaded runner
    for job in jobs_sorted:
        # Pick runner with minimum total_weight
        runner_list.sort(key=lambda r: (r["total_weight"], len(r["jobs"])))
        best = runner_list[0]
        # Clean job dict (remove weight)
        clean_job = {
            "job_name": job["job_name"],
            "sample": job["sample"],
            "energy_kev": job["energy_kev"],
            "energy_mev": job["energy_mev"],
            "thickness_cm": job["thickness_cm"]
        }
        best["jobs"].append(clean_job)
        best["total_weight"] += job["weight"]

    # Assemble into nested dictionary: plan[account][runner_id] = [jobs]
    plan = {acc: {} for acc in ACCOUNTS}
    for r in runner_list:
        acc = r["account"]
        r_id_str = str(r["runner_id"])
        plan[acc][r_id_str] = r["jobs"]

    return plan

def main():
    jobs = build_all_jobs()
    print(f"Total jobs built: {len(jobs)} (Expected: 1711)")
    assert len(jobs) == 1711, f"Expected 1711 jobs, got {len(jobs)}"

    plan = partition_jobs(jobs)

    out_file = Path(r"C:\2026.9.28_Paper10\Geant4_mac\geant4_plan_200.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    print(f"Successfully generated execution plan: {out_file}")
    print(f"Accounts: {len(plan)} | Runners: {TOTAL_RUNNERS}")

    # Statistics
    counts = []
    for acc in plan:
        for r_id, r_jobs in plan[acc].items():
            counts.append(len(r_jobs))
    print(f"Jobs per runner: Min={min(counts)}, Max={max(counts)}, Avg={sum(counts)/len(counts):.2f}")

if __name__ == "__main__":
    main()
