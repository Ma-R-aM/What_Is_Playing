# What_Is_Playing
Project for Android 7.0+ looking for notifications from selected music platforms and sends information to Discord as a custom status.

How to run:
- installed Android Studio
  
- load this project
  
- change Discord token to your personal Discord token - this should be NOT shared with anyone
    app/src/main/java/martin_svk/whatisplaying/WhatIsPlaying.kt -> private val discordToken = "pasteHereYourDiscordToken"

- if you need/want, change 21. line of WhatIsPlaying.kt -> if (sbn.packageName != "com.metrolist.music" && sbn.packageName != "deezer.android.app") return
    open Logcat and filter name of your Music app. Paste it (for example "deezer.android.app") as you can see above.
  
- connect your Android phone - you have to have debugging mode turned on and also installation using USB
  
- run this project, install it on your mobile phone. After first start you should confirm reading notifications privilege and also consider turning off the battery optimization.
  
- Now this app should work and your Discord status should change based on what you are listening to :3
