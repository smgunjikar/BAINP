NeuroSense dashboard v2

backend/: authenticated observation router and experimental change engine.
frontend/: connected-monitoring interface.
Active: existing stored observations, five-second dashboard polling. No live adapter installed.
Demo: explicitly simulated stream, not persisted.
Database remains the existing NeuroAccess SQLite store, with participant cascade deletion.
Device adapters/mobile companions are not implemented.
