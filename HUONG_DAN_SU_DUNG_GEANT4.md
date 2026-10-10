# HƯỚNG DẪN VẬN HÀNH & TỐI ƯU HÓA GEANT4 (PAPER 10.1 BENCHMARK)

Tài liệu này cung cấp hướng dẫn toàn diện về cơ chế mô phỏng, tăng tốc vật lý hạt, giải pháp cô lập môi trường biên dịch Conda/CMake trên cụm GitHub Actions và quy trình xuất báo cáo cho **Geant4**.

---

## 1. Cơ Chế Mô Phỏng & Tối Ưu Tăng Tốc Thuần Photon (Pure Photon Acceleration)

### 1.1. Mô Hình Vật Lý Điện Từ (Physics List)
- Sử dụng mô hình `G4EmLivermorePhysics`: mô hình tương tác điện từ năng lượng thấp của phòng thí nghiệm Lawrence Livermore (LLNL), tính toán chính xác tán xạ Rayleigh, tán xạ Compton, hiệu ứng quang điện và tạo cặp từ $250\text{ eV} \to 100\text{ GeV}$.

### 1.2. Kỹ Thuật Triệt Tiêu Hạt Thứ Cấp (Secondary Particle Suppression)
- Trong mô phỏng photon xuyên qua mẫu che chắn, photon tương tác sinh ra các electron thứ cấp (photoelectrons, Compton electrons, electron-positron pairs). Quá trình lan truyền và ion hóa năng lượng của electron trong vật chất chiếm hơn 90% thời gian CPU.
- Để tính toán hệ số suy giảm khối (MAC) và thông lượng photon tới đầu dò, việc theo vết chi tiết electron thứ cấp trong thể tích mẫu là hoàn toàn không cần thiết.
- **Giải pháp tối ưu hóa tại `MySteppingAction.cc`**:
  ```cpp
  // Chỉ theo dõi photon (G4Gamma), triệt tiêu ngay lập tức electron/positron thứ cấp
  if (track->GetDefinition() != G4Gamma::Definition()) {
      track->SetTrackStatus(fStopAndKill);
      return;
  }
  ```
- Kỹ thuật này giúp mô phỏng $10^8$ hạt/job tăng tốc từ **10 – 50 lần**, rút ngắn thời gian chạy từ hàng giờ xuống chỉ còn **khoảng 10 – 15 phút** cho mỗi runner.

### 1.3. Đa Luồng Động (Dynamic Multi-Threading)
- Trong `main.cc`: sử dụng `G4MTRunManager` và tự động nhận diện toàn bộ số vCPU của runner thông qua `G4Threading::G4GetNumberOfCores()`.
- Chế độ chạy Batch tự động vô hiệu hóa `G4VisExecutive` và `G4UIExecutive`, tiết kiệm bộ nhớ RAM và thời gian khởi động.

---

## 2. Giải Pháp Cô Lập Môi Trường Biên Dịch (Conda / CMake / Linker)

Trên máy ảo Ubuntu 22.04 của GitHub Actions, hệ thống host có các thư viện cũ (`libexpat.so.2.4.7`, `libz.so.1.2.11`, `libfreetype.so.2.11.1`, GCC 11 thiếu `CXXABI_1.3.15`). 

Để đảm bảo quá trình biên dịch `Sim` diễn ra trơn tru 100%:
1. **Thiết lập Micromamba tối thiểu**:
   Cài đặt `geant4 expat zlib freetype cmake make gxx_linux-64 python=3.11`.
2. **Cô lập bộ tìm kiếm trong `CMakeLists.txt`**:
   ```cmake
   if(EXISTS "/tmp/g4_env")
     list(PREPEND CMAKE_PREFIX_PATH "/tmp/g4_env")
     set(CMAKE_FIND_ROOT_PATH "/tmp/g4_env")
     set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
     set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
     set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
   endif()
   ```
3. **Chỉ định Trình Biên Dịch Conda & RPATH**:
   Truyền `-DCMAKE_CXX_COMPILER=x86_64-conda-linux-gnu-g++` và `-DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath,/tmp/g4_env/lib -L/tmp/g4_env/lib"` để đảm bảo thực thi binary luôn nạp đúng `libstdc++.so.6` của Conda có hỗ trợ đầy đủ `CXXABI_1.3.15`.

---

## 3. Kiến Trúc Cụm 180 Runners & Google Drive

- **Thư mục Google Drive chuyên biệt**: `Paper10.1_Geant4` (ID: `1Q6T25GCTu3UO2xzlJrNUPKCzSdjoGFIx`).
  - `01_Summary_Excel_Results` (`1w5PD4hjwRkjpnwNNRJqlSbV5jmhpayXG`)
  - `02_Flux_Data` (`1qYPpmQA9TDY4zpYNeZM7KVJjFlVjDrau`)
  - `03_Simulation_Outputs` (`1VA8AbwSQ4_ZvdhvKgKLEe3mQyFqzVGmN`)
  - `04_Input_Decks` (`13IEE8PUl-KVgsFAD-y7QspvhLuHA2wRT`)
  - `05_Execution_Logs_and_Benchmarks` (`1YF3tq5WxRC5V1hEau0Kta-QdtX3P35zE`)
- **Phân bổ 1,711 jobs (`geant4_plan_200.json`)**:
  - 9 tài khoản hoạt động: `haoidlemystic1`, `vuicho`, `haoidle4zk`, `67hao`, `idlemystich`, `CarwynDuc`, `laolaolaoma09`, `Bethwl`, `coredaohaojack`.
  - Mỗi runner chạy 9 – 10 jobs.

---

## 4. Quy Trình Vận Hành (Lệnh Chạy Chuẩn)

### Bước 1: Khởi chạy Swarm 180 Runners
```powershell
python C:\2026.9.28_Paper10\Geant4_mac\deploy_geant4_swarm.py
```

### Bước 2: Kiểm tra Tiến Độ & Tự Động Đồng Bộ Dữ Liệu
```powershell
python C:\2026.9.28_Paper10\Geant4_mac\update_geant4.py
```

### Bước 3: Xuất Dữ Liệu Ra 8 File Excel Riêng Biệt & So Sánh EpiXS
```powershell
python C:\2026.9.28_Paper10\Geant4_mac\export_individual_quantity_workbooks_g4.py
```
Các file Excel đầu ra:
- `Paper_10_1_Geant4_MAC_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_LAC_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_HVL_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_TVL_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_MFP_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_Zeff_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_Nel_vs_EpiXS.xlsx`
- `Paper_10_1_Geant4_RPE_vs_EpiXS.xlsx`

### Chạy kiểm tra nhanh cục bộ (Local Single Job):
```powershell
./build/Release/Sim.exe test_quick.mac
```
