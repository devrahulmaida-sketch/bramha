package com.rahul.connect.camera

/**
 * Singleton bus that connects the camera streaming service to the
 * active WebSocket connection (whichever exists).
 */
object CameraStreamBus {
    @Volatile
    var frameSender: ((jpegBase64: String) -> Unit)? = null
}
