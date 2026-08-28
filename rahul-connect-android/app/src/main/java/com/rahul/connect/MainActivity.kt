package com.rahul.connect

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.rahul.connect.core.AgentStateStore
import com.rahul.connect.pairing.PairingStorage
import com.rahul.connect.ui.RahulConnectApp
import com.rahul.connect.ui.theme.RahulConnectTheme

class MainActivity : ComponentActivity() {
    private lateinit var storage: PairingStorage
    private var pendingServiceStart = false

    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { _ ->
        // The UI will react by showing the scanner if permission is granted.
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted || Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            if (pendingServiceStart) {
                pendingServiceStart = false
                startGatewayService()
            }
        } else {
            pendingServiceStart = false
            AgentStateStore.setError("Notification permission is required for Rahul Connect.")
            AgentStateStore.setStatus("Notification permission denied")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        storage = PairingStorage(this)
        AgentStateStore.setCredential(storage.loadCredential())
        storage.loadGatewayHint()?.let {
            AgentStateStore.setPairingOffer(it)
            AgentStateStore.setGateway(
                com.rahul.connect.core.GatewayEndpoint(
                    name = "Rahul PC",
                    host = it.host,
                    port = it.port,
                )
            )
        }
        maybeStartService()
        ensureCameraPermission()
        setContent {
            RahulConnectTheme {
                RahulConnectApp(
                    onRequestCameraPermission = {
                        cameraPermission.launch(Manifest.permission.CAMERA)
                    },
                    onRequestNotificationPermission = {
                        notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    },
                    onStartService = { maybeStartService() },
                )
            }
        }
    }

    private fun maybeStartService() {
        val endpoint = AgentStateStore.gateway.value
        if (endpoint != null || AgentStateStore.credential.value != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) {
                pendingServiceStart = true
                notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                return
            }
            startGatewayService()
        }
    }

    private fun ensureCameraPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            cameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startGatewayService() {
        val endpoint = AgentStateStore.gateway.value
        if (endpoint != null || AgentStateStore.credential.value != null) {
            val intent = Intent(this, RahulConnectForegroundService::class.java)
            ContextCompat.startForegroundService(this, intent)
        }
    }
}
