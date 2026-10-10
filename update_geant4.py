"""
update_geant4.py - High-speed monitor and data consolidation utility for Geant4 Cluster
- Scans Google Drive (Paper10.1_Geant4/02_Flux_Data) via ThreadPoolExecutor (~2s)
- Syncs raw CSVs to C:\\2026.9.28_Paper10\\Geant4_results_10e8_raw
- Merges into Geant4_10e8_Raw_Merged.csv
- Checks 200 GitHub runners across all 10 accounts in parallel
- Updates projects_state.json for Control Center Dashboard (http://localhost:8080)
"""
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_DIR = Path(r"C:\2026.9.28_Paper10")
GEANT4_DIR = BASE_DIR / "Geant4_mac"
RAW_DIR = BASE_DIR / "Geant4_results_10e8_raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
MERGED_CSV = BASE_DIR / "Geant4_10e8_Raw_Merged.csv"
STATE_FILE = Path(r"C:\antigravity_goat\control_center\projects_state.json")

sys.path.insert(0, str(GEANT4_DIR))
import gdrive_helper
from googleapiclient.http import MediaIoBaseDownload
import io

TOTAL_EXPECTED_JOBS = 1711

def get_drive_folder_files(service, parent_id):
    q = f"'{parent_id}' in parents and trashed = false"
    res = service.files().list(q=q, fields="files(id, name, mimeType, size, modifiedTime)", pageSize=1000).execute()
    items = res.get("files", [])

    csv_files = []
    subfolders = []
    for item in items:
        if item.get("mimeType") == "application/vnd.google-apps.folder":
            subfolders.append(item)
        elif item.get("name", "").endswith(".csv"):
            csv_files.append(item)

    for sf in subfolders:
        q_sub = f"'{sf['id']}' in parents and trashed = false and name contains '.csv'"
        res_sub = service.files().list(q=q_sub, fields="files(id, name, mimeType, size, modifiedTime)", pageSize=1000).execute()
        for f in res_sub.get("files", []):
            f["account_folder"] = sf["name"]
            csv_files.append(f)

    return csv_files

