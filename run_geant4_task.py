"""
run_geant4_task.py - Parallel worker for Geant4 Simulation on GitHub Actions Cluster
Paper 10.1 (PNE 2022) Benchmark: 1,711 jobs across 200 runners on 10 accounts.
"""
import argparse
import os
import sys
import time
import json
import subprocess
from pathlib import Path
import pandas as pd

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import gdrive_helper

def parse_args():
    parser = argparse.ArgumentParser(description="Geant4 Parallel Worker for Paper 10.1")
    parser.add_argument("--runner-id", type=int, required=True, help="ID cua runner (1..20)")
    parser.add_argument("--num-runners", type=int, default=20, help="Tong so runner moi account")
    parser.add_argument("--primaries", type=int, default=10000000, help="So hat moi job (mac dinh 10^7, hoac 10^8)")
    parser.add_argument("--gdrive-folder", type=str, default="1Q6T25GCTu3UO2xzlJrNUPKCzSdjoGFIx")
    parser.add_argument("--plan-file", type=str, default="geant4_plan_200.json")
    parser.add_argument("--github-user", type=str, default=None)
    parser.add_argument("--sim-bin", type=str, default=None)
    parser.add_argument("--timeout-hours", type=float, default=5.4)
    return parser.parse_args()

def find_sim_binary(custom_bin: str = None) -> str:
    if custom_bin and os.path.exists(custom_bin):
        return custom_bin
    candidates = [
        "./build/Sim",
        "./build/Release/Sim.exe",
        "./Sim",
        "/tmp/geant4_build/Sim"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "Sim"

def parse_process_results_last_row(csv_path: Path):
    """Doc dong cuoi cung cua process_results.csv de lay CrossFlux."""
    if not csv_path.exists():
        return 0.0, 0.0
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return 0.0, 0.0
        last = df.iloc[-1]
        tot = float(last.get("CrossFlux_total", 0.0))
        uncoll = float(last.get("CrossFlux_uncollided", 0.0))
        return uncoll, tot
    except Exception as e:
        print(f"    [PARSE ERROR] {e}")
        return 0.0, 0.0

def main():
    args = parse_args()
    print("=" * 80)
    print(f"🚀 STARTING GEANT4 PARALLEL RUNNER #{args.runner_id} / {args.num_runners}")
    print(f"Primaries per job: {args.primaries:,}")
    print(f"Target Drive Folder: {args.gdrive_folder}")
    print("=" * 80)

    sim_bin = find_sim_binary(args.sim_bin)
    print(f"Using Geant4 executable: {sim_bin}")

    # Connect Google Drive
    drive_service = None
    flux_folder_id = None
    account_folder_id = None
    acc_name = args.github_user or os.environ.get("GITHUB_REPOSITORY_OWNER") or "runner"

    try:
        os.environ["GDRIVE_FOLDER_ID"] = args.gdrive_folder
        drive_service = gdrive_helper.get_drive_service()
        folder_ids = gdrive_helper.get_or_create_subfolders(drive_service, parent_id=args.gdrive_folder)
        flux_folder_id = folder_ids.get("02_Flux_Data")

        if flux_folder_id and drive_service:
            # Create subfolder for this account inside 02_Flux_Data
            q = f"'{flux_folder_id}' in parents and name = '{acc_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            res = drive_service.files().list(q=q, fields="files(id, name)").execute()
            items = res.get("files", [])
            if items:
                account_folder_id = items[0]["id"]
            else:
                meta = {
                    "name": acc_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [flux_folder_id]
                }
                created = drive_service.files().create(body=meta, fields="id, name").execute()
                account_folder_id = created["id"]
        print(f">>> [DRIVE] Google Drive connected. Subfolder: 02_Flux_Data/{acc_name}")
    except Exception as e:
        print(f">>> [WARNING] Google Drive connection failed: {e}. Output will be saved locally.")

    # Load plan
    with open(args.plan_file, "r", encoding="utf-8") as pf:
        full_plan = json.load(pf)

    matched_acc = None
    for acc in full_plan:
        if acc.lower() == acc_name.lower():
            matched_acc = acc
            break
    if not matched_acc and full_plan:
        matched_acc = list(full_plan.keys())[0]

    runner_jobs = full_plan[matched_acc].get(str(args.runner_id), [])
    total_jobs = len(runner_jobs)
    print(f"Runner #{args.runner_id} allocated {total_jobs} jobs from account '{matched_acc}'.")

    # Local output CSV
    out_csv = Path(f"flux_{acc_name}_runner_{args.runner_id:02d}.csv")
    existing_results = {}
    if out_csv.exists():
        try:
            df_old = pd.read_csv(out_csv)
            for _, r in df_old.iterrows():
                existing_results[r["job_name"]] = r.to_dict()
            print(f"Loaded {len(existing_results)} already completed jobs from previous run.")
        except Exception:
            pass

    records = list(existing_results.values())
    start_time = time.time()
    max_duration = args.timeout_hours * 3600

    work_dir = Path("geant4_work")
    work_dir.mkdir(parents=True, exist_ok=True)
    proc_csv_path = Path("process_results.csv")

    for idx, job in enumerate(runner_jobs, 1):
        job_name = job["job_name"]
        if time.time() - start_time > max_duration:
            print(f"\n⚠️ Timeout approaching ({args.timeout_hours}h). Stopping safely.")
            break

        if job_name in existing_results:
            print(f"[{idx}/{total_jobs}] SKIP: {job_name} already completed.")
            continue

        sample = job["sample"]
        e_kev = float(job["energy_kev"])
        e_mev = float(job["energy_mev"])
        th_cm = float(job["thickness_cm"])
        th_mm = th_cm * 10.0

        print(f"\n[{idx}/{total_jobs}] RUNNING: {job_name} | {sample} | E={e_kev} keV | Th={th_cm} cm...")

        # Generate macro file
        macro_content = f"""/control/verbose 0
/run/verbose 0
/DetectorConstruction/Sample_Material {sample}
/DetectorConstruction/Sample_Thickness {th_mm:.6f}
/DetectorConstruction/update
/run/initialize
/gun/energy {e_kev:.4f} keV
/run/beamOn {args.primaries}
"""
        mac_file = work_dir / f"job_{job_name}.mac"
        with open(mac_file, "w", encoding="utf-8") as mf:
            mf.write(macro_content)

        t0 = time.time()
        res = subprocess.run([sim_bin, str(mac_file)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        elapsed = time.time() - t0

        if res.returncode != 0:
            print(f"    [SIM ERROR]: {res.stderr.strip()[-300:]}")

        peak_flux, tot_flux = parse_process_results_last_row(proc_csv_path)

        rec = {
            "job_name": job_name,
            "energy_mev": e_mev,
            "sample": sample,
            "thickness_cm": th_cm,
            "peak_flux": peak_flux,
            "peak_err": 0.0,
            "total_flux": tot_flux,
            "total_err": 0.0,
            "elapsed_s": round(elapsed, 2)
        }
        records.append(rec)
        existing_results[job_name] = rec

        print(f">>> [JOB_DONE] {job_name} | Peak: {peak_flux:.6e} | Total: {tot_flux:.6e} | Elapsed: {elapsed:.1f}s", flush=True)

        # Update CSV
        df_out = pd.DataFrame(records)
        df_out.to_csv(out_csv, index=False)

        # Upload to Google Drive periodically
        if drive_service and account_folder_id:
            try:
                gdrive_helper.upload_file_to_folder(drive_service, str(out_csv), account_folder_id)
            except Exception as e:
                print(f"    [DRIVE UPLOAD WARN]: {e}")

    print("\n" + "=" * 80)
    print(f"🎉 RUNNER #{args.runner_id} FINISHED {len(records)}/{total_jobs} JOBS!")
    print("=" * 80)

if __name__ == "__main__":
    main()
