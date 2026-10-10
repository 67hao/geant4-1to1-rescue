# =========================================================================
# CMakeLists.txt
# =========================================================================

# --- 1. CMake Initial Setup ---

# a) Require CMake version between 3.16 and 3.27, otherwise stop processing
cmake_minimum_required(VERSION 3.16...3.27 FATAL_ERROR) # 

# b) Declare project source directory name
project(ECD_NaI_Detector)

# c) Force CMake to use "Release" configuration
set(CMAKE_CONFIGURATION_TYPES "Release" CACHE STRING "Configs" FORCE)

# --- 2. Find Geant4 package ---
if(EXISTS "/tmp/g4_env")
  list(PREPEND CMAKE_PREFIX_PATH "/tmp/g4_env")
  set(CMAKE_FIND_ROOT_PATH "/tmp/g4_env")
  set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
  set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
endif()

# a) Find Geant4 package
find_package(Geant4 REQUIRED)

# b) Include Geant4 installation directory
include(${Geant4_USE_FILE})

# --- 3. Glob all source, header and macro files ---
file(GLOB sources ${PROJECT_SOURCE_DIR}/src/*.cc)
file(GLOB headers ${PROJECT_SOURCE_DIR}/include/*.hh)
file(GLOB macros ${PROJECT_SOURCE_DIR}/macros/*.mac)

# --- 4. Create executable target and link to Geant4 libraries ---

# a) Create executable target Sim from main.cc and all source and header files
add_executable(Sim main.cc ${sources} ${headers}) 
target_link_libraries(Sim ${Geant4_LIBRARIES}) # Link Sim to Geant4 libraries
target_include_directories(Sim PRIVATE ${PROJECT_SOURCE_DIR}/include) # Include header files for Sim
target_compile_definitions(Sim PRIVATE MACROPATH="${PROJECT_BINARY_DIR}/macros") # Define MACROPATH for Sim in build folder


# --- 5. Copy macro files to build/macros directory ---

# a) Create build/macros directory if it doesn't exist
file(MAKE_DIRECTORY ${PROJECT_BINARY_DIR}/macros)

# b) Copy each macro file to build/macros directory
foreach(_script ${macros})
    configure_file(${_script} ${PROJECT_BINARY_DIR}/macros COPYONLY) # Copy each macro file to build/macros directory
endforeach()

