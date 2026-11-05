package martin_svk.whatisplaying

import android.content.Context
import android.content.SharedPreferences

object AppPreferences {

    private const val PREFS_NAME = "whatisplaying_prefs"
    const val KEY_ENABLED = "discord_enabled"
    const val KEY_SELECTED_PACKAGES = "selected_player_packages"
    private const val KEY_TOKEN = "discord_token"

    /**
     * Packages that are watched before the user opens the app for the first
     * time. Once the user saves a selection, that selection is used instead.
     */
    val DEFAULT_PACKAGES = setOf(
        "com.metrolist.music",
        "deezer.android.app",
        "com.spotify.music",
        "com.apple.android.music",
        "com.google.android.apps.youtube.music",
        "com.google.android.music",
        "com.amazon.mp3",
        "com.soundcloud.android"
    )

    fun prefs(context: Context): SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun isEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_ENABLED, true)

    fun setEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_ENABLED, enabled).apply()
    }

    fun getToken(context: Context): String =
        prefs(context).getString(KEY_TOKEN, "").orEmpty().trim()

    fun setToken(context: Context, token: String) {
        prefs(context).edit().putString(KEY_TOKEN, token.trim()).apply()
    }

    fun hasExplicitPackageSelection(context: Context): Boolean =
        prefs(context).contains(KEY_SELECTED_PACKAGES)

    fun getSelectedPackages(context: Context): Set<String> =
        prefs(context)
            .getStringSet(KEY_SELECTED_PACKAGES, null)
            ?.toSet()
            ?: DEFAULT_PACKAGES

    fun setSelectedPackages(context: Context, packages: Set<String>) {
        prefs(context).edit()
            .putStringSet(KEY_SELECTED_PACKAGES, packages.toSet())
            .apply()
    }

    fun isPackageSelected(context: Context, packageName: String): Boolean =
        packageName in getSelectedPackages(context)
}
