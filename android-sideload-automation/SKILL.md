---
name: android-sideload-automation
version: 1.4.0
author: Ferdinand Manurung
license: MIT
description: Use when sideloading APKs and fixing restricted settings.
metadata:
  hermes:
    tags: [android, adb, sideload, permissions, xos, restricted-settings]
    related_skills: [mobile-payment-automation, cross-device-local-sync]
---

# Android Sideload Operations & Restricted Settings Bypass

Comprehensive operational workflow for installing, updating, and authorizing sideloaded Android applications (Android 13 through 15, Transsion XOS, Xiaomi HyperOS, Oppo ColorOS, Samsung OneUI) with sensitive permissions (Notification Listener, Accessibility, Device Admin, Battery Whitelist).

## When to Use
- Sideloaded APK has permissions blocked with "Dikontrol oleh Setelan Terbatas" (*Controlled by Restricted Settings*).
- Granting `NotificationListenerService` or `AccessibilityService` without requiring Google Play Store distribution.
- Managing USB Debugging authorization states (`unauthorized` to `device`).
- Streamed in-place APK updates without data wipes.
- Whitelisting background daemons against aggressive OEM battery cleaners.

---

## 1. Android Sideload Security Architecture (Android 13+)

### The "Restricted Settings" (Setelan Terbatas) Guard
Starting in Android 13, applications installed outside authorized app stores (sideloaded via browser download, WhatsApp, USB, or file managers) receive restricted appops flags. Android disables sensitive permission switches in Settings and marks them with:
`"Dikontrol oleh Setelan Terbatas"` (*Controlled by Restricted Settings*).

This restriction blocks:
- **Notification Access** (`NotificationListenerService`)
- **Accessibility Services** (`AccessibilityService`)
- **Device Admin** (`DeviceAdminReceiver`)

---

## 2. Automated Bypass via ADB (USB Debugging)

When the phone is connected to a PC via USB:

### Step 1: Resolve Authorization State
Run ADB detection:
```bash
adb devices
```
- **If output shows `<serial> unauthorized`**:
  The Android kernel rejects shell commands until the host RSA key is trusted. Instruct the user:
  1. Unlock the phone screen.
  2. In the "Izinkan proses debug USB?" (*Allow USB debugging?*) dialog, check "Selalu izinkan dari komputer ini" (*Always allow from this computer*).
  3. Tap **Izinkan** (*Allow*).
  If the prompt does not appear, change USB mode from "Charging only" to "File Transfer / MTP" or toggle USB Debugging off and on in Developer Options.

### Step 2: Unlock Restricted Settings
Once status shows `<serial> device`, remove the sideload appops block:
```bash
adb shell appops set <package_name> ACCESS_RESTRICTED_SETTINGS allow
```

### Step 3: Directly Grant Listener & Runtime Permissions
Grant sensitive permissions without requiring manual navigation through system settings:
```bash
# 1. Grant Notification Listener Service:
adb shell cmd notification allow_listener <package_name>/<service_class_name>

# 2. Grant POST_NOTIFICATIONS (Android 13+):
adb shell pm grant <package_name> android.permission.POST_NOTIFICATIONS

# 3. Grant READ_MEDIA_AUDIO (Android 13+ Media / Music apps):
adb shell pm grant <package_name> android.permission.READ_MEDIA_AUDIO
```

### Step 4: Whitelist Background Battery Optimization
Prevent aggressive OEM process killers (Infinix XOS, Xiaomi HyperOS, Samsung OneUI) from terminating services when the screen locks:
```bash
adb shell dumpsys deviceidle whitelist +<package_name>
```

### Step 5: Verify Active System Binding
Never run `cmd notification get_listeners` (which fails with `Unknown command: get_listeners`). Use:
```bash
# Verify string registration:
adb shell settings get secure enabled_notification_listeners

# Verify active IPC binder connection:
adb shell dumpsys notification | grep -i <package_name>
# Must output: ComponentInfo{<package>/<service>} : INotificationListener$Stub$Proxy

# Verify battery whitelist:
adb shell dumpsys deviceidle whitelist | grep -i <package_name>
```

### Step 6: Streamed In-Place Update & Launch
Install newer APK revisions without uninstalling or wiping user SQLite/SharedPreferences data:
```bash
adb install -r <path_to_apk>

# Direct launch using the exact exported activity:
adb shell am start -n <package_name>/<launcher_activity_class>

# Fallback when exact activity class is unknown:
adb shell monkey -p <package_name> -c android.intent.category.LAUNCHER 1
```

