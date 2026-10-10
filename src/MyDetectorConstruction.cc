// =========================================================================
// Header Definition
// =========================================================================

// 1. Include Local headers
#include "MyDetectorConstruction.hh" // Geometry definition class
#include "MySensitiveDetector.hh"    // Custom Sensitive Detector

// 2. Include Geant4 headers
#include "G4NistManager.hh"          // Material database
#include "G4Box.hh"                  // Box geometry
#include "G4Tubs.hh"                 // Cylinder geometry
#include "G4Sphere.hh"
#include "G4LogicalVolume.hh"        // Logical volume
#include "G4VPhysicalVolume.hh"
#include "G4PVPlacement.hh"          // Physical volume placement
#include "G4SubtractionSolid.hh"     // Boolean subtraction solid
#include "G4VisAttributes.hh"        // Visualization attributes
#include "G4Colour.hh"               // Colors
#include "G4Region.hh"               // Regions
#include "G4SDManager.hh"            // Sensitive detector manager
#include "G4SystemOfUnits.hh"        // Units
#include "G4RegionStore.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4IStore.hh"
#include "G4RunManager.hh"           // Run manager
#include "G4OpticalSurface.hh"
#include "G4MaterialPropertiesTable.hh"
#include "G4LogicalSkinSurface.hh"
#include "G4ProductionCuts.hh"
#include <map>

// =========================================================================
// Geometry Dimensions
// =========================================================================
// Geometry Dimensions - Paper 10.1 Benchmark (PNE 2022, Fig. 1 & Sec 2.2)
// =========================================================================
namespace GEO {
	// 1. World Volume (Galactic Vacuum)
	const G4double WorldSize = 3 * m;

	// 2. Source: Point photon source at (0, 0, 0)
	const G4double Source_Radius = 0.5 * mm;

	// 3. Pb Collimator: z = 10.0 cm to 50.0 cm (length 40 cm)
	const G4double Collimator_ZFront = 10.0 * cm;
	const G4double Collimator_ZBack  = 50.0 * cm;
	const G4double Collimator_Length = Collimator_ZBack - Collimator_ZFront; // 40 cm
	const G4double Collimator_InnerRadius = 0.5 * cm; // 5 mm
	const G4double Collimator_OuterRadius = 3.0 * cm; // 30 mm
	const G4double Collimator_PosZ = (Collimator_ZFront + Collimator_ZBack) / 2.0; // 30 cm

	// 4. Glass Sample (S1 - S8): front face at z = 50.0 cm, radius = 5.0 cm
	const G4double Sample_ZFront = 50.0 * cm;
	const G4double Sample_Radius = 5.0 * cm; // 50 mm
	const G4double Default_Sample_Thickness = 5.0 * mm;

	// 5. Outer Pb Shield: z = 45.0 cm to 75.0 cm (length 30 cm)
	const G4double Shield_ZFront = 45.0 * cm;
	const G4double Shield_ZBack  = 75.0 * cm;
	const G4double Shield_Length = Shield_ZBack - Shield_ZFront; // 30 cm
	const G4double Shield_InnerRadius = 8.0 * cm; // 80 mm
	const G4double Shield_OuterRadius = 10.0 * cm; // 100 mm
	const G4double Shield_PosZ = (Shield_ZFront + Shield_ZBack) / 2.0; // 60 cm

	// 6. Detection Field (F4 equivalent): z = 70.0 cm to 72.0 cm, radius = 5.0 cm
	const G4double Det_ZFront = 70.0 * cm;
	const G4double Det_ZBack  = 72.0 * cm;
	const G4double Det_Length = Det_ZBack - Det_ZFront; // 2 cm
	const G4double Det_Radius = 5.0 * cm; // 50 mm

	// 6b. Virtual Detector Plane (surface-crossing flux tally at front of detection field)
	const G4double DetPlane_Radius    = Det_Radius; // 5.0 cm (Area = 78.5398 cm2)
	const G4double DetPlane_Thickness = 1.0e-3 * mm; // thin virtual plane
	const G4double DetPlane_PosZ      = Det_ZFront + DetPlane_Thickness / 2.0;
}

