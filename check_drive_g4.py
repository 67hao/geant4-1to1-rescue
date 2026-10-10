import sys
sys.path.append(r'C:\2026.9.28_Paper10\Geant4_mac')
import gdrive_helper
import json
service = gdrive_helper.get_drive_service()
with open('gdrive_folders.json') as f: folders = json.load(f)
f_id = folders['subfolders']['02_Flux_Data']
res = service.files().list(q=f"'{f_id}' in parents and name contains 'flux_runner_' and trashed = false", pageSize=1000, fields="files(name)").execute().get('files', [])
print(f"Found {len(res)} files on Google Drive for Geant4!")