### Step 7: Internal Sandbox File & Database Injection (`run-as`)
Direct push to `/data/data/<package_name>/` fails with `Permission denied` even under USB debugging. To update local JSON libraries, Room DBs, or SharedPreferences without rooting:
```bash
# 1. Push payload to world-readable staging area:
adb push <local_file> /data/local/tmp/<target_name>

# 2. Copy into app internal sandbox using package UID:
adb shell "run-as <package_name> cp /data/local/tmp/<target_name> files/<target_name>"

# 3. Force stop and relaunch to reload memory cache:
adb shell am force-stop <package_name>
adb shell am start -n <package_name>/<launcher_activity_class>
```

---

## 3. Manual Device-Only Bypass (No PC / No Cable)

When ADB is unavailable, guide the user through the 2-step OS settings bypass:
1. Long-press the app icon on the home screen -> Tap **Detail Aplikasi** (*App Info* / `(i)` icon).
2. Tap the **three dots (⋮)** in the top-right corner.
3. Tap **"Izinkan setelan terbatas"** (*Allow restricted settings*).
4. Authenticate with device PIN, pattern, or fingerprint.
5. Return to the permission screen (*Device & app notifications*) -> the toggle is now active and clickable.

---

## 4. Media Playback, MediaSession & Audio Architecture (Android 11–15)

### Android Quick Settings Media Controls & MediaSessionCompat
Starting in Android 11 (API 30) through Android 15, the System Media Player carousel in Quick Settings and Lockscreen does not rely solely on standard notification action intents. It communicates exclusively via `MediaSessionCompat`:
- **State Synchronization (`setPlaybackState`)**: Always dispatch `mediaSession.setPlaybackState(...)` on every state transition (`STATE_PLAYING`, `STATE_PAUSED`, `STATE_BUFFERING`, `STATE_STOPPED`, `seekTo`). Specify supported actions (`ACTION_PLAY | ACTION_PAUSE | ACTION_PLAY_PAUSE | ACTION_SKIP_TO_NEXT | ACTION_SKIP_TO_PREVIOUS | ACTION_STOP | ACTION_SEEK_TO`). Omitting `setPlaybackState` leaves the player in `STATE_NONE`, breaking play/pause buttons and timeline seekers on system widgets.
- **Metadata Broadcast (`setMetadata`)**: Always dispatch `mediaSession.setMetadata(...)` using `MediaMetadataCompat.Builder()` with `METADATA_KEY_TITLE`, `METADATA_KEY_ARTIST`, `METADATA_KEY_ALBUM`, and `METADATA_KEY_DURATION` so OS lockscreen cards render metadata without scraping notification strings.
- **PendingIntent Restrictions (Android 12+)**: Never use `PendingIntent.getService(..., ACTION_TOGGLE)` for media notification buttons. Calling `getService` when backgrounded throws `ForegroundServiceStartNotAllowedException`. Use `MediaButtonReceiver.buildMediaButtonPendingIntent(this, PlaybackStateCompat.ACTION_...)`, declare `<receiver android:name="androidx.media.session.MediaButtonReceiver" android:exported="true">` in `AndroidManifest.xml`, and delegate `MediaButtonReceiver.handleIntent(mediaSession, intent)` in `onStartCommand()`.

### AudioFocus & Transient Interruption Guard (WA Status / Calls / Reels)
In `AudioManager.OnAudioFocusChangeListener`, never blindly trigger `AUDIOFOCUS_GAIN -> play()`.
- **The Bug**: When a user explicitly pauses audio, subsequent transient focus events from other apps (watching a WhatsApp video status, Instagram reel, phone ring) trigger `AUDIOFOCUS_LOSS_TRANSIENT`, followed by `AUDIOFOCUS_GAIN` when the external media ends. A naive `AUDIOFOCUS_GAIN -> play()` spontaneously unpauses and blasts audio even though the user paused it minutes or hours earlier.
- **The Guard Rule**: Maintain a boolean `resumeOnFocusGain = false`. Whenever the user explicitly calls `pause()` or `stop()`, reset `resumeOnFocusGain = false`. On `AUDIOFOCUS_LOSS_TRANSIENT` or `AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK`, set `resumeOnFocusGain = true` ONLY IF `isPlaying == true` at that moment. On `AUDIOFOCUS_GAIN`, only call `play()` if `resumeOnFocusGain == true`, then reset the flag to `false`.

---

## 5. Common Pitfalls & Diagnostic Checks

