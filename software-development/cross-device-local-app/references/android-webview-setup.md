# Android Studio WebView Setup Guide

Guide for creating clean, zero-maintenance Android Studio WebView projects that connect to local LAN servers.

## 1. Project Structure
```
TaskFlowApp/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle/
│   ├── libs.versions.toml
│   └── wrapper/
│       ├── gradle-wrapper.jar
│       └── gradle-wrapper.properties
└── app/
    ├── build.gradle.kts
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/com/<package>/MainActivity.kt
        └── res/
            ├── layout/activity_main.xml
            └── values/strings.xml
```

## 2. AndroidManifest.xml Permissions
Crucial attributes for local HTTP communication:
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:theme="@style/Theme.Material3.DayNight.NoActionBar"
        android:usesCleartextTraffic="true">
        
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:windowSoftInputMode="adjustResize"
            android:configChanges="orientation|screenSize|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

## 3. WebView Settings in Kotlin
Configure DOM storage, hardware acceleration, and audio autoplay:
```kotlin
val settings: WebSettings = webView.settings
settings.javaScriptEnabled = true
settings.domStorageEnabled = true
settings.loadWithOverviewMode = true
settings.useWideViewPort = true
settings.cacheMode = WebSettings.LOAD_DEFAULT
settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
// Allow audio/TTS playback from asynchronous network callbacks without requiring direct user tap
settings.mediaPlaybackRequiresUserGesture = false
```

## 4. Dynamic IP Handling with SharedPreferences & Legacy Migration
Avoid hardcoding inflexible LAN addresses. When running backend on-device (Termux), use loopback `http://127.0.0.1:8000` (prefer raw IPv4 over `localhost`). When running on PC, use Tailscale CGNAT IPs (`100.x.y.z:port`) or Wi-Fi LAN IPs:
```kotlin
private val PREFS_NAME = "AppPrefs"
private val KEY_SERVER_URL = "server_url"
// Default to on-device server (Termux) or host PC IP
private val DEFAULT_SERVER_URL = "http://127.0.0.1:8000"

private fun initServerUrl() {
    val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    val saved = prefs.getString(KEY_SERVER_URL, null)
    // Auto-migrate stale host laptop IPs when switching to on-device Termux execution
    currentServerUrl = if (saved == null || saved.contains("100.89.") || saved.contains("192.168.")) {
        prefs.edit().putString(KEY_SERVER_URL, DEFAULT_SERVER_URL).apply()
        DEFAULT_SERVER_URL
    } else {
        saved
    }
    webView.loadUrl(currentServerUrl)
}

private fun showChangeIpDialog() {
    val input = EditText(this).apply {
        setText(currentServerUrl)
        hint = "http://127.0.0.1:8000"
    }
    AlertDialog.Builder(this)
        .setTitle("Ubah Alamat Server")
        .setMessage("Default lokal HP (Termux): http://127.0.0.1:8000\nAtau dari PC: http://100.x.y.z:8000")
        .setView(input)
        .setPositiveButton("Simpan & Hubungkan") { _, _ ->
            var newUrl = input.text.toString().trim()
            if (newUrl.isNotEmpty()) {
                if (!newUrl.startsWith("http://") && !newUrl.startsWith("https://")) {
                    newUrl = "http://$newUrl"
                }
                currentServerUrl = newUrl
                val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                prefs.edit().putString(KEY_SERVER_URL, currentServerUrl).apply()
                webView.loadUrl(currentServerUrl)
            }
        }
        .setNeutralButton("Reset ke Lokal HP") { _, _ ->
            currentServerUrl = DEFAULT_SERVER_URL
            val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().putString(KEY_SERVER_URL, currentServerUrl).apply()
            webView.loadUrl(currentServerUrl)
        }
        .setNegativeButton("Batal", null)
        .show()
}
```

## 5. Building from Terminal via Bundled JBR
If Java is not in the shell PATH, invoke Gradle using Android Studio's bundled JBR.
On Windows MSYS/Git-Bash, `JAVA_HOME` must be passed as a native Windows path (not `/c/...`) because `gradlew.bat` executes via Windows command interpreter:
```bash
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
export ANDROID_HOME='C:\Users\User\AppData\Local\Android\Sdk'
./gradlew.bat assembleDebug
```
Ensure `local.properties` exists with `sdk.dir=C\:\\Users\\<user>\\AppData\\Local\\Android\\Sdk`.
The built APK lands at `app/build/outputs/apk/debug/app-debug.apk`.

## 6. App Icon Customization & AAPT2 Duplicate Resource Pitfall
When replacing default Android app icons with custom branding/character art across density folders (`mipmap-mdpi`, `hdpi`, `xhdpi`, `xxhdpi`, `xxxhdpi`):
- **Delete existing WebP files before generating PNGs (and vice-versa)**: Android's AAPT2 asset merger refuses duplicate resource basenames in the same density bucket. Having both `ic_launcher.png` and `ic_launcher.webp` in `mipmap-hdpi/` immediately crashes `packageDebugResources` with `Error: Duplicate resources`.
- **Remove or update `mipmap-anydpi-v26/`**: Android 8+ (API 26+) prioritizes XML adaptive icons under `mipmap-anydpi-v26/` over bitmap drawables. If default template XML files (`ic_launcher.xml` referencing boilerplate background/foreground) remain, the custom icon will not display on modern Android launchers. Delete `mipmap-anydpi-v26/` or update its foreground drawable to use the new art.

## 7. Microphone & Audio Recording Permissions
When embedding web pages that record audio via browser WebRTC (`navigator.mediaDevices.getUserMedia`):
1. Add permissions in `AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
```
2. Request runtime permission in `onCreate`:
```kotlin
if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
    ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 101)
}
```
3. Grant permission to WebView inside `WebChromeClient`:
```kotlin
webView.webChromeClient = object : WebChromeClient() {
    override fun onPermissionRequest(request: PermissionRequest?) {
        runOnUiThread {
            request?.grant(request.resources)
        }
    }
}
```
If `onPermissionRequest` is omitted, the web browser instance inside the WebView will silently deny the microphone stream without prompting or logging an error.

## 8. Mobile File Downloads & The Blob URL Trap
- **The Android Blob Scheme Failure**: Generating `blob:` URLs in JavaScript via `URL.createObjectURL(blob)` and triggering `<a href="blob:..." download="...">` fails silently in Android WebViews. Android `setDownloadListener` and `DownloadManager` discard non-HTTP/HTTPS URLs.
- **Direct HTTP Attachment Endpoints**: Serve download files from endpoints returning `Content-Disposition: attachment; filename="..."`.
- **Universal JavaScript Trigger Pattern**:
```javascript
function triggerUniversalDownload(url, filename) {
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", filename);
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { try { document.body.removeChild(a); } catch(e){} }, 400);

    // Fallback for Android WebView to invoke setDownloadListener
    if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
        setTimeout(() => { window.location.href = url; }, 200);
    }
}
```
- **Instant Messenger Bridge Delivery**: For media files (screenshots, camera photos), offer a direct WhatsApp bridge trigger (`/api/laptop/send_media_to_wa`) that delivers the full-resolution image straight into the user's mobile WhatsApp chat within 500ms, completely bypassing mobile filesystem downloads.
