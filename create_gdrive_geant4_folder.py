"""
create_gdrive_geant4_folder.py
Creates the dedicated Google Drive folder for Paper 10.1 Geant4 and saves the IDs to gdrive_folders.json
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, r"C:\2026.9.28_Paper10\Openmc_mac")
import gdrive_helper

def main():
    service = gdrive_helper.get_drive_service()
    
    # 1. Check if Paper10.1_Geant4 already exists
    q = "name = 'Paper10.1_Geant4' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = service.files().list(q=q, fields="files(id, name)").execute()
    files = res.get("files", [])
    
    if files:
        parent_id = files[0]["id"]
        print(f"Thu muc Paper10.1_Geant4 da ton tai: {parent_id}")
    else:
        meta = {
            "name": "Paper10.1_Geant4",
            "mimeType": "application/vnd.google-apps.folder"
        }
        folder = service.files().create(body=meta, fields="id, name").execute()
        parent_id = folder["id"]
        print(f"Da tao thu muc Paper10.1_Geant4 moi tren Google Drive: {parent_id}")

    # 2. Tao cac thu muc con
    subfolders = [
        "01_Summary_Excel_Results",
        "02_Flux_Data",
        "03_Simulation_Outputs",
        "04_Input_Decks",
        "05_Execution_Logs_and_Benchmarks"
    ]
    
    folder_map = {}
    for sf in subfolders:
        q_sf = f"'{parent_id}' in parents and name = '{sf}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_sf = service.files().list(q=q_sf, fields="files(id, name)").execute()
        items = res_sf.get("files", [])
        if items:
            folder_map[sf] = items[0]["id"]
        else:
            meta_sf = {
                "name": sf,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]
            }
            created_sf = service.files().create(body=meta_sf, fields="id, name").execute()
            folder_map[sf] = created_sf["id"]
        print(f"  + Subfolder: {sf} -> {folder_map[sf]}")
        
    cfg = {
        "parent": parent_id,
        "subfolders": folder_map
    }
    
    out_cfg_path = Path(r"C:\2026.9.28_Paper10\Geant4_mac\gdrive_folders.json")
    with open(out_cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"\nDa luu cau hinh vao: {out_cfg_path}")

if __name__ == "__main__":
    main()