- **The `unauthorized` Loop**: Do not loop adb shell commands when status is `unauthorized`. Shell commands fail with `device unauthorized`. Wait for screen unlock and user RSA confirmation.
- **Service Name FQCN Requirement**: `cmd notification allow_listener` requires the full class name (`com.example.app/com.example.app.service.MyListenerService`). Passing only the package name silently fails.
- **`pm grant` Non-Changeable Permission Type**: Running `adb shell pm grant <pkg> <permission>` on permissions with `normal` protection level (e.g., `MODIFY_AUDIO_SETTINGS`, `INTERNET`, `WAKE_LOCK`) fails with `SecurityException: Permission ... is not a changeable permission type`. Only `dangerous` runtime permissions (e.g. `POST_NOTIFICATIONS`, `READ_MEDIA_AUDIO`) can and need to be granted via `pm grant`; normal permissions are granted automatically by Android at install time.
- **JVM Unit Tests on Android `org.json` Classes**: Running unit tests (`./gradlew testDebugUnitTest`) on data models using `org.json.JSONObject` or `JSONArray` fails with `NullPointerException` because Android SDK stubs in `android.jar` return null for framework classes on the host JVM. Add `testImplementation("org.json:json:20240303")` to `build.gradle.kts` dependencies so unit tests use the real JVM JSON library instead of Android SDK stubs.
- **Activity Component Resolution (`am start` vs `monkey`)**: `monkey -p <pkg> 1` injects raw UI events and may launch unwanted intermediate activities or misfire on splash screens. Inspect `AndroidManifest.xml` for the activity with `android.intent.action.MAIN` and target it explicitly using `adb shell am start -n <package>/<activity>`.
- **Horizontal LinearLayout Squeezing**: In native companion apps with multiple toolbar action buttons, never combine multiple `wrap_content` buttons with a `weight="1"` title container without setting compact padding (`minWidth="0dp"`, `paddingHorizontal="6dp"`), or Android compresses the title vertically character-by-character.
- **Bottom Navigation Bar Insets Squashing**: Never apply `bars.bottom` as `paddingBottom` to a bottom navigation view with a fixed `layout_height` (e.g. `layout_height="56dp"`). Fixed height causes the bottom system inset (~48dp for 3-button navigation) to consume the view's internal space, collapsing child tabs into near-zero height and clipping icons and text. Always expand the total height dynamically (`navParams.height = baseNavHeight + bars.bottom`) or set `layout_height="wrap_content"` with `minHeight="58dp"`.
- **MaterialButton Multi-Line Text Clipping & Outlines**: In weighted horizontal button groups, never place long labels with parenthetical text (e.g., `(Needs)` or `(Wants)`). The button wraps text to line 2, and constrained container heights (`32dp-40dp`) slice off the second line vertically, creating the visual illusion of "double lines" or random dashes underneath. Use single-line labels (`maxLines="1"`, `singleLine="true"`). Furthermore, never call `setBackgroundColor()` on a styled MaterialButton; it destroys the internal `MaterialShapeDrawable` while preserving stroke insets. Use `backgroundTintList = ColorStateList.valueOf(...)` and set `strokeWidth = 0`.
- **Vector Brand Logo Tinting**: In `MaterialButton`, always set `iconTint = null` when displaying multi-color branded vector icons (e.g., SeaBank, ShopeePay, GoPay, DANA). Omitting this or leaving default tints causes Android to override brand vectors into a flat monochrome silhouette.
- **Headless Screencap on Keyguard / AOD**: On Android 10-15 (especially Transsion XOS, HyperOS, OneUI), running `screencap -p` on a locked/dozing phone yields a ~16KB black screen showing only the AOD clock. In test/debug builds, add `setShowWhenLocked(true)` and `setTurnScreenOn(true)` to `onCreate()` of the launcher activity. Then send `adb shell input keyevent KEYCODE_WAKEUP` before `screencap` to capture full-resolution in-app UI without requiring manual PIN unlock.
- **compileSdk 37 / Android 15 `onNewIntent` Signature Change**: In Android 15 / compileSdk 37, `override fun onNewIntent(intent: Intent)` takes a non-nullable `Intent` parameter. Declaring `override fun onNewIntent(intent: Intent?)` causes compilation failure with `'onNewIntent' overrides nothing`.
- **HTML Tag Leaks in TextViews**: When rendering scripture, receipts, or notification snippets containing markup (e.g. `<b>Gal 5:18</b>`), assigning directly via `textView.text = rawString` renders literal unparsed HTML tags. Format through `Html.fromHtml(rawString.replace("\n", "<br/>"), Html.FROM_HTML_MODE_LEGACY)` so bold tags and styling render natively.
- **Notification Source App Importance Diagnostic**: If an authorized `NotificationListenerService` fails to receive events from a specific e-wallet or bank app, inspect `adb shell dumpsys notification`. If the source package has `importance=NONE`, notifications for that app are muted or disabled in Android system settings. Unblock with `adb shell pm grant <pkg> android.permission.POST_NOTIFICATIONS`.
- **IME Keyboard Overlap with WindowInsets**: When applying `ViewCompat.setOnApplyWindowInsetsListener` to a root layout, omitting `WindowInsetsCompat.Type.ime()` and applying only `navBar.bottom` suppresses default `adjustResize`, causing the soft keyboard to cover bottom input bars (`EditText` and send buttons). Always check `val ime = insets.getInsets(WindowInsetsCompat.Type.ime())`. When `ime.bottom > 0`, hide fixed bottom navigation bars (`bottomNav.visibility = View.GONE`) and set bottom padding to `ime.bottom`. Restore `bottomNav.visibility = View.VISIBLE` and `navBar.bottom` padding when `ime.bottom == 0`.
- **ADB UI Automator Keyboard Coordinate Shift**: In automated UI tests, typing text into an `EditText` via `adb shell input text` causes the virtual keyboard to pop up and shift bottom-anchored action buttons upward. Blindly sending an `input tap` to pre-keyboard coordinates clicks underneath the keyboard into background layers or system navigation. Always re-dump the UI hierarchy (`adb shell uiautomator dump /data/local/tmp/uidump.xml`) after input events to resolve the shifted component bounds, or submit forms using `adb shell input keyevent 66` (KEYCODE_ENTER).
- **Transient Overlay Window Focus Theft**: Automated ADB test runs can be hijacked when system reminders or background app popups steal focus. Always verify foreground window ownership via `adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'` before injecting touch events. Dismiss interfering alert windows with `adb shell input keyevent 4` (KEYCODE_BACK) or force-stop conflicting background daemons (`am force-stop <pkg>`).
- **ADB String Extras Word Splitting in `am start`**: When launching activities with multi-word string extras via `adb shell am start ... --es <key> "hello world"`, bash word-splitting fragments the arguments unless the entire shell command is enclosed in single quotes (`adb shell 'am start -n <pkg>/.<activity> --es <key> "hello world"'`). If the target activity is already active, ensure `--es` arguments are handled in `onNewIntent(intent: Intent)` as `onCreate()` will not re-execute.
- **Mobile Multi-Turn AI Context Integrity Guard**: In conversational assistant apps, never append network failure or timeout messages into the in-memory `conversationHistory` list when an AI endpoint call fails. If a request throws, immediately pop the unfulfilled user message from history; otherwise, subsequent contextual commands (e.g. "singkatkan poin intinya", "jelaskan lagi") instruct the LLM to process and summarize the error message rather than the real topic. Additionally, embed transient contextual references (e.g. selected scripture verses or transaction IDs) directly into the recorded user turn so follow-up questions retain the subject across all subsequent turns.
- **Action Button Multi-Line Text Clipping**: Never assign fixed heights (e.g. `layout_height="46dp"`) to buttons containing multi-line or dynamic text. Constrained heights vertically clip the second line on mobile screens. Always use `android:layout_height="wrap_content"`, `android:minHeight="48dp"`, and `android:paddingVertical="10dp"`.
- **Text Selectability & 1-Tap Copy in Content Views**: In chat and reading interfaces, set `android:textIsSelectable="true"` on content TextViews so users can highlight and copy spans manually. Provide an adjacent 1-tap copy button (`ClipboardManager.setPrimaryClip`) for copying full content without requiring manual selection gestures.
- **Internal Sandbox File Push via `run-as`**: Pushing files directly to `/data/data/<pkg>/` fails with `Permission denied` even under USB debugging. Push to `/data/local/tmp/` first, copy into the app sandbox with `adb shell "run-as <pkg> cp /data/local/tmp/<file> files/<file>"`, then execute `am force-stop` and relaunch to flush in-memory state.
- **MediaButtonReceiver Intent Delegation in Service**: Registering `MediaButtonReceiver` in `AndroidManifest.xml` and building pending intents with `MediaButtonReceiver.buildMediaButtonPendingIntent(...)` is insufficient if `onStartCommand()` omits `MediaButtonReceiver.handleIntent(mediaSession, intent)`. Media button events from system quick settings carousels, lockscreen cards, or Bluetooth headsets trigger service start but silently drop the transport command without explicit intent delegation.
- **Programmatic App Icon Boolean Union in Pillow/PIL**: When generating app icon mipmap assets (`ic_launcher.png`, `ic_launcher_round.png`) with Python Pillow, never composite overlapping semi-transparent shapes or separate primitives for stems, beams, and noteheads directly onto the color buffer. Overlapping alpha paths produce internal seams, double-alpha artifacts, and corner notches ("dog ears") where angles meet. Instead, compose a single 8-bit binary mask (`mode='L'`) using boolean union (`np.maximum`), draft stems and angled beams as a single closed polygon sharing vertices along the exact slope, mask a continuous gradient through that single united mask, and apply Gaussian blur to the mask for outer bloom and elevation shadows.
