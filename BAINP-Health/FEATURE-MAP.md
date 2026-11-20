# Requested image features and implementation status

Seven images inspected; three were HEIF files with PNG extensions and were decoded for review. No personal values or images from the screenshots are bundled or imported.

| Reference | Feature | Status in this update |
|---|---|---|
| IMG_6942 | Account identity | Existing authenticated account; My health link added |
| IMG_6942 / IMG_6943 | Health details | Optional date of birth, sex, height and weight, saved privately |
| IMG_6943 / IMG_6946 | Pregnancy | Optional free-text notes, no pregnancy calculations |
| IMG_6942 | Move goal | Saved self-selected kcal/day goal; no tracking computation |
| IMG_6942 | Units | Preference note; explicit cm/kg inputs, no conversion yet |
| IMG_6946 | Medical ID | Private medications/allergies/conditions/emergency-contact notes |
| IMG_6946 | Show when locked | Unavailable; no unauthenticated health-record access added |
| IMG_6947 | Health checklist | Capability checklist on My health; no fake device-status detection |
| IMG_6947 | Emergency SOS | Unavailable; app does not call or message emergency services |
| IMG_6947 | Crash detection | Unavailable; requires native supported sensors and validation |
| IMG_6947 / IMG_6949 | Walking steadiness alerts | Unavailable; no detector or notification delivery |
| IMG_6949 | Trend notifications | Unavailable; no validated trend pipeline or background delivery |
| IMG_6949 | Sleep/medication/BP/mood notifications | Time preferences stored only; scheduling/delivery pending |
| IMG_6950 | Privacy: apps/devices | Explicit connection status; no connectors added |
| IMG_6950 | Research studies | Existing journey permissions linked; study recruitment/enrolment not implemented |
| IMG_6950 | Export all health data | Only new health-details record export implemented; all-module export pending |
| IMG_6950 | iCloud sync/encryption | Not implemented; no Apple privacy claims copied |
| IMG_6955 | Health-data cards | Self-reported details only; existing monitoring link; measured activity/energy charts pending data integration |
| IMG_6942 | Workout / Fitness+ / GymKit | No native integration or proprietary subscription content |
| IMG_6942 | Gift cards / redemption | Not implemented; needs an actual commerce and entitlement system |

This is a partial implementation of the requested image features, not a complete Apple Health/Fitness equivalent. Next engineering dependencies: unified observation schema and source provenance; device/native integrations; notification scheduler and delivery; complete permission-scoped export; protocol-reviewed accessibility metadata; production privacy/security review. Do not treat interface settings as evidence that these services exist.
