package martin_svk.whatisplaying

import android.app.Notification
import android.content.ComponentName
import android.content.Context
import android.content.SharedPreferences
import android.media.AudioManager
import android.media.session.MediaController
import android.media.session.MediaSession
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import java.util.concurrent.Executors

class WhatIsPlaying : NotificationListenerService() {

    companion object {
        private const val TAG = "MusicApp"
        private const val MAX_STATUS_LENGTH = 128
        private const val PLAYBACK_CHECK_INTERVAL_MS = 5_000L

        private val KAOMOJIS = listOf(
            "(=^•ω•^=)",
            "(=^･ω･^=)",
            "(=ↀωↀ=)",
            "(=^ ◡ ^=)",
            "(^・ω・^ )",
            "(｡•̀ᴗ-)✧",
            "(๑>ᴗ<๑)",
            "(≧◡≦)",
            "(づ｡◕‿‿◕｡)づ",
            "(´｡• ᵕ •｡`)",
            "(˶ᵔ ᵕ ᵔ˶)",
            "(｡･ω･｡)",
            "(„• ᴗ •„)",
            "(✿◠‿◠)",
            "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
            "(๑•́ ₃ •̀๑)",
            "(≧ω≦)",
            "(＾▽＾)",
            "(⌒‿⌒)",
            "(๑˃ᴗ˂)ﻭ",
            "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
            "(｡>﹏<｡)",
            "(´･ω･`)",
            "(・∀・)",
            "(◕ᴗ◕✿)",
            "(ᵔᴥᵔ)",
            "(ฅ^•ﻌ•^ฅ)",
            "(｡•ω•｡)",
            "(っ˘ω˘ς)",
            "(๑´ω`๑)",
            "(o^▽^o)",
            "(✧ω✧)",
            "(ﾉ´ヮ`)ﾉ*: ･ﾟ",
            "( ˘ ³˘)♥",
            "(๑•᎑•๑)"
        )
    }

    private val handler = Handler(Looper.getMainLooper())
    private val networkExecutor = Executors.newSingleThreadExecutor()

    private var lastTitle = ""
    private var lastArtist = ""
    private var lastTrackKey = ""
    private var lastPackage = ""
    private var lastSessionToken: MediaSession.Token? = null
    private var statusShown = false

