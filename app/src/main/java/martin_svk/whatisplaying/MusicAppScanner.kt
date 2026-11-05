package martin_svk.whatisplaying

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.Drawable
import android.os.Build
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap

data class MusicApp(
    val packageName: String,
    val label: String
)

/**
 * Finds installed apps that can play music, so the user can choose which ones
 * should update their Discord status.
 */
object MusicAppScanner {

    /**
     * Well-known players. Some of them do not advertise a media-button receiver
     * or a MediaBrowserService in a way that can be queried, so they are added
     * explicitly when installed.
     */
    private val KNOWN_PLAYERS = setOf(
        "com.metrolist.music",
        "deezer.android.app",
        "com.spotify.music",
        "com.spotify.lite",
        "com.apple.android.music",
        "com.google.android.apps.youtube.music",
        "com.google.android.music",
        "com.amazon.mp3",
        "com.soundcloud.android",
        "com.aspiro.tidal",
        "com.qobuz.music",
        "com.anghami",
        "com.pandora.android",
        "com.kugou.android",
        "com.netease.cloudmusic",
        "com.tencent.qqmusic",
        "com.maxmpz.audioplayer",
        "org.videolan.vlc",
        "com.android.music",
        "com.sec.android.app.music",
        "com.miui.player",
        "com.oppo.music",
        "com.coloros.music",
        "com.oneplus.music"
    )

    private const val MEDIA_BROWSER_SERVICE = "android.media.browse.MediaBrowserService"

    /**
     * Music-player candidates: apps that handle media buttons, expose a media
     * browser service, or are on the known-player list.
     */
    fun detectPlayers(context: Context): List<MusicApp> {
        val pm = context.packageManager
        val packages = linkedSetOf<String>()

        runCatching {
            @Suppress("DEPRECATION")
            pm.queryBroadcastReceivers(Intent(Intent.ACTION_MEDIA_BUTTON), 0)
                .forEach { info -> info.activityInfo?.packageName?.let(packages::add) }
        }

        runCatching {
            @Suppress("DEPRECATION")
            pm.queryIntentServices(Intent(MEDIA_BROWSER_SERVICE), 0)
                .forEach { info -> info.serviceInfo?.packageName?.let(packages::add) }
        }

        KNOWN_PLAYERS.forEach { packageName ->
            if (isInstalled(pm, packageName)) packages.add(packageName)
        }

        packages.remove(context.packageName)

        return packages
            .mapNotNull { packageName -> toMusicApp(pm, packageName) }
            .sortedBy { it.label.lowercase() }
    }

    /**
     * Every launchable app on the device, so a player that was not detected can
     * still be picked manually.
     */
    fun allLaunchableApps(context: Context): List<MusicApp> {
        val pm = context.packageManager
        val apps = installedApplications(pm)
            .asSequence()
            .filter { it.packageName != context.packageName }
            .filter { pm.getLaunchIntentForPackage(it.packageName) != null }
            .mapNotNull { info -> toMusicApp(pm, info.packageName) }
            .sortedBy { it.label.lowercase() }
            .toList()

        return apps
    }

    private fun isInstalled(pm: PackageManager, packageName: String): Boolean =
        runCatching { applicationInfo(pm, packageName) != null }.getOrDefault(false)

    private fun toMusicApp(pm: PackageManager, packageName: String): MusicApp? {
        val info = applicationInfo(pm, packageName) ?: return null
        val label = runCatching { pm.getApplicationLabel(info).toString() }
            .getOrDefault(packageName)
        return MusicApp(packageName = packageName, label = label)
    }

    private fun applicationInfo(pm: PackageManager, packageName: String): ApplicationInfo? =
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getApplicationInfo(
                    packageName,
                    PackageManager.ApplicationInfoFlags.of(0)
                )
            } else {
                @Suppress("DEPRECATION")
                pm.getApplicationInfo(packageName, 0)
            }
        }.getOrNull()

    private fun installedApplications(pm: PackageManager): List<ApplicationInfo> =
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getInstalledApplications(PackageManager.ApplicationInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                pm.getInstalledApplications(0)
            }
        }.getOrDefault(emptyList())
}

/**
 * Renders a package icon into a Compose-friendly bitmap.
 */
fun Drawable.toImageBitmap(sizePx: Int): ImageBitmap {
    val bitmap = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    setBounds(0, 0, sizePx, sizePx)
    draw(canvas)
    return bitmap.asImageBitmap()
}
