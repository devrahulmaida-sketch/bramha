package com.rahul.connect.camera

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import android.util.Base64
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * Streams the back camera as base64-JPEG `camera_frame` messages to the PC
 * (~10 fps, 640px long edge) while Rahul AI's holographic viewer is open.
 */
class CameraStreamService : Service(), LifecycleOwner {

    private val lifecycleRegistry = LifecycleRegistry(this)
    override val lifecycle: Lifecycle get() = lifecycleRegistry

    private var cameraProvider: ProcessCameraProvider? = null
    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private var lastSentAt = 0L

    override fun onCreate() {
        super.onCreate()
        lifecycleRegistry.handleEvent(Lifecycle.Event.ON_CREATE)
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopStreaming()
                return START_NOT_STICKY
            }
        }
        val notification = buildNotification()
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (security: SecurityException) {
            stopSelf()
            return START_NOT_STICKY
        }
        startCamera()
        return START_STICKY
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                val provider = future.get()
                cameraProvider = provider
                lifecycleRegistry.handleEvent(Lifecycle.Event.ON_START)
                lifecycleRegistry.handleEvent(Lifecycle.Event.ON_RESUME)

                val analysis = ImageAnalysis.Builder()
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                analysis.setAnalyzer(analysisExecutor, ::analyzeFrame)

                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, Preview.Builder().build(), analysis)
            } catch (t: Throwable) {
                stopSelf()
            }
        }, androidx.core.content.ContextCompat.getMainExecutor(this))
    }

    private fun analyzeFrame(proxy: ImageProxy) {
        try {
            val now = SystemClock.elapsedRealtime()
            if (now - lastSentAt >= FRAME_INTERVAL_MS) {
                lastSentAt = now
                val buffer = proxy.planes[0].buffer
                val width = proxy.width
                val height = proxy.height
                val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                bitmap.copyPixelsFromBuffer(buffer)

                val maxEdge = 640
                val scale = minOf(maxEdge.toFloat() / width, maxEdge.toFloat() / height, 1f)
                val out = if (scale < 1f) {
                    val w = (width * scale).toInt().coerceAtLeast(1)
                    val h = (height * scale).toInt().coerceAtLeast(1)
                    Bitmap.createScaledBitmap(bitmap, w, h, true)
                } else bitmap

                val jpeg = ByteArrayOutputStream()
                out.compress(Bitmap.CompressFormat.JPEG, 55, jpeg)
                val b64 = Base64.encodeToString(jpeg.toByteArray(), Base64.NO_WRAP)
                CameraStreamBus.frameSender?.invoke(b64)
                if (out !== bitmap) out.recycle()
                bitmap.recycle()
            }
        } catch (t: Throwable) {
            // drop frame
        } finally {
            proxy.close()
        }
    }

    private fun stopStreaming() {
        try {
            cameraProvider?.unbindAll()
        } catch (t: Throwable) {
        }
        lifecycleRegistry.handleEvent(Lifecycle.Event.ON_PAUSE)
        lifecycleRegistry.handleEvent(Lifecycle.Event.ON_STOP)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        try {
            cameraProvider?.unbindAll()
        } catch (t: Throwable) {
        }
        analysisExecutor.shutdown()
        lifecycleRegistry.handleEvent(Lifecycle.Event.ON_DESTROY)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(com.rahul.connect.R.drawable.ic_rahul_launcher)
            .setContentTitle("Rahul Connect")
            .setContentText("Camera streaming to Rahul AI…")
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Camera Stream", NotificationManager.IMPORTANCE_LOW)
        )
    }

    companion object {
        const val ACTION_START = "com.rahul.connect.camera.START"
        const val ACTION_STOP = "com.rahul.connect.camera.STOP"
        private const val CHANNEL_ID = "rahul_camera"
        private const val NOTIFICATION_ID = 4202
        private const val FRAME_INTERVAL_MS = 100L
    }
}
