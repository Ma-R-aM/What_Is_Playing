package martin_svk.whatisplaying
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import kotlin.concurrent.thread
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class WhatIsPlaying : NotificationListenerService(){

    private var lastTrack = ""
    private val discordToken = "pasteHereYourDiscordToken"

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)

        if(sbn == null) return


        if (sbn.packageName != "com.metrolist.music" && sbn.packageName != "deezer.android.app") return //the name of your music application, get from Logcat

        val extras = sbn.notification.extras

        val title = extras.getCharSequence("android.title")?.toString()
        val artist = extras.getCharSequence("android.text")?.toString()

        if (title == null || artist == null) {
            clearDiscordStatus()
            return
        }

        if (title == "Prehrávač hudby" || title.contains("Metrolist", ignoreCase = true)) {
            return
        }

        var cleanedTitle = title.replace(Regex("\\(spolu s[^)]*\\)"), "").trim()
        cleanedTitle = cleanedTitle.replace(Regex("\\(with[^)]*\\)"), "").trim()

        val currentTrack = "$cleanedTitle - $artist"
        if(currentTrack == lastTrack) return

        lastTrack = currentTrack
        Log.d("MusicApp", "send to DC: $currentTrack")

        thread {
            updateDiscordStatus(cleanedTitle, artist)
        }
    }




    private fun updateDiscordStatus(title: String, artist: String) {
        try{

            val catEmoji = "(=^•ω•^=)"
            var statusText = "$title | $artist $catEmoji"
            if(statusText.length > 125)
                statusText = statusText.substring(0,122) + "..."


            val url = URL("https://discord.com/api/v9/users/@me/settings")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "PATCH"
            connection.setRequestProperty("Authorization", discordToken)
            connection.setRequestProperty("Content-Type", "application/json;charset=UTF-8")
            connection.setRequestProperty("Accept", "application/json")
            connection.doOutput = true

            val jsonBody = """
                {
                  "custom_status": {
                    "text": ${escapeJsonString(statusText)},
                    "emoji_name": "🌱"
                  }
                }
            """.trimIndent()

            val os = OutputStreamWriter(connection.outputStream, "UTF-8")
            os.write(jsonBody)
            os.flush()
            os.close()

            val responseCode = connection.responseCode
            Log.d("MusicApp", "DC API response: $responseCode")

            if (responseCode !in 200..299) {
                val errorString = connection.errorStream?.bufferedReader()?.use { it.readText() }
                Log.e("MusicApp", "DC error message: $errorString")
            }

            connection.disconnect()
        } catch (e: Exception) {
            Log.e("MusicApp", "Error sending update: ${e.message}")
        }
        }
    private fun clearDiscordStatus(){
        lastTrack = ""

        thread {
            try {
                val url = URL("https://discord.com/api/v9/users/@me/settings")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "PATCH"
                connection.setRequestProperty("Authorization", discordToken)
                connection.setRequestProperty("Content-Type", "application/json;charset=UTF-8")
                connection.doOutput = true

                val jsonBody = """
                    {
                      "custom_status": null
                    }
                """.trimIndent()

                val os = OutputStreamWriter(connection.outputStream, "UTF-8")
                os.write(jsonBody)
                os.flush()
                os.close()

                Log.d("MusicApp", "DC API remove status code: ${connection.responseCode}")
                connection.disconnect()
            } catch (e: Exception) {
                Log.e("MusicApp", "Delete status error: ${e.message}")
            }
        }
    }


    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        super.onNotificationRemoved(sbn)
        if (sbn?.packageName == "com.metrolist.music") {
            Log.d("MusicApp", "No notification")
            clearDiscordStatus()
        }
    }

    override fun onDestroy() {
        Log.e("MusicApp", "Shutdown")
        clearDiscordStatus()
        super.onDestroy()
    }

    private fun escapeJsonString(text: String): String {
        val escaped = text
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        return "\"$escaped\""
    }


}