namespace {
	struct SampleDims { G4double length, width, thickness; };
	const std::map<G4String, SampleDims> kSampleDims = {};
}

// =========================================================================
// Constructor / Destructor
// =========================================================================
MyDetectorConstruction::MyDetectorConstruction()
	: G4VUserDetectorConstruction(),
	fMessenger(nullptr),
	fSample_Thickness(5.0 * mm), // Default HDPE+hBN Layer Thickness
	fSampleMaterial("S1"),        // NEW: default sample material, can be changed via messenger
	// NEW: Collimator2 height, now configurable via macro (default matches old GEO constant)
	fCollimator2_Height(3.0 * cm)
{
	// Messenger for setting the volume fraction of hBN in the composite material
	fMessenger = new G4GenericMessenger(this, "/DetectorConstruction/", "Detector Construction Control");
	auto& fSample_Thicknesscmd = fMessenger->DeclareProperty("Sample_Thickness", fSample_Thickness, "Set Sample_Thickness");
	// NEW: allow choosing which sample material (S0, S1, S2, ..., S7, S8) to use for the run
	auto& fSampleMaterialCmd = fMessenger->DeclareProperty("Sample_Material", fSampleMaterial, "Set Sample material name (e.g. S1, S2, S3...)");
	// NEW: Collimator2 height, settable from .mac files, e.g.:
	//   /DetectorConstruction/Collimator2_Height 3 cm
	//   /DetectorConstruction/update
	auto& fCollimator2_HeightCmd = fMessenger->DeclareProperty("Collimator2_Height", fCollimator2_Height, "Set Collimator2 height");
	fMessenger->DeclareMethod("update", &MyDetectorConstruction::UpdateGeometry, "Update geometry after parameter changes");

}
MyDetectorConstruction::~MyDetectorConstruction() {}

