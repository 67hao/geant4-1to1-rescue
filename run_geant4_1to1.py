import argparse
import os
import sys
import time
import subprocess
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import gdrive_helper

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-id", type=int, required=True)
    parser.add_argument("--num-runners", type=int, default=20)
    parser.add_argument("--primaries", type=int, default=10000000)
    parser.add_argument("--gdrive-folder", type=str, required=True)
    parser.add_argument("--checklist", type=str, default="missing_g4.csv")
    parser.add_argument("--github-user", type=str, default="local")
    parser.add_argument("--timeout-hours", type=float, default=5.4)
    return parser.parse_args()

def parse_process_results_last_row():
    """Locate and parse the last row of process_results.csv."""
    candidates = [
        Path.cwd() / "process_results.csv",
        Path("process_results.csv"),
        Path("build") / "process_results.csv",
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            try:
                df = pd.read_csv(c)
                if not df.empty:
                    last = df.iloc[-1]
                    tot = float(last.get("CrossFlux_total", 0.0))
                    uncoll = float(last.get("CrossFlux_uncollided", 0.0))
                    return uncoll, tot
            except Exception as e:
                print(f"Error parsing {c}: {e}")
                
    for c in Path.cwd().rglob("process_results.csv"):
        if c.exists() and c.stat().st_size > 0:
            try:
                df = pd.read_csv(c)
                if not df.empty:
                    last = df.iloc[-1]
                    tot = float(last.get("CrossFlux_total", 0.0))
                    uncoll = float(last.get("CrossFlux_uncollided", 0.0))
                    return uncoll, tot
            except Exception:
                pass
                
    return 0.0, 0.0

def main():
    args = parse_args()
    print(f"Starting 1-to-1 Worker: Runner #{args.runner_id} on {args.github_user}")
    print(f"Primaries: {args.primaries:,}")
    
    # 1. Init Drive & Get Flux Folder
    drive_service = gdrive_helper.get_drive_service()
    subfolders = gdrive_helper.get_or_create_subfolders(drive_service, parent_id=args.gdrive_folder)
    flux_folder_id = subfolders.get("02_Flux_Data")
    
    # 2. Read Checklist and divide workload
    df_check = pd.read_csv(args.checklist)
    my_jobs = []
    for i, row in df_check.iterrows():
        if i % args.num_runners == (args.runner_id - 1):
            my_jobs.append(row)
            
    if not my_jobs:
        print("No jobs assigned to this runner! Exiting.")
        return
        
    print(f"Runner assigned {len(my_jobs)} jobs from checklist.")
    
    sim_bin = "./build/Sim" if os.path.exists("./build/Sim") else "./build/Release/Sim.exe"
    if not os.path.exists(sim_bin):
        sim_bin = "./Sim" # fallback
        
    start_time = time.time()
    work_dir = Path("geant4_work")
    work_dir.mkdir(parents=True, exist_ok=True)
    
    for row in my_jobs:
        e_mev = float(row['energy_mev'])
        e_kev = e_mev * 1000.0
        sample = str(row['sample']).upper()
        thick_cm = float(row['thickness_cm'])
        thick_mm = thick_cm * 10.0
        
        job_name = f"{sample}_{e_mev:.3f}_{thick_cm:.3f}"
        out_csv = f"{job_name}.csv"
        
        print(f"\n--- RUNNING JOB: {job_name} ({sample}, E={e_kev:.1f} keV, Th={thick_mm:.2f} mm) ---")
        
        mac_path = work_dir / f"{job_name}.mac"
        macro_content = f"""/control/verbose 0
/run/verbose 0
/DetectorConstruction/Sample_Material {sample}
/DetectorConstruction/Sample_Thickness {thick_mm:.6f}
/DetectorConstruction/update
/run/initialize
/gun/energy {e_kev:.4f} keV
/run/beamOn {args.primaries}
"""
        with open(mac_path, "w", encoding="utf-8") as f:
            f.write(macro_content)
            
        # Clean any existing process_results.csv before run to avoid stale data
        for p in Path.cwd().rglob("process_results.csv"):
            try:
                p.unlink()
            except Exception:
                pass
            
        t0 = time.time()
        cmd = [sim_bin, str(mac_path)]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
        
        if res.returncode != 0:
            print(f"SIM ERROR (code {res.returncode}): {res.stderr[-300:]}")
            print(f"STDOUT: {res.stdout[-300:]}")
            
        peak_flux, tot_flux = parse_process_results_last_row()
        print(f">>> Result for {job_name}: peak_flux (uncollided) = {peak_flux:.6e}, tot_flux = {tot_flux:.6e}")
        
        # Save exact 1-to-1 file
        rec = {
            "job_name": job_name,
            "energy_mev": e_mev,
            "sample": sample,
            "thickness_cm": thick_cm,
            "peak_flux": peak_flux,
            "tot_flux": tot_flux
        }
        df_out = pd.DataFrame([rec])
        df_out.to_csv(out_csv, index=False)
        
        # Upload to Google Drive (updates existing file)
        print(f"Uploading {out_csv} to Drive...")
        gdrive_helper.upload_file_to_folder(drive_service, out_csv, flux_folder_id)
        print(f"Done! Elapsed: {time.time()-t0:.1f}s")
        
if __name__ == "__main__":
    main()
