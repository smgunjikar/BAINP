# Future real-time NeuroPulse acquisition

Design: EEG/ear-EEG via qualified hardware + MNE-LSL or BrainFlow; ECG/PPG, motion and sleep via authorized vendor SDKs. Record source, timestamps, sampling rate, device, montage, reference scheme, artifacts and measurement context. Synchronize clinically relevant streams with timebase validation.

ECG and EEG measure electrical potentials from different organs. Wrist PPG/IMU cannot substitute for EEG; no validated consumer wearable measures brain oxidative stress or universally predicts neurological disease.

Hardware is *not* integrated into this release. Implement recorded EEG replay first, clearly labeled as replay; production live acquisition and clinical prediction require separate development and validation.