// =========================================================================
// Define Materials
// =========================================================================
void MyDetectorConstruction::DefineMaterials() {
	G4NistManager* NIST = G4NistManager::Instance();
	// ===============================================
	// 1. NIST Materials
	// ===============================================
	NIST->FindOrBuildMaterial("G4_AIR");
	NIST->FindOrBuildMaterial("G4_Galactic");
	NIST->FindOrBuildMaterial("G4_SODIUM_IODIDE");
	NIST->FindOrBuildMaterial("G4_Pb");


	// ===============================================
	// 2. Sample Materials
	// ===============================================

	// [0]. S0: "No sample" placeholder - vacuum, so the Sample volume
	//      still exists geometrically (Collimator2 position unaffected)
	//      but is effectively transparent to radiation.
	//      Select via macro:
	//        /DetectorConstruction/Sample_Material S0
	//        /DetectorConstruction/update
	if (!G4Material::GetMaterial("S0", false)) {
		new G4Material("S0", 1, 1.008 * g / mole, 1e-25 * g / cm3,
			kStateGas, 2.73 * kelvin, 3e-18 * pascal);
	}

	// Paper 10.1 (PNE 2022) Gadolinium Silicoborate glass system (S1 -> S8)
	// Mass fractions and densities taken from Table 1 of Paper 10.1:
	// Elements used: Li, B, O, Al, Si, Ca, Gd

	// [1]. S1: 45 B2O3 - 10 SiO2 - 40 Li2O - 5 Al2O3 - 0 Gd2O3 (rho = 2.390 g/cm3)
	if (!G4Material::GetMaterial("S1", false)) {
		G4Material* S1 = new G4Material("S1", 2.390 * g / cm3, 5);
		S1->AddElement(NIST->FindOrBuildElement("Li"), 0.18583);
		S1->AddElement(NIST->FindOrBuildElement("B"),  0.13976);
		S1->AddElement(NIST->FindOrBuildElement("O"),  0.60120);
		S1->AddElement(NIST->FindOrBuildElement("Al"), 0.02646);
		S1->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
	}

	// [2]. S2: 40 B2O3 - 10 SiO2 - 40 Li2O - 5 Al2O3 - 5 Gd2O3 (rho = 2.725 g/cm3)
	if (!G4Material::GetMaterial("S2", false)) {
		G4Material* S2 = new G4Material("S2", 2.725 * g / cm3, 6);
		S2->AddElement(NIST->FindOrBuildElement("Li"), 0.18583);
		S2->AddElement(NIST->FindOrBuildElement("B"),  0.12423);
		S2->AddElement(NIST->FindOrBuildElement("O"),  0.57335);
		S2->AddElement(NIST->FindOrBuildElement("Al"), 0.02646);
		S2->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S2->AddElement(NIST->FindOrBuildElement("Gd"), 0.04338);
	}

	// [3]. S3: 35 B2O3 - 10 SiO2 - 40 Li2O - 5 Al2O3 - 10 Gd2O3 (rho = 2.908 g/cm3)
	if (!G4Material::GetMaterial("S3", false)) {
		G4Material* S3 = new G4Material("S3", 2.908 * g / cm3, 6);
		S3->AddElement(NIST->FindOrBuildElement("Li"), 0.18583);
		S3->AddElement(NIST->FindOrBuildElement("B"),  0.10870);
		S3->AddElement(NIST->FindOrBuildElement("O"),  0.54550);
		S3->AddElement(NIST->FindOrBuildElement("Al"), 0.02646);
		S3->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S3->AddElement(NIST->FindOrBuildElement("Gd"), 0.08676);
	}

	// [4]. S4: 30 B2O3 - 10 SiO2 - 40 Li2O - 5 Al2O3 - 15 Gd2O3 (rho = 3.103 g/cm3)
	if (!G4Material::GetMaterial("S4", false)) {
		G4Material* S4 = new G4Material("S4", 3.103 * g / cm3, 6);
		S4->AddElement(NIST->FindOrBuildElement("Li"), 0.18583);
		S4->AddElement(NIST->FindOrBuildElement("B"),  0.09317);
		S4->AddElement(NIST->FindOrBuildElement("O"),  0.51765);
		S4->AddElement(NIST->FindOrBuildElement("Al"), 0.02646);
		S4->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S4->AddElement(NIST->FindOrBuildElement("Gd"), 0.13014);
	}

	// [5]. S5: 60 B2O3 - 10 SiO2 - 10 CaO - 20 Gd2O3 (rho = 3.836 g/cm3)
	if (!G4Material::GetMaterial("S5", false)) {
		G4Material* S5 = new G4Material("S5", 3.836 * g / cm3, 5);
		S5->AddElement(NIST->FindOrBuildElement("B"),  0.18635);
		S5->AddElement(NIST->FindOrBuildElement("O"),  0.52192);
		S5->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S5->AddElement(NIST->FindOrBuildElement("Ca"), 0.07147);
		S5->AddElement(NIST->FindOrBuildElement("Gd"), 0.17352);
	}

	// [6]. S6: 55 B2O3 - 10 SiO2 - 10 CaO - 25 Gd2O3 (rho = 3.909 g/cm3)
	if (!G4Material::GetMaterial("S6", false)) {
		G4Material* S6 = new G4Material("S6", 3.909 * g / cm3, 5);
		S6->AddElement(NIST->FindOrBuildElement("B"),  0.17082);
		S6->AddElement(NIST->FindOrBuildElement("O"),  0.49407);
		S6->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S6->AddElement(NIST->FindOrBuildElement("Ca"), 0.07147);
		S6->AddElement(NIST->FindOrBuildElement("Gd"), 0.21690);
	}

	// [7]. S7: 50 B2O3 - 10 SiO2 - 10 CaO - 30 Gd2O3 (rho = 4.181 g/cm3)
	if (!G4Material::GetMaterial("S7", false)) {
		G4Material* S7 = new G4Material("S7", 4.181 * g / cm3, 5);
		S7->AddElement(NIST->FindOrBuildElement("B"),  0.15529);
		S7->AddElement(NIST->FindOrBuildElement("O"),  0.46622);
		S7->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S7->AddElement(NIST->FindOrBuildElement("Ca"), 0.07147);
		S7->AddElement(NIST->FindOrBuildElement("Gd"), 0.26028);
	}

	// [8]. S8: 45 B2O3 - 10 SiO2 - 10 CaO - 35 Gd2O3 (rho = 4.411 g/cm3)
	if (!G4Material::GetMaterial("S8", false)) {
		G4Material* S8 = new G4Material("S8", 4.411 * g / cm3, 5);
		S8->AddElement(NIST->FindOrBuildElement("B"),  0.13976);
		S8->AddElement(NIST->FindOrBuildElement("O"),  0.43837);
		S8->AddElement(NIST->FindOrBuildElement("Si"), 0.04674);
		S8->AddElement(NIST->FindOrBuildElement("Ca"), 0.07147);
		S8->AddElement(NIST->FindOrBuildElement("Gd"), 0.30366);
	}

}

