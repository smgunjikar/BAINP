# NeuroVision imaging workspace v1

## Installed structure
backend/engine.py: read-only NIfTI preparation, native volumetry, display resampling, coarse label-boundary meshes, upstream OASIS artifact verification.
backend/router.py: authenticated catalog/package/comparison API using the existing BAINP operator session.
frontend/: three orthogonal slice viewers, overlay opacity, contrast, drag/zoom mesh, measurements, QC, comparison and provenance.
tests/verify_engine.py: isolated synthetic engine/API tests.

## Run environments and data
Prepare images in bainp-brain (NumPy, SciPy, nibabel, scikit-image). Serve through the existing bainp NeuroAccess API/frontend; the web API only needs standard-library modules plus existing FastAPI.
Prepared packages live outside Git at BAINP_DATA/derived/neurovision/v1 (override NEUROVISION_DATA_DIR consistently for engine and API). Original research files remain untouched. There is no upload endpoint, arbitrary-path read endpoint or automatic mapping to live participants.

Default preparation imports ONE completed OASIS acquisition from derived/oasis2/experimental_batch_v1. Change --limit to 0 to prepare all 407 acquisitions. Preparing all increases storage and initial catalog size; no segmentation is rerun. Input, mask and labels must match upstream completion-manifest hashes. Use --review-csv with the user-reviewed acquisition_qc.csv to preserve explicit session/acquisition review status. The historical flags remain visible. No clinical approval is inferred.

## Generic authorized NIfTI / ADNI route
engine.py image --image T1.nii.gz --mask brainmask.nii.gz --labels segmentation.nii.gz --metadata scan_metadata.json --lut label_names.json --out OUTPUT

Required metadata: cohort, subject, visit, protocol, pipeline, review, synthetic.
Optional: date (YYYY-MM-DD), longitudinal_comparable (boolean; must be explicitly true for real comparisons).
Optional LUT is a JSON object mapping integer labels to anatomical names from the actual upstream atlas, e.g. {"17":"Left hippocampus"} ONLY when label 17 really denotes that structure in the selected atlas. No generic anatomical mapping is invented.
Native images and overlays must be finite 3D, in millimeters, with matching affine and shape. Label IDs currently 0..255. DICOM conversion, registration, cortical-thickness estimation and anatomical segmentation must be performed by a suitable separately verified pipeline. This engine consumes those outputs rather than fabricating them.

## Measurement meaning
Volumes use absolute determinant of the native affine and native voxel counts. Display images are separately resampled with interpolation (intensity linear; labels nearest neighbor) to a physical RAS+ cardinal grid. Native intensity data are never overwritten. Image labels follow neurological convention. Header orientation still needs independent anatomical review.
Meshes are downsampled mask/class boundaries. They are not validated cortical surfaces, a biological replica or a cortical-thickness measurement. Experimental Atropos intensity classes are NOT anatomical regions or validated CSF/GM/WM compartments.

No automatic MRI artifact detector, disease diagnosis, pathology evidence, cortical thickness, diffusion connectome or clinical forecast is included. The code exposes technical checks and upstream QC status. Existing OASIS data contain one selected session per subject in this batch: repeated acquisitions are not longitudinal visits.

## Comparisons
Active differences require same cohort/subject/protocol/pipeline, distinct visits, ordered verified dates, explicit comparability, approved review and no unreviewed automated flags. Side-by-side images use header coordinates and DO NOT establish longitudinal registration. Percentage differences are descriptive, not annualized atrophy or reliable change. Scanner/protocol/tissue-label sensitivity and segmentation error must be considered in a validated longitudinal workflow.

## Demo and security
Demo is an explicitly labelled mathematical phantom, never a human scan. Active research and demo catalogs are separate. API access requires the current operator login; it is local prototype authentication, not a multi-user clinical access-control system. Prepared packages contain research imaging and should be kept outside Git. Native raw paths are not exposed by the API.

## Verification performed during development
Synthetic: native anisotropic-volume calculation, left/right affine handling, RAS display, overlay-mismatch rejection, auth/mode isolation, package tamper detection, comparison gates. Simulated DOM: catalog, slice/overlay controls, 3D mesh render, comparison handlers. Full browser rendering and local Windows/OASIS preparation remain to be verified on the user's machine.

## Next scientific work
Choose and validate an atlas-based anatomical segmentation pipeline, or import authorized versioned ADNI regional measurements with verified column dictionaries and units. Build a longitudinal registration workflow from genuinely repeated matched visits. Disease-specific modeling follows participant-held-out evaluation and external validation, not a single MRI inspection.

References:
https://nipy.org/nibabel/reference/nibabel.funcs.html
https://nipy.org/nibabel/reference/nibabel.orientations.html
https://scikit-image.org/docs/stable/api/skimage.measure.html

# V2 upgrade
- GPU/WebGL2 MRI intensity volume rendering: actual prepared MRI data, optional
  brain mask, threshold, superior cutaway, rotation and zoom. Requires WebGL2;
  fallback slice and mesh viewers remain available if unsupported.
- Brain mask surface is now first. Meshes use native grids with a small
  display-only smoothing, shared physical center, and sampled MRI intensity.
  All quantitative volumes remain unsmoothed native voxel counts.
- Native-grid voxel counts and fractions of the provided mask are shown.
  Mask fraction is not intracranial-volume normalization or a normative score.
- Compare visits now explains missing follow-up instead of leaving blank controls.
  Baseline axial image is visible even without a follow-up. Multiple people or
  acquisitions in one visit never imply disease detection or longitudinal data.
- OASIS preparation selects one acquisition per visit by default; limit 8 gives
  broader subject coverage. --all-acquisitions allows repeat acquisitions.
- Repreparing the same image replaces its old catalog entry (old packages remain
  archived on disk), avoiding duplicate viewer versions.
- Import-NeuroVision.ps1 allows authorized local 3D NIfTI imports and a local
  dcm2niix conversion workflow for DICOM series. A user selects the specific
  converted series. No web-based arbitrary filesystem access is added.
- Use --mask, --labels and --lut only for anatomically aligned upstream outputs.
- No generic analysis of every MRI modality: viewing and numerical checks do not
  establish a modality-specific segmentation, diffusion/fMRI analysis or diagnosis.

V2 verification: synthetic native-volume, mask-first mesh, mask-volume payload,
mode/auth boundaries, package integrity, same-visit rejection and catalog-version
replacement tests pass. Simulated DOM exercises slices, surface fallback and
comparison. MRI volume GLSL shaders compile/link in Mesa OpenGL ES 3. Actual
Windows/WebGL2 browser rendering and DICOM conversion remain untested.