def download_file(service, file_id, dest_path):
    request = service.files().get_media(fileId=file_id)
    with io.FileIO(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

def check_account_runners(acc, token):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{acc}/geant4-parallel-benchmark/actions/runs?per_page=1"
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            runs = r.json().get("workflow_runs", [])
            if runs:
                latest = runs[0]
                run_id = latest["id"]
                jobs_url = f"https://api.github.com/repos/{acc}/geant4-parallel-benchmark/actions/runs/{run_id}/jobs?per_page=100"
                rj = requests.get(jobs_url, headers=headers, timeout=5)
                if rj.status_code == 200:
                    jobs = rj.json().get("jobs", [])
                    in_progress = sum(1 for j in jobs if j.get("status") == "in_progress")
                    completed = sum(1 for j in jobs if j.get("conclusion") == "success")
                    failed = sum(1 for j in jobs if j.get("conclusion") == "failure")
                    return {
                        "account": acc, "run_id": run_id, "status": latest["status"],
                        "conclusion": latest.get("conclusion"), "in_progress": in_progress,
                        "success": completed, "failed": failed, "total_jobs": len(jobs)
                    }
        return {"account": acc, "run_id": None, "status": "none", "in_progress": 0, "success": 0, "failed": 0, "total_jobs": 0}
    except Exception as e:
        return {"account": acc, "run_id": None, "status": "error", "error": str(e), "in_progress": 0, "success": 0, "failed": 0, "total_jobs": 0}

def main():
    t_start = time.time()
    print("=" * 90)
    print("⚡ GEANT4 10^8 - CAP NHAT TIEN DO & TONG HOP DU LIEU CLUSTER GITHUB")
    print("=" * 90)

    # 1. Google Drive
    print(">>> [1/3] Ket noi Google Drive & Dong bo file CSV...")
    service = gdrive_helper.get_drive_service()
    parent_id = "1Q6T25GCTu3UO2xzlJrNUPKCzSdjoGFIx" # Paper10.1_Geant4
    subfolders = gdrive_helper.get_or_create_subfolders(service, parent_id=parent_id)
    flux_fid = subfolders.get("02_Flux_Data")

    csv_files = get_drive_folder_files(service, flux_fid) if flux_fid else []
    print(f"    Tim thay {len(csv_files)} file CSV tren Drive (Paper10.1_Geant4/02_Flux_Data).")

    download_count = 0
    for f in csv_files:
        fname = f["name"]
        acc_dir = RAW_DIR / f.get("account_folder", "")
        acc_dir.mkdir(parents=True, exist_ok=True)
        local_path = acc_dir / fname
        fsize = int(f.get("size", 0))
        if not local_path.exists() or local_path.stat().st_size < fsize:
            try:
                download_file(service, f["id"], local_path)
                download_count += 1
            except Exception:
                pass

    if download_count > 0:
        print(f"    Da tai/dong bo moi {download_count} file CSV ve {RAW_DIR}.")
    else:
        print("    Tat ca file CSV da duoc dong bo san local (Cache OK).")

    # 2. Merge Data
    print(">>> [2/3] Tong hop toan bo job da hoan thanh...")
    all_dfs = []
    for csv_p in RAW_DIR.glob("**/*.csv"):
        try:
            df = pd.read_csv(csv_p)
            if "job_name" in df.columns and len(df) > 0:
                all_dfs.append(df)
        except Exception:
            pass

    if all_dfs:
        merged_df = pd.concat(all_dfs, ignore_index=True)
        merged_df = merged_df.drop_duplicates(subset=["job_name"], keep="last")
        merged_df.to_csv(MERGED_CSV, index=False, encoding="utf-8")
        completed_jobs = len(merged_df)
    else:
        completed_jobs = 0
        merged_df = pd.DataFrame()

    # 3. Check Cluster
    print(">>> [3/3] Quet trang thai Cluster 200 Runners...")
    acc_stats = []
    target_accounts = [
        'haoidlemystic1', 'vuicho', 'haoidle4zk', '67hao', 'idlemystich',
        'CarwynDuc', 'laolaolaoma09', 'Bethwl', 'coredaohaojack'
    ]
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as sf:
            state_data = json.load(sf)
        accounts_cfg = state_data.get("accounts", {})

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(check_account_runners, acc, accounts_cfg[acc]['pat_token'])
                for acc in target_accounts if acc in accounts_cfg
            ]
            for fut in as_completed(futures):
                acc_stats.append(fut.result())

    acc_stats.sort(key=lambda x: x['account'])

    pct = (completed_jobs / TOTAL_EXPECTED_JOBS) * 100.0
    print("\n" + "=" * 90)
    print(f"📊 TIEN DO GEANT4 (10^8): {completed_jobs:,} / {TOTAL_EXPECTED_JOBS:,} JOBS ({pct:.2f}%)")
    print("=" * 90)

    if not merged_df.empty:
        sample_counts = merged_df['sample'].value_counts().to_dict()
        samples_info = "  ".join(f"{s}: {c}" for s, c in sorted(sample_counts.items()))
        print(f"Chi tiet theo mau (Sample):\n  {samples_info}")

    print("-" * 90)
    print(f"{'ACCOUNT':<16} | {'RUN ID':<12} | {'STATUS':<12} | {'RUNNING':<8} | {'SUCCESS':<8} | {'FAILED':<8}")
    print("-" * 90)

    total_running = 0
    total_failed = 0
    for st in acc_stats:
        run_id_str = str(st.get("run_id") or "N/A")
        status_str = str(st.get("status") or "N/A")
        inp = st.get("in_progress", 0)
        succ = st.get("success", 0)
        fail = st.get("failed", 0)
        total_running += inp
        total_failed += fail
        print(f"{st['account']:<16} | {run_id_str:<12} | {status_str:<12} | {inp:<8} | {succ:<8} | {fail:<8}")
    print("-" * 90)
    print(f"Tong cong: {total_running} Runners dang chay song song | {total_failed} Runners loi | Tong runner: 200 runners\n")

    # Update state file
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as sf:
                state = json.load(sf)
            if "projects" not in state:
                state["projects"] = {}
            state["projects"]["Paper_10_1_Geant4"] = {
                "name": "Paper 10.1 (Geant4 10^8 Particles Benchmark)",
                "status": "IN_PROGRESS" if total_running > 0 else ("COMPLETED" if completed_jobs == TOTAL_EXPECTED_JOBS else "PENDING"),
                "total_runs": TOTAL_EXPECTED_JOBS,
                "completed_runs": completed_jobs,
                "progress_pct": round(pct, 2),
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            with open(STATE_FILE, "w", encoding="utf-8") as sf:
                json.dump(state, sf, indent=2)
        except Exception:
            pass

    print(f"⏱️ Thoi gian quet: {time.time() - t_start:.2f}s")
    print("=" * 90)

if __name__ == "__main__":
    main()
