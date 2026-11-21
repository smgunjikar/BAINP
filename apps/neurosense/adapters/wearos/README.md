# Deferred Samsung/Wear OS integration
Status: source component only; not a built application or tested connection.

WatchSensorCollector.kt uses Android SensorManager for available acceleration,
gyroscope and heart-rate sensors. Requested motion interval is 20 ms, not a
sampling guarantee. Acceleration includes gravity and is in m/s2, whereas PADS
uses g: never silently reuse PADS preprocessing or models.

Host requirements before testing:
- Confirm exact watch model and Wear OS/API version. Older Tizen models are not Wear OS.
- Use an Android Studio Wear OS project; integrate this Kotlin component in its
  visible recording lifecycle. stop() on lifecycle exit. No background collection yet.
- Declare/request applicable sensor permissions. Android 16+ uses granular health
  permissions; earlier releases use BODY_SENSORS for heart rate. Check current
  Android documentation against the actual target SDK.
- Preserve sensor monotonic timestamps, UTC anchor, sensor accuracy and device metadata.
- Add encrypted durable queue, explicit participant pairing, expiring/revocable
  credentials and authenticated TLS transport before any synchronization.
- Existing BAINP server binds to loopback; never expose it to Wi-Fi without
  implementing pairing, authentication, TLS and network-boundary changes.
- No wearable credentials or operator secret should be embedded in an APK.
- Sleep history needs a separate authorized health-data adapter. ECG and raw PPG
  require model-specific Samsung SDK capability checks and access requirements.
- Evaluate signal gaps, clock changes, background suspension, denied/revoked
  permissions, sensor accuracy and battery use on hardware after submission.

No SDK binary is bundled; no build tooling or proprietary API is guessed.
Official references:
https://developer.samsung.com/health/sensor/guide/introduction.html
https://developer.samsung.com/health/sensor/guide/environment.html
https://developer.android.com/health-and-fitness/health-services/permissions

Next: native host, durable queue, secure pairing/ingestion, then hardware tests.
