package org.bainp.neurosense

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.SystemClock

/** Foreground-only collection component. Host must request runtime permissions,
 * persist batches securely, and stop when its visible recording lifecycle ends.
 * No network upload, diagnosis, sleep estimation or background service implied.
 */
class WatchSensorCollector(context: Context, private val emit: (Sample) -> Unit) : SensorEventListener {
    data class Sample(val type: Int, val sensorName: String, val vendor: String,
        val timestampNs: Long, val estimatedUtcMs: Long, val accuracy: Int,
        val values: List<Float>, val unit: String, val device: String)
    private val manager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private var running = false
    private var anchorUtcMs = 0L
    private var anchorElapsedNs = 0L
    fun capabilities(): List<Int> = listOf(Sensor.TYPE_ACCELEROMETER,
        Sensor.TYPE_GYROSCOPE, Sensor.TYPE_HEART_RATE).filter {
        manager.getDefaultSensor(it) != null
    }
    /** Call only after applicable permission grants; permission failures propagate. */
    fun start(): List<Int> {
        check(!running) { "Already collecting" }
        anchorUtcMs = System.currentTimeMillis()
        anchorElapsedNs = SystemClock.elapsedRealtimeNanos()
        val registered = mutableListOf<Int>()
        try {
            for (type in capabilities()) {
                val sensor = manager.getDefaultSensor(type) ?: continue
                if (manager.registerListener(this, sensor, if (type == Sensor.TYPE_HEART_RATE)
                    SensorManager.SENSOR_DELAY_NORMAL else 20000)) registered.add(type)
            }
            running = true
            return registered
        } catch (e: Exception) { manager.unregisterListener(this); throw e }
    }
    fun stop() { manager.unregisterListener(this); running = false }
    override fun onSensorChanged(event: SensorEvent) {
        if (!running) return
        val unit = when(event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> "m/s2"
            Sensor.TYPE_GYROSCOPE -> "rad/s"
            Sensor.TYPE_HEART_RATE -> "bpm"
            else -> return
        }
        val values = event.values.toList()
        if (values.any { !it.isFinite() }) return
        emit(Sample(event.sensor.type,event.sensor.name,event.sensor.vendor,
            event.timestamp,anchorUtcMs+(event.timestamp-anchorElapsedNs)/1000000,
            event.accuracy,values,unit,Build.MANUFACTURER+" "+Build.MODEL))
    }
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) { }
}