    private val prefsListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        when (key) {
            AppPreferences.KEY_ENABLED -> {
                if (AppPreferences.isEnabled(this)) {
                    refreshFromActiveNotifications()
                } else {
                    stopPlaybackWatcher()
                    forgetTrack()
                    clearDiscordStatus()
                }
            }

            AppPreferences.KEY_SELECTED_PACKAGES -> {
                if (!AppPreferences.isEnabled(this)) return@OnSharedPreferenceChangeListener

                if (lastPackage.isNotEmpty() && !isSelectedPackage(lastPackage)) {
                    stopPlaybackWatcher()
                    forgetTrack()
                    clearDiscordStatus()
                } else {
                    refreshFromActiveNotifications()
                }
            }
        }
    }

    private val playbackWatcher = object : Runnable {
        override fun run() {
            checkPlaybackState()
            if (lastTitle.isNotEmpty() && AppPreferences.isEnabled(this@WhatIsPlaying)) {
                handler.postDelayed(this, PLAYBACK_CHECK_INTERVAL_MS)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        AppPreferences.prefs(this).registerOnSharedPreferenceChangeListener(prefsListener)
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        if (AppPreferences.isEnabled(this)) {
            refreshFromActiveNotifications()
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return
        if (!isSelectedPackage(sbn.packageName)) return

        if (!AppPreferences.isEnabled(this)) {
            stopPlaybackWatcher()
            forgetTrack()
            clearDiscordStatus()
            return
        }

        val sessionToken = mediaSessionToken(sbn)
        if (sbn.notification.category != Notification.CATEGORY_TRANSPORT && sessionToken == null) {
            return
        }

        val extras = sbn.notification.extras
        val rawTitle = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim()
        val rawArtist = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()?.trim()

        if (rawTitle.isNullOrBlank() || rawArtist.isNullOrBlank()) {
            // Other selected players may keep a silent/persistent notification
            // around. Only clear the status if it belongs to this app.
            if (lastPackage.isEmpty() || lastPackage == sbn.packageName) {
                forgetTrack()
                clearDiscordStatus()
            }
            return
        }

        if (TrackInfoParser.isPlayerNotification(rawTitle)) {
            return
        }

        val title = TrackInfoParser.cleanTitle(rawTitle).ifBlank { rawTitle }
        val artist = TrackInfoParser.cleanArtist(rawArtist).ifBlank { rawArtist }
        val trackKey = "$title - $artist"
        val trackChanged = trackKey != lastTrackKey

        lastTitle = title
        lastArtist = artist
        lastTrackKey = trackKey
        lastPackage = sbn.packageName
        lastSessionToken = sessionToken

        if (isPlaybackPaused(sbn, sessionToken)) {
            clearDiscordStatus()
        } else if (!statusShown || trackChanged) {
            sendStatus(title, artist)
        }

        startPlaybackWatcher()
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        super.onNotificationRemoved(sbn)
        if (sbn != null && isSelectedPackage(sbn.packageName) && sbn.packageName == lastPackage) {
            Log.d(TAG, "Music notification removed")
            stopPlaybackWatcher()
            forgetTrack()
            clearDiscordStatus()
        }
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        stopPlaybackWatcher()
        forgetTrack()
        clearDiscordStatus()
    }

    override fun onDestroy() {
        Log.d(TAG, "Shutdown")
        handler.removeCallbacks(playbackWatcher)
        AppPreferences.prefs(this).unregisterOnSharedPreferenceChangeListener(prefsListener)
        forgetTrack()
        clearDiscordStatus()
        networkExecutor.shutdown()
        super.onDestroy()
    }

    private fun sendStatus(title: String, artist: String) {
        val token = AppPreferences.getToken(this)
        if (token.isBlank()) {
            Log.w(TAG, "Discord token is not set")
            return
        }

        val status = buildStatus(title, artist)
        statusShown = true
        Log.d(TAG, "send to DC: $status")

        networkExecutor.execute {
            DiscordApi.update(token, status)
        }
    }

    private fun clearDiscordStatus() {
        if (!statusShown) return
        statusShown = false

        val token = AppPreferences.getToken(this)
        if (token.isBlank()) {
            Log.w(TAG, "Discord token is not set; cannot clear status")
            return
        }

        networkExecutor.execute {
            DiscordApi.clear(token)
        }
    }

    private fun buildStatus(title: String, artist: String): String {
        val kaomoji = KAOMOJIS.random()
        val suffix = " $kaomoji"
        val maxBodyLength = MAX_STATUS_LENGTH - suffix.codePointCount(0, suffix.length)

        var body = "$title | $artist"
        if (body.codePointCount(0, body.length) > maxBodyLength) {
            body = truncateCodePoints(body, (maxBodyLength - 3).coerceAtLeast(0)) + "..."
        }

        return body + suffix
    }

    private fun truncateCodePoints(text: String, maxCodePoints: Int): String {
        if (maxCodePoints <= 0) return ""
        if (text.codePointCount(0, text.length) <= maxCodePoints) return text
        return text.substring(0, text.offsetByCodePoints(0, maxCodePoints))
    }

    private fun checkPlaybackState() {
        if (!AppPreferences.isEnabled(this)) {
            stopPlaybackWatcher()
            forgetTrack()
            clearDiscordStatus()
            return
        }

        if (lastTitle.isEmpty()) {
            stopPlaybackWatcher()
            return
        }

        val state = currentPlaybackState()
        when {
            isPausedState(state) -> clearDiscordStatus()
            state != null && !statusShown -> sendStatus(lastTitle, lastArtist)
        }
    }

    private fun currentPlaybackState(): Int? =
        stateFromToken(lastSessionToken) ?: stateFromActiveSessions(lastPackage)

    private fun isPlaybackPaused(
        sbn: StatusBarNotification,
        sessionToken: MediaSession.Token?
    ): Boolean {
        val state = stateFromToken(sessionToken) ?: stateFromActiveSessions(sbn.packageName)
        if (state != null) return isPausedState(state)
        return !isMusicActive()
    }

    private fun stateFromToken(token: MediaSession.Token?): Int? {
        if (token == null) return null

        return try {
            val controller = MediaController(this, token)
            controller.playbackState?.state
        } catch (e: Exception) {
            Log.w(TAG, "MediaController from notification failed: ${e.message}")
            null
        }
    }

    private fun stateFromActiveSessions(packageName: String): Int? {
        if (packageName.isEmpty()) return null

        return try {
            val manager = getSystemService(Context.MEDIA_SESSION_SERVICE) as MediaSessionManager
            val component = ComponentName(this, WhatIsPlaying::class.java)
            manager.getActiveSessions(component)
                .firstOrNull { it.packageName == packageName }
                ?.playbackState?.state
        } catch (e: Exception) {
            Log.w(TAG, "getActiveSessions failed: ${e.message}")
            null
        }
    }

    private fun mediaSessionToken(sbn: StatusBarNotification): MediaSession.Token? {
        val extras = sbn.notification.extras
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                extras.getParcelable(Notification.EXTRA_MEDIA_SESSION, MediaSession.Token::class.java)
            } else {
                @Suppress("DEPRECATION")
                extras.getParcelable(Notification.EXTRA_MEDIA_SESSION)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Media session token unavailable: ${e.message}")
            null
        }
    }

    private fun isMusicActive(): Boolean {
        return try {
            val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audioManager.isMusicActive
        } catch (e: Exception) {
            false
        }
    }

    private fun isPausedState(state: Int?): Boolean =
        state == PlaybackState.STATE_PAUSED ||
            state == PlaybackState.STATE_STOPPED ||
            state == PlaybackState.STATE_NONE

    private fun startPlaybackWatcher() {
        handler.removeCallbacks(playbackWatcher)
        handler.postDelayed(playbackWatcher, PLAYBACK_CHECK_INTERVAL_MS)
    }

    private fun stopPlaybackWatcher() {
        handler.removeCallbacks(playbackWatcher)
    }

    private fun isSelectedPackage(packageName: String): Boolean =
        AppPreferences.isPackageSelected(this, packageName)

    private fun refreshFromActiveNotifications() {
        if (!AppPreferences.isEnabled(this)) return

        try {
            activeNotifications?.forEach { onNotificationPosted(it) }
        } catch (e: Exception) {
            Log.w(TAG, "Refreshing active notifications failed: ${e.message}")
        }
    }

    private fun forgetTrack() {
        lastTitle = ""
        lastArtist = ""
        lastTrackKey = ""
        lastPackage = ""
        lastSessionToken = null
    }
}
