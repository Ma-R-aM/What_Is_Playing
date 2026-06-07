# What Is Playing
Project for Android 7.0+ that looks for notifications from selected music platforms and sends the information to Discord as a custom status.

## How to run:

- Install Android Studio
- Load this project
- Change the Discord token to your personal Discord token (do NOT share this with anyone):
    app/src/main/java/martin_svk/whatisplaying/WhatIsPlaying.kt -> private val discordToken = "pasteHereYourDiscordToken"
- If needed, change line 21 of WhatIsPlaying.kt -> if (sbn.packageName != "com.metrolist.music" && sbn.packageName != "deezer.android.app") return
    Open Logcat, find your music app's package name, and paste it as shown above.
- Connect your Android phone (enable USB debugging and install via USB)
- Run the project and install it on your phone. On first launch, confirm the notification listener permission and consider disabling battery optimization.
- The app should now work — your Discord status will change based on what you're listening to :3
