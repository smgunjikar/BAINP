# NeuroVision V2 repair

Binary mask byte values 0/1 are expanded to 0/255 before normalized R8 GPU upload. Prepared packages stay unchanged. Renderer validates nonempty mask length and resets threshold/cutaway when a new scan is selected.

Evidence is now a structured summary plus a downloadable JSON report. Raw hashes remain in the technical disclosure.

Active research NIfTI uploads are bounded to 64 MB and processed locally by a separate single-owner worker in bainp-brain. The operator session, explicit authorization, research subject/visit metadata and API request header are required. No paths supplied by a browser are used as server paths. Raw uploaded files and errors are retained outside Git under import_jobs for provenance. One upload creates one immutable source and a job; five pending jobs are allowed. The worker verifies source hashes, finite 3D geometry and the bounded voxel count, and publishes the prepared package. No anatomical segmentation is invented without upstream masks/labels. Demo cannot ingest real scans.

Start-NeuroVision-Worker.ps1 must run with bainp-brain. Worker locks are OS-held and released on process exit. Its heartbeat supports visible availability status. Interrupted processing is retried when a new exclusive worker starts. Closing the browser does not stop queued processing. If the queue is blocked by abandoned pending imports, inspect the local job files before removing any authorized data. The local companion remains available for DICOM and larger images.

Verified: actual OpenGL ES shader mask regression, existing-auth API queue validation, upload limit/cleanup and duplicate protection, synthetic processing/catalog publication, JavaScript syntax, simulated DOM evidence and download handlers. Windows browser execution, Windows worker startup and actual user MRI uploads still need local verification.
