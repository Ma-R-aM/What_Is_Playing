package martin_svk.whatisplaying

import android.util.Log
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object DiscordApi {

    private const val TAG = "MusicApp"
    private const val SETTINGS_URL = "https://discord.com/api/v9/users/@me/settings"

    fun update(token: String, statusText: String): Boolean {
        val payload = JSONObject().apply {
            put(
                "custom_status",
                JSONObject().apply {
                    put("text", statusText)
                    put("emoji_name", "🌱")
                }
            )
        }
        return patch(token, payload.toString(), "update")
    }

    fun clear(token: String): Boolean {
        val payload = JSONObject().put("custom_status", JSONObject.NULL)
        return patch(token, payload.toString(), "clear")
    }

    private fun patch(token: String, body: String, action: String): Boolean {
        if (token.isBlank()) {
            Log.w(TAG, "Discord token is not set")
            return false
        }

        var connection: HttpURLConnection? = null
        return try {
            connection = URL(SETTINGS_URL).openConnection() as HttpURLConnection
            connection.requestMethod = "PATCH"
            connection.setRequestProperty("Authorization", token)
            connection.setRequestProperty("Content-Type", "application/json;charset=UTF-8")
            connection.setRequestProperty("Accept", "application/json")
            connection.doOutput = true
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000

            OutputStreamWriter(connection.outputStream, "UTF-8").use { it.write(body) }

            val responseCode = connection.responseCode
            Log.d(TAG, "Discord $action response: $responseCode")

            if (responseCode !in 200..299) {
                val error = connection.errorStream?.bufferedReader()?.use { it.readText() }
                Log.e(TAG, "Discord $action error: $error")
            }

            responseCode in 200..299
        } catch (e: Exception) {
            Log.e(TAG, "Discord $action failed: ${e.message}")
            false
        } finally {
            connection?.disconnect()
        }
    }
}