// =========================================================================
// Construct Geometry - Paper 10.1 Benchmark (PNE 2022 Fig. 1 & Sec 2.2)
// =========================================================================
G4VPhysicalVolume* MyDetectorConstruction::Construct() {
	DefineMaterials();
	G4NistManager* NIST = G4NistManager::Instance();

	// ===============================================
	// 1. World Volume (Galactic Vacuum)
	// ===============================================
	G4Box* solidWorld = new G4Box("World", GEO::WorldSize / 2, GEO::WorldSize / 2, GEO::WorldSize / 2);
	G4LogicalVolume* World_LV = new G4LogicalVolume(solidWorld, NIST->FindOrBuildMaterial("G4_Galactic"), "WorldLV");
	World_Phys = new G4PVPlacement(nullptr, {}, World_LV, "World", nullptr, false, 0, true);

	// ===============================================
	// 2. Source Volume (marker at z = 0 cm)
	// ===============================================
	G4Sphere* solidSource = new G4Sphere("Source", 0, GEO::Source_Radius, 0, 360 * deg, 0, 180 * deg);
	G4LogicalVolume* Source_LV = new G4LogicalVolume(solidSource, NIST->FindOrBuildMaterial("G4_Galactic"), "Source_LV");
	new G4PVPlacement(nullptr, G4ThreeVector(0, 0, 0), Source_LV, "Source", World_LV, false, 0, true);

	// ===============================================
	// 3. Pb Collimator (z = 10 cm to 50 cm, rin = 0.5 cm, rout = 3.0 cm)
	// ===============================================
	G4Tubs* solidCollimator = new G4Tubs("Collimator",
		GEO::Collimator_InnerRadius, GEO::Collimator_OuterRadius,
		GEO::Collimator_Length / 2, 0, 360 * deg);
	G4LogicalVolume* Collimator_LV = new G4LogicalVolume(solidCollimator, NIST->FindOrBuildMaterial("G4_Pb"), "Collimator_LV");
	new G4PVPlacement(nullptr, G4ThreeVector(0, 0, GEO::Collimator_PosZ), Collimator_LV, "Collimator", World_LV, false, 0, true);

	// ===============================================
	// 4. Glass Sample S1 - S8 (front face at z = 50.0 cm, r = 5.0 cm)
	// ===============================================
	G4double sampleThickness = fSample_Thickness;
	if (sampleThickness <= 0.) sampleThickness = 0.001 * mm;

	G4Tubs* solidSample = new G4Tubs("Sample", 0, GEO::Sample_Radius, sampleThickness / 2, 0, 360 * deg);
	G4Material* sampleMat = G4Material::GetMaterial(fSampleMaterial, false);
	if (!sampleMat) {
		G4cerr << "\n*** ERROR: Sample material \"" << fSampleMaterial
			<< "\" not found in DefineMaterials(). Falling back to S1.\n" << G4endl;
		sampleMat = G4Material::GetMaterial("S1");
	}
	G4LogicalVolume* Sample_LV = new G4LogicalVolume(solidSample, sampleMat, "Sample_LV");
	G4double Sample_PosZ = GEO::Sample_ZFront + sampleThickness / 2;
	new G4PVPlacement(nullptr, G4ThreeVector(0, 0, Sample_PosZ), Sample_LV, "Sample", World_LV, false, 0, true);

	// ===============================================
	// 5. Outer Pb Shield (z = 45 cm to 75 cm, rin = 8.0 cm, rout = 10.0 cm)
	// ===============================================
	G4Tubs* solidOuterShield = new G4Tubs("OuterShield",
		GEO::Shield_InnerRadius, GEO::Shield_OuterRadius,
		GEO::Shield_Length / 2, 0, 360 * deg);
	G4LogicalVolume* OuterShield_LV = new G4LogicalVolume(solidOuterShield, NIST->FindOrBuildMaterial("G4_Pb"), "OuterShield_LV");
	new G4PVPlacement(nullptr, G4ThreeVector(0, 0, GEO::Shield_PosZ), OuterShield_LV, "OuterShield", World_LV, false, 0, true);

	// ===============================================
	// 6. Detection Field (z = 70.0 cm to 72.0 cm, r = 5.0 cm, V = 157.0796 cm3)
	// ===============================================
	G4Tubs* solidDetField = new G4Tubs("DetField", 0, GEO::Det_Radius, GEO::Det_Length / 2, 0, 360 * deg);
	G4LogicalVolume* DetField_LV = new G4LogicalVolume(solidDetField, NIST->FindOrBuildMaterial("G4_Galactic"), "DetField_LV");
	G4double DetField_PosZ = (GEO::Det_ZFront + GEO::Det_ZBack) / 2.0;
	// new G4PVPlacement(nullptr, G4ThreeVector(0, 0, DetField_PosZ), DetField_LV, "DetField", World_LV, false, 0, true);


	// ===============================================
	// 6b. Virtual Detector Plane (surface-crossing flux tally at z = 70.0 cm)
	// ===============================================
	G4Tubs* solidDetPlane = new G4Tubs("DetPlane", 0, GEO::DetPlane_Radius, GEO::DetPlane_Thickness / 2, 0, 360 * deg);
	G4LogicalVolume* DetPlane_LV = new G4LogicalVolume(solidDetPlane, NIST->FindOrBuildMaterial("G4_Galactic"), "DetPlane_LV");
	new G4PVPlacement(nullptr, G4ThreeVector(0, 0, GEO::DetPlane_PosZ), DetPlane_LV, "DetPlane", World_LV, false, 0, true);

	// ===============================================
	// VISUALIZATION ATTRIBUTES
	// ===============================================
	// 1. World: invisible
	G4VisAttributes* World_VisAtt = new G4VisAttributes(G4Colour(1, 1, 1, 0.0));
	World_VisAtt->SetVisibility(false);
	World_LV->SetVisAttributes(World_VisAtt);

	// 2. Source: Red
	G4VisAttributes* Source_VisAtt = new G4VisAttributes(G4Colour(1, 0, 0));
	Source_VisAtt->SetForceSolid(true);
	Source_LV->SetVisAttributes(Source_VisAtt);

	// 3. Collimator: Yellow
	G4VisAttributes* Collimator_VisAtt = new G4VisAttributes(G4Colour(1, 1, 0, 0.8));
	Collimator_VisAtt->SetForceSolid(true);
	Collimator_LV->SetVisAttributes(Collimator_VisAtt);

	// 4. Sample: Cyan
	G4VisAttributes* Sample_VisAtt = new G4VisAttributes(G4Colour(0, 1, 1, 0.8));
	Sample_VisAtt->SetForceSolid(true);
	Sample_LV->SetVisAttributes(Sample_VisAtt);

	// 5. Outer Shield: Dark Blue
	G4VisAttributes* Shield_VisAtt = new G4VisAttributes(G4Colour(0.2, 0.3, 0.8, 0.5));
	Shield_VisAtt->SetForceSolid(true);
	OuterShield_LV->SetVisAttributes(Shield_VisAtt);

	// 6. Detection Field: Green wireframe
	G4VisAttributes* DetField_VisAtt = new G4VisAttributes(G4Colour(0, 1, 0, 0.3));
	DetField_VisAtt->SetForceWireframe(true);
	DetField_LV->SetVisAttributes(DetField_VisAtt);

	// 6b. DetPlane: Magenta
	G4VisAttributes* DetPlane_VisAtt = new G4VisAttributes(G4Colour(1, 0, 1));
	DetPlane_VisAtt->SetVisibility(false);
	DetPlane_LV->SetVisAttributes(DetPlane_VisAtt);

	// ===============================================
	// PRODUCTION CUTS (Sample Region)
	// ===============================================
	G4Region* Sample_Region = G4RegionStore::GetInstance()->FindOrCreateRegion("SampleRegion");
	Sample_Region->AddRootLogicalVolume(Sample_LV);
	G4ProductionCuts* sampleCuts = new G4ProductionCuts();
	sampleCuts->SetProductionCut(1 * nm, G4ProductionCuts::GetIndex("gamma"));
	sampleCuts->SetProductionCut(1 * nm, G4ProductionCuts::GetIndex("e-"));
	sampleCuts->SetProductionCut(1 * nm, G4ProductionCuts::GetIndex("e+"));
	Sample_Region->SetProductionCuts(sampleCuts);

	return World_Phys;
}

