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
    parser.add_argument("--primaries", type=int, default=100000000)
    parser.add_argument("--gdrive-folder", type=str, required=True)
    parser.add_argument("--checklist", type=str, default="missing_g4.csv")
    parser.add_argument("--github-user", type=str, default="local")
    parser.add_argument("--timeout-hours", type=float, default=5.4)
    return parser.parse_args()

def parse_process_results_last_row(csv_path: Path):
    if not csv_path.exists():
        return 0.0, 0.0
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return 0.0, 0.0
        last = df.iloc[-1]
        return float(last.get("CrossFlux_total", 0.0)), float(last.get("CrossFlux_uncollided", 0.0))
    except:
        return 0.0, 0.0

def main():
    args = parse_args()
    print(f"Starting 1-to-1 Worker: Runner #{args.runner_id} on {args.github_user}")
    
    # 1. Init Drive & Get Flux Folder
    drive_service = gdrive_helper.get_drive_service()
    subfolders = gdrive_helper.get_or_create_subfolders(drive_service, parent_id=args.gdrive_folder)
    flux_folder_id = subfolders.get("02_Flux_Data")
    
    # 2. Get existing files in Flux Folder
    print("Checking existing files on Drive...")
    q = f"'{flux_folder_id}' in parents and trashed = false"
    res = drive_service.files().list(q=q, fields="files(id, name)", pageSize=1000).execute()
    existing_files = {f['name'] for f in res.get('files', [])}
    print(f"Found {len(existing_files)} files already on Drive.")
    
    # 3. Read Checklist and divide workload
    df_check = pd.read_csv(args.checklist)
    # Filter only those assigned to this runner
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
    proc_csv_path = Path("process_results.csv")
    
    for row in my_jobs:
        e_mev = float(row['energy_mev'])
        sample = str(row['sample']).upper()
        thick = float(row['thickness_cm'])
        
        job_name = f"{sample}_{e_mev:.3f}_{thick:.3f}"
        out_csv = f"{job_name}.csv"
        
        if out_csv in existing_files:
            print(f"[{job_name}] ALREADY EXISTS ON DRIVE. SKIPPING.")
            continue
            
        print(f"\n--- RUNNING JOB: {job_name} ---")
        
        mac_path = work_dir / f"{job_name}.mac"
        with open(mac_path, "w", encoding="utf-8") as f:
            f.write(f"/control/verbose 0\n/run/verbose 0\n/event/verbose 0\n/tracking/verbose 0\n")
            f.write(f"/process/em/verbose 0\n")
            f.write(f"/det/setSampleMaterial {sample}\n")
            f.write(f"/det/setSampleThickness {thick} cm\n")
            f.write(f"/run/initialize\n")
            f.write(f"/gun/energy {e_mev} MeV\n")
            f.write(f"/run/beamOn {args.primaries}\n")
            
        t0 = time.time()
        cmd = [sim_bin, str(mac_path)]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
        
        if res.returncode != 0:
            print(f"SIM ERROR: {res.stderr[-300:]}")
            continue
            
        peak_flux, tot_flux = parse_process_results_last_row(proc_csv_path)
        
        # Save exact 1-to-1 file
        rec = {
            "job_name": job_name,
            "energy_mev": e_mev,
            "sample": sample,
            "thickness_cm": thick,
            "peak_flux": peak_flux,
            "tot_flux": tot_flux
        }
        df_out = pd.DataFrame([rec])
        df_out.to_csv(out_csv, index=False)
        
        # Upload
        print(f"Uploading {out_csv} to Drive...")
        gdrive_helper.upload_file_to_folder(drive_service, out_csv, flux_folder_id)
        print(f"Done! Elapsed: {time.time()-t0:.1f}s")
        
if __name__ == "__main__":
    main()
