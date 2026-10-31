package martin_svk.whatisplaying

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import martin_svk.whatisplaying.ui.theme.WhatIsPlayingTheme
import kotlin.concurrent.thread

class MainActivity : ComponentActivity() {

    private val notificationAccessGranted = mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        notificationAccessGranted.value = isNotificationServiceEnabled()

        setContent {
            WhatIsPlayingTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    SettingsScreen(
                        notificationAccessGranted = notificationAccessGranted.value,
                        onOpenNotificationSettings = ::openNotificationSettings,
                        onRefreshNotificationAccess = {
                            notificationAccessGranted.value = isNotificationServiceEnabled()
                        }
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        notificationAccessGranted.value = isNotificationServiceEnabled()
    }

    private fun openNotificationSettings() {
        startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
    }

    private fun isNotificationServiceEnabled(): Boolean {
        val flat = Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
        return flat != null && flat.contains(packageName)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsScreen(
    notificationAccessGranted: Boolean,
    onOpenNotificationSettings: () -> Unit,
    onRefreshNotificationAccess: () -> Unit
) {
    val context = LocalContext.current
    var enabled by rememberSaveable { mutableStateOf(AppPreferences.isEnabled(context)) }
    var token by rememberSaveable { mutableStateOf(AppPreferences.getToken(context)) }
    var savedToken by rememberSaveable { mutableStateOf(AppPreferences.getToken(context)) }
    var tokenVisible by rememberSaveable { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("WhatIsPlaying", fontWeight = FontWeight.SemiBold) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(start = 20.dp, top = 8.dp, end = 20.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            IntroCard()

            StatusCard(
                enabled = enabled,
                tokenConfigured = savedToken.isNotBlank(),
                notificationAccessGranted = notificationAccessGranted,
                onEnabledChange = { checked ->
                    enabled = checked
                    AppPreferences.setEnabled(context, checked)

                    if (!checked) {
                        val savedToken = AppPreferences.getToken(context)
                        if (savedToken.isNotBlank()) {
                            thread { DiscordApi.clear(savedToken) }
                        }
                    }
                },
                onOpenNotificationSettings = onOpenNotificationSettings,
                onRefreshNotificationAccess = onRefreshNotificationAccess
            )

            TokenCard(
                token = token,
                tokenVisible = tokenVisible,
                onTokenChange = { token = it },
                onToggleVisibility = { tokenVisible = !tokenVisible },
                onSave = {
                    AppPreferences.setToken(context, token)
                    savedToken = AppPreferences.getToken(context)
                    Toast.makeText(context, "Discord token saved", Toast.LENGTH_SHORT).show()
                }
            )

            InfoCard()
        }
    }
}

@Composable
private fun IntroCard() {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        ),
        shape = RoundedCornerShape(24.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(
                text = "Your music, on Discord",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "Metrolist and Deezer notifications are turned into a Discord custom status.",
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}

@Composable
private fun StatusCard(
    enabled: Boolean,
    tokenConfigured: Boolean,
    notificationAccessGranted: Boolean,
    onEnabledChange: (Boolean) -> Unit,
    onOpenNotificationSettings: () -> Unit,
    onRefreshNotificationAccess: () -> Unit
) {
    Card(shape = RoundedCornerShape(20.dp)) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = "Send to Discord",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = if (enabled) {
                            "Now playing will be shared as your custom status."
                        } else {
                            "Sending is turned off. Your Discord status is left alone."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Spacer(Modifier.width(12.dp))

                Switch(
                    checked = enabled,
                    onCheckedChange = onEnabledChange
                )
            }

            HorizontalDivider()

            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .background(
                            color = if (notificationAccessGranted) {
                                Color(0xFF22C55E)
                            } else {
                                Color(0xFFF59E0B)
                            },
                            shape = CircleShape
                        )
                )

                Spacer(Modifier.width(10.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = if (notificationAccessGranted) {
                            "Notification access granted"
                        } else {
                            "Notification access needed"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = if (notificationAccessGranted) {
                            "WhatIsPlaying can read media notifications."
                        } else {
                            "Allow notification access so the app can see what is playing."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            if (notificationAccessGranted) {
                TextButton(
                    onClick = onRefreshNotificationAccess,
                    modifier = Modifier.align(Alignment.End)
                ) {
                    Text("Check again")
                }
            } else {
                Button(onClick = onOpenNotificationSettings) {
                    Text("Open notification access")
                }
            }

            if (enabled && !tokenConfigured) {
                Text(
                    text = "Add your Discord token below to start sending.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
private fun TokenCard(
    token: String,
    tokenVisible: Boolean,
    onTokenChange: (String) -> Unit,
    onToggleVisibility: () -> Unit,
    onSave: () -> Unit
) {
    Card(shape = RoundedCornerShape(20.dp)) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Discord token",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "Used to update your own Discord custom status. It is stored only on this device.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            OutlinedTextField(
                value = token,
                onValueChange = onTokenChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Token") },
                placeholder = { Text("Paste your Discord token") },
                singleLine = true,
                visualTransformation = if (tokenVisible) {
                    VisualTransformation.None
                } else {
                    PasswordVisualTransformation()
                },
                trailingIcon = {
                    TextButton(onClick = onToggleVisibility) {
                        Text(if (tokenVisible) "Hide" else "Show")
                    }
                }
            )

            Button(
                onClick = onSave,
                modifier = Modifier.align(Alignment.End)
            ) {
                Text("Save token")
            }
        }
    }
}

@Composable
private fun InfoCard() {
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "What it does",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            InfoLine("Works with Metrolist and Deezer notifications.")
            InfoLine("Removes play counts like \"1,3 tis. prehraní\" from artist names.")
            InfoLine("Adds a random cute kaomoji to every status.")
            InfoLine("Clears the status when playback is paused and restores it when you continue.")
        }
    }
}

@Composable
private fun InfoLine(text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = "•",
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
