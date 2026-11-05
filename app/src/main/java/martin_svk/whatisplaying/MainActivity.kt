package martin_svk.whatisplaying

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
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

    var players by remember { mutableStateOf<List<MusicApp>>(emptyList()) }
    var allApps by remember { mutableStateOf<List<MusicApp>>(emptyList()) }
    var appsLoaded by remember { mutableStateOf(false) }
    var selectedPackages by remember {
        mutableStateOf(AppPreferences.getSelectedPackages(context))
    }
    var showAllApps by rememberSaveable { mutableStateOf(false) }

    fun saveSelection(newSelection: Set<String>) {
        selectedPackages = newSelection
        AppPreferences.setSelectedPackages(context, newSelection)
    }

    LaunchedEffect(Unit) {
        val (detected, installed) = withContext(Dispatchers.IO) {
            MusicAppScanner.detectPlayers(context) to MusicAppScanner.allLaunchableApps(context)
        }
        players = detected
        allApps = installed

        // First run: watch every detected player by default.
        if (!AppPreferences.hasExplicitPackageSelection(context) && detected.isNotEmpty()) {
            saveSelection(detected.map { it.packageName }.toSet())
        }
        appsLoaded = true
    }

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

            PlayerAppsCard(
                apps = players,
                loaded = appsLoaded,
                selected = selectedPackages,
                onToggle = { packageName, checked ->
                    saveSelection(
                        if (checked) {
                            selectedPackages + packageName
                        } else {
                            selectedPackages - packageName
                        }
                    )
                },
                onSelectAll = {
                    saveSelection(selectedPackages + players.map { it.packageName })
                },
                onClear = { saveSelection(emptySet()) },
                onBrowseAll = { showAllApps = true }
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
        }
    }

    if (showAllApps) {
        AllAppsDialog(
            apps = allApps,
            selected = selectedPackages,
            onToggle = { packageName, checked ->
                saveSelection(
                    if (checked) {
                        selectedPackages + packageName
                    } else {
                        selectedPackages - packageName
                    }
                )
            },
            onDismiss = { showAllApps = false }
        )
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
                text = "Pick the music apps on your phone and share what you are listening to as a Discord custom status.",
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
private fun PlayerAppsCard(
    apps: List<MusicApp>,
    loaded: Boolean,
    selected: Set<String>,
    onToggle: (String, Boolean) -> Unit,
    onSelectAll: () -> Unit,
    onClear: () -> Unit,
    onBrowseAll: () -> Unit
) {
    Card(shape = RoundedCornerShape(20.dp)) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "Music apps",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = "Only selected apps can update your Discord status.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(
                    text = "${selected.size} selected",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }

            HorizontalDivider()

            when {
                !loaded -> Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp
                    )
                    Spacer(Modifier.width(12.dp))
                    Text(
                        text = "Looking for installed players…",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                apps.isEmpty() -> Text(
                    text = "No music players were detected. Browse all installed apps to pick one manually.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                else -> Column {
                    apps.forEach { app ->
                        AppRow(
                            app = app,
                            checked = app.packageName in selected,
                            onToggle = onToggle
                        )
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(
                    onClick = onSelectAll,
                    enabled = apps.isNotEmpty()
                ) {
                    Text("Select all")
                }
                TextButton(
                    onClick = onClear,
                    enabled = selected.isNotEmpty()
                ) {
                    Text("Clear")
                }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onBrowseAll) {
                    Text("Browse all")
                }
            }

            if (selected.isEmpty()) {
                Text(
                    text = "No apps selected — your Discord status will not be updated.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
private fun AllAppsDialog(
    apps: List<MusicApp>,
    selected: Set<String>,
    onToggle: (String, Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    val filtered = remember(apps, query) {
        val search = query.trim()
        if (search.isEmpty()) {
            apps
        } else {
            apps.filter {
                it.label.contains(search, ignoreCase = true) ||
                    it.packageName.contains(search, ignoreCase = true)
            }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("All installed apps") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Search") },
                    singleLine = true
                )

                if (filtered.isEmpty()) {
                    Text(
                        text = "No apps found.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    LazyColumn(modifier = Modifier.heightIn(max = 400.dp)) {
                        items(filtered, key = { it.packageName }) { app ->
                            AppRow(
                                app = app,
                                checked = app.packageName in selected,
                                onToggle = onToggle
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Done")
            }
        }
    )
}

@Composable
private fun AppRow(
    app: MusicApp,
    checked: Boolean,
    onToggle: (String, Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onToggle(app.packageName, !checked) }
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        AppIcon(packageName = app.packageName)

        Spacer(Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = app.label,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium
            )
            Text(
                text = app.packageName,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Checkbox(
            checked = checked,
            onCheckedChange = { onToggle(app.packageName, it) }
        )
    }
}

@Composable
private fun AppIcon(packageName: String) {
    val context = LocalContext.current
    val icon by produceState<ImageBitmap?>(initialValue = null, packageName) {
        value = withContext(Dispatchers.IO) {
            runCatching {
                context.packageManager
                    .getApplicationIcon(packageName)
                    .toImageBitmap(96)
            }.getOrNull()
        }
    }

    val bitmap = icon
    if (bitmap != null) {
        Image(
            bitmap = bitmap,
            contentDescription = null,
            modifier = Modifier.size(36.dp)
        )
    } else {
        Box(
            modifier = Modifier
                .size(36.dp)
                .background(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(8.dp)
                )
        )
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
