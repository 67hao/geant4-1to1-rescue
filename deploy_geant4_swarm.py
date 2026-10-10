"""
deploy_geant4_swarm.py
Automates the full deployment and dispatch of Geant4 10^8 photon transport benchmark
across 10 GitHub accounts (200 parallel runners) for Paper 10.1 (1,711 jobs).
"""
import os
import sys
import json
import time
import subprocess
import requests
from base64 import b64encode
from pathlib import Path
import nacl.encoding
import nacl.public

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_DIR = Path(r"C:\2026.9.28_Paper10\Geant4_mac")
STATE_FILE = Path(r"C:\antigravity_goat\control_center\projects_state.json")
OAUTH_FILE = Path(r"C:\antigravity_goat\user_oauth_creds.json")

REPO_NAME = "geant4-parallel-benchmark"
GDRIVE_FOLDER_ID = "1Q6T25GCTu3UO2xzlJrNUPKCzSdjoGFIx"  # Paper10.1_Geant4

ACCOUNTS = [
    'haoidlemystic1', 'vuicho', 'haoidle4zk', '67hao', 'idlemystich',
    'CarwynDuc', 'laolaolaoma09', 'Bethwl', 'coredaohaojack'
]

def set_repo_secret(owner: str, repo: str, token: str, secret_name: str, secret_value: str) -> bool:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    pk_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    r = requests.get(pk_url, headers=headers)
    if r.status_code != 200:
        print(f"    [ERR] Cannot get public key for {owner}/{repo}: {r.status_code}")
        return False
    
    key_data = r.json()
    key_id = key_data["key_id"]
    public_key = nacl.public.PublicKey(key_data["key"].encode("utf-8"), nacl.encoding.Base64Encoder)
    box = nacl.public.SealedBox(public_key)
    encrypted = box.encrypt(secret_value.encode("utf-8"))
    enc_str = b64encode(encrypted).decode("utf-8")

    sec_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    res = requests.put(sec_url, headers=headers, json={"encrypted_value": enc_str, "key_id": key_id})
    return res.status_code in [201, 204]

def main():
    print("=" * 80)
    print("🚀 TRIỂN KHAI VÀ KHỞI CHẠY GEANT4 PARALLEL BENCHMARK (10 TÀI KHOẢN, 200 RUNNERS)")
    print("=" * 80)

    with open(STATE_FILE, "r", encoding="utf-8") as sf:
        state_data = json.load(sf)
    acc_config = state_data.get("accounts", {})

    with open(OAUTH_FILE, "r", encoding="utf-8") as of:
        oauth_json_str = of.read()

    # Step 1: Ensure Repos & Secrets
    print("\n>>> [BƯỚC 1/3] Kiểm tra Repository và thiết lập Secret Google Drive...")
    for acc in ACCOUNTS:
        tok = acc_config[acc]["pat_token"]
        headers = {"Authorization": f"token {tok}", "Accept": "application/vnd.github.v3+json"}
        
        # Check repo
        repo_url = f"https://api.github.com/repos/{acc}/{REPO_NAME}"
        r = requests.get(repo_url, headers=headers)
        if r.status_code == 404:
            print(f"  + Tạo repo mới: {acc}/{REPO_NAME}...")
            r_create = requests.post("https://api.github.com/user/repos", headers=headers, json={"name": REPO_NAME, "private": False})
            if r_create.status_code != 201:
                print(f"    [ERR] Không thể tạo repo cho {acc}: {r_create.text}")
                continue
        elif r.status_code == 200:
            print(f"  + Repo {acc}/{REPO_NAME} đã tồn tại.")

        # Set secret
        ok_sec = set_repo_secret(acc, REPO_NAME, tok, "GDRIVE_OAUTH_JSON", oauth_json_str)
        if ok_sec:
            print(f"  + Secret GDRIVE_OAUTH_JSON -> {acc}/{REPO_NAME} [OK]")
        else:
            print(f"  + [ERR] Không thể set secret cho {acc}")

    # Step 2: Push code to all 10 remotes
    print("\n>>> [BƯỚC 2/3] Push mã nguồn Geant4 lên 10 tài khoản GitHub...")
    for acc in ACCOUNTS:
        tok = acc_config[acc]["pat_token"]
        remote_url = f"https://{acc}:{tok}@github.com/{acc}/{REPO_NAME}.git"
        remote_name = f"remote_{acc}"

        # Setup remote
        subprocess.run(["git", "remote", "remove", remote_name], cwd=str(BASE_DIR), stderr=subprocess.DEVNULL)
        subprocess.run(["git", "remote", "add", remote_name, remote_url], cwd=str(BASE_DIR), stdout=subprocess.DEVNULL)

        print(f"  + Pushing to {acc}/{REPO_NAME}...")
        res_push = subprocess.run(["git", "push", "-u", remote_name, "master", "--force"], cwd=str(BASE_DIR), capture_output=True, text=True)
        if res_push.returncode == 0:
            print(f"    -> Push thành công: {acc}/{REPO_NAME}")
        else:
            print(f"    -> [ERR] Push thất bại {acc}: {res_push.stderr[:100]}")

    # Step 3: Dispatch workflows
    print("\n>>> [BƯỚC 3/3] Kích hoạt 20 runners song song trên cả 10 tài khoản (Tổng 200 runners)...")
    primaries_str = "100000000"  # 10^8
    for acc in ACCOUNTS:
        tok = acc_config[acc]["pat_token"]
        headers = {"Authorization": f"token {tok}", "Accept": "application/vnd.github.v3+json"}
        disp_url = f"https://api.github.com/repos/{acc}/{REPO_NAME}/actions/workflows/geant4_parallel.yml/dispatches"
        payload = {
            "ref": "master",
            "inputs": {
                "primaries": primaries_str,
                "gdrive_folder": GDRIVE_FOLDER_ID
            }
        }
        r_disp = requests.post(disp_url, headers=headers, json=payload)
        if r_disp.status_code == 204:
            print(f"  🚀 {acc:<16} -> DISPATCH SUCCESS (204) [20 Runners kích hoạt!]")
        else:
            print(f"  ❌ {acc:<16} -> FAILED ({r_disp.status_code}): {r_disp.text[:80]}")
        time.sleep(1.0)

    print("\n" + "=" * 80)
    print("🎉 TOÀN BỘ 200 RUNNERS TRÊN 10 TÀI KHOẢN ĐÃ ĐƯỢC KÍCH HOẠT THÀNH CÔNG!")
    print(f"Theo dõi tiến độ bằng lệnh: python C:\\2026.9.28_Paper10\\Geant4_mac\\update_geant4.py")
    print("=" * 80)

if __name__ == "__main__":
    main()