void MyDetectorConstruction::UpdateGeometry() {
	auto runManager = G4RunManager::GetRunManager();
	runManager->ReinitializeGeometry();         // rebuild geometry
	ConstructSDandField();                      // reattach SDs manually
	// Print updated parameters
	G4cout << "\n================ Updated Geometry (Paper 10.1) ================\n";
	G4cout << " Sample Thickness: " << fSample_Thickness / mm << " mm (" << fSample_Thickness / cm << " cm)\n";
	G4cout << " Sample Material : " << fSampleMaterial << "\n";
	G4cout << " Collimator: z = 10 -> 50 cm, rin = 0.5 cm, rout = 3.0 cm\n";
	G4cout << " Outer Shield: z = 45 -> 75 cm, rin = 8.0 cm, rout = 10.0 cm\n";
	G4cout << " Detection Field: z = 70 -> 72 cm, r = 5.0 cm\n";
	G4cout << "=================================================================\n" << G4endl;
}

// Getters used by MyRunAction
G4String MyDetectorConstruction::GetSampleMaterialName() const {
	return fSampleMaterial;
}

G4double MyDetectorConstruction::GetSampleThickness() const {
	return fSample_Thickness;
}

// =========================================================================
// Construct Sensitive Detectors
// =========================================================================
void MyDetectorConstruction::ConstructSDandField() {
	G4cout << "\n================ ConstructSDandField() =================\n";

	auto sdManager = G4SDManager::GetSDMpointer();
	auto LVS = G4LogicalVolumeStore::GetInstance();

	// DetPlane: surface-crossing flux tally (T-Cross / F2 equivalent)
	G4String SDname = "DetPlane_SD";
	auto DetPlane_Detector = dynamic_cast<MySensitiveDetector*>(sdManager->FindSensitiveDetector(SDname, false));
	if (!DetPlane_Detector) {
		DetPlane_Detector = new MySensitiveDetector(SDname, "DetPlaneHitsCollection");
		sdManager->AddNewDetector(DetPlane_Detector);
	}
	for (auto lv : *LVS) {
		if (lv->GetName() == "DetPlane_LV") {
			lv->SetSensitiveDetector(DetPlane_Detector);
		}
	}

	G4cout << "Attached DetPlane_SD to DetPlane_LV (z = 70 cm, r = 5 cm)" << G4endl;
	G4cout << "========================================================\n\n";
}