"""
export_individual_quantity_workbooks_g4.py
Xuất 8 file Excel riêng biệt cho từng đại lượng (MAC, LAC, HVL, TVL, MFP, RPE, Zeff, Nel)
cho Geant4 (10^8 primaries) và upload lên Google Drive: Paper10.1_Geant4/01_Summary_Excel_Results.
"""
import sys
from pathlib import Path

# Add Openmc_mac to sys.path to reuse process_suite
sys.path.insert(0, r"C:\2026.9.28_Paper10\Openmc_mac")
from export_individual_quantity_workbooks import process_suite

RAW_CSV = r"C:\2026.9.28_Paper10\Geant4_10e8_Raw_Merged.csv"
OUTPUT_DIR = r"C:\2026.9.28_Paper10\Geant4_mac"
GDRIVE_SUMMARY_FOLDER_ID = "1w5PD4hjwRkjpnwNNRJqlSbV5jmhpayXG" # 01_Summary_Excel_Results

def main():
    print("=" * 80)
    print("🚀 BẮT ĐẦU XUẤT 8 FILE EXCEL ĐỘC LẬP CHO GEANT4 (10^8)")
    print("=" * 80)
    process_suite(
        name="Geant4",
        raw_csv_path=RAW_CSV,
        output_dir=OUTPUT_DIR,
        drive_folder_id=GDRIVE_SUMMARY_FOLDER_ID
    )
    print("\n" + "=" * 80)
    print("🎉 HOÀN THÀNH XUẤT 8 FILE EXCEL ĐỘC LẬP CHO GEANT4!")
    print("=" * 80)

if __name__ == "__main__":
    main()
