# Signal/parameter registry (science and roadmap)

Version 1.0. The collection frequency is instrument- and protocol-specific, not a disease-detection guarantee.

| Source | Parameter | Typical unit/interpretation | Quality/confounders | Stage |
|---|---|---|---|---|
| Browser cognition | Correct response, omission, commission, latency | Accuracy count, milliseconds | Input device, vision, education, language, practice | Toy demo implemented; validation absent |
| Functional report | Daily activity concerns | Structured, time-stamped self/informant response | Context, recall and informant differences | Synthetic cases only |
| Wrist IMU | Acceleration, gyroscope, task tremor power, motion variability | g, rad/s, Hz, derived statistics | Wearing position, dominant hand, medication, physical activity | PADS research script |
| PPG/ECG | Pulse/beat intervals, HR/HRV or PRV | Beats/min, time-domain variability | Motion, ectopy, disease, sampling and vendor processing | Future device integration |
| Consumer sleep | Duration, regularity and interruption proxies | Minutes, sleep timing | Sleep-stage estimates vary by device; RBD requires formal clinical evaluation | Future collection |
| Scalp EEG | Bandpower, event-related responses, entropy, artifact proportion | µV, Hz, normalized features | Electrode contact, montage, movement, sleepiness | EEG research planned |
| Ear EEG | Ear-electrode signals and artifact characteristics | µV, Hz | Sensor placement, limited channels, motion | Future hardware |
| fNIRS | Oxygenated/deoxygenated hemodynamic change | Relative concentration | Scalp hemodynamics, hair, contact, systemic physiology | Future research |
| MRI | eTIV, nWBV, ventricular/hippocampal estimates, QC | Volumes and normalized measurements | Scanner, segmentation, registration, demographics | OASIS scripts, image processing future |
| Retinal OCT | Thickness/layer and vascular measures | µm, device-derived | Eye disease, instrumentation, segmentation | Future specialist input |
| Biomarkers | p-tau, amyloid, relevant disease-specific assays | Assay-specific concentrations | Indication, assay platform, systemic confounding | Future professional integration |
| Oxidative stress | Experimental redox/metabolic lab signals | Assay-specific | Low brain specificity, artifacts, peripheral sources | Long-term analytical validation |

**Rule:** A signal is not a disorder label. For multimodal models, measurements must be linked to the same consented participant at appropriate time intervals; cohort-level statistics cannot be forged into a fictional 'real' multimodal patient.
