---
name: mobile-payment-automation
description: Use when building Android payment and transfer automation.
---

# Mobile Payment Automation (QRIS, Bank Transfers, E-Wallet Notification Parsing & Offline-First Fintech)

Comprehensive workflow for engineering native Android background payment capture (QRIS, peer-to-peer transfers, bank transfers, utility bills, and inbound funds), resilient regex parsing heuristics, local-first SQLite persistence, and zero-cost cloud synchronization across mobile and desktop.

## 1. Android Background Notification Interception Architecture

### The System Security Boundary (Web vs Native)
- **Web & WebView Sandbox Strict Isolation**:
  Web browsers, PWAs, and Android system WebViews **cannot intercept notifications from third-party applications**. Android OS framework strictly isolates notification queues behind system permissions; any inbound payment auto-capture feature requires a native Android service (`NotificationListenerService`).
- **`NotificationListenerService` Declaration**:
  Declare in `AndroidManifest.xml` protected by the system permission guard:
  ```xml
  <service
      android:name=".service.QrisNotificationListenerService"
      android:label="Payment & Transfer Interceptor"
      android:permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"
      android:exported="true">
      <intent-filter>
          <action android:name="android.service.notification.NotificationListenerService" />
      </intent-filter>
  </service>
  ```
- **Non-Bypassable Manual User Authorization**:
  Android OS framework strictly forbids granting notification listener access programmatically from within an app. Check enabled status and launch the system settings intent:
  ```kotlin
  fun isNotificationAccessGranted(context: Context): Boolean {
      val flat = Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners")
      return flat != null && flat.contains(context.packageName)
  }

  fun requestNotificationAccess(context: Context) {
      val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
      context.startActivity(intent)
  }
  ```

### Android 13+ "Restricted Settings" (Setelan Terbatas) Sideload Block
When an APK is sideloaded (installed outside Google Play Store via WhatsApp, browser download, or file manager) on Android 13/14+ (including Infinix XOS, Xiaomi HyperOS, Oppo ColorOS):
- The `NotificationListenerService` toggle in *Device & app notifications* is disabled and grayed out with the label `"Dikontrol oleh Setelan Terbatas"` (*Controlled by Restricted Settings*).
- **Manual Bypass on Device (No PC required)**:
  1. Long-press app icon on home screen -> Tap **App Info** (Detail Aplikasi / `(i)` icon).
  2. In the top-right corner, tap the three dots (**⋮**).
  3. Tap **"Izinkan setelan terbatas"** (*Allow restricted settings*).
  4. Authenticate with device PIN / fingerprint.
  5. Return to *Notification Access* -> the toggle is now enabled and clickable.
- **Automated Bypass via ADB (USB Debugging)**:
  When the device is connected to a PC with USB Debugging enabled:
  1. Ensure the user accepts the RSA authorization prompt on the phone screen (if status is `unauthorized`, ADB commands fail).
  2. Unlock restricted settings:
     ```bash
     adb shell appops set <package_name> ACCESS_RESTRICTED_SETTINGS allow
     ```
  3. Directly grant the listener service without user opening settings:
     ```bash
     adb shell cmd notification allow_listener <package_name>/<service_class_name>
     ```
  4. Whitelist background battery optimization:
     ```bash
     adb shell dumpsys deviceidle whitelist +<package_name>
     ```
- **OEM Battery Optimization Trap (Transsion XOS, MIUI, HyperOS, ColorOS)**:
  OEM task cleaners terminate background listener services during screen-off sleep. Always request battery optimization whitelist during onboarding:
  ```kotlin
  val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
  if (!powerManager.isIgnoringBatteryOptimizations(context.packageName)) {
      val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
          data = Uri.parse("package:${context.packageName}")
      }
      context.startActivity(intent)
  }
  ```

---

## 2. Indonesian E-Wallet, QRIS & Bank Transfer Parsing Heuristics

Payment notifications are not limited to QRIS. Users frequently perform peer-to-peer bank transfers, utility bill payments, and receive funds. A robust parser must differentiate:
1. **Outbound QRIS**: Merchant payment -> Expense (deducts balance, default category Food).
2. **Outbound Bank / E-Wallet Transfer**: "Transfer ke [Nama/Rekening]" -> Expense (deducts balance, category Money).
3. **Outbound Bill Payments**: "Pembayaran tagihan PLN/listrik/pulsa" -> Expense (deducts balance, category Housing/Education).
4. **Inbound Transfers**: "Transfer masuk dari [Nama]" / "Dana masuk" -> **Income** (adds to balance, category Money).

### Package Mapping & Negative Filters
- GoPay: `com.gojek.app`, `com.gojek.gopay`
- ShopeePay: `com.shopee.id`
- SeaBank: `com.seabank.id`
- BCA / myBCA: `com.bca`, `com.bca.mybca`
- DANA: `id.dana`
- OVO: `owo.id`
- Mandiri Livin: `id.bmri.livin`
- BRImo: `id.co.bri.brimo`

- **Negative Promo Suffix Filter Trap**:
  Indonesian e-wallets (especially ShopeePay and GoPay) routinely append promotional marketing suffix text to genuine transaction notices (e.g. *"Kamu telah membayar Rp 15.000 ke Teh Sri. Dapatkan cashback hingga 100%!"*). Never discard based on negative words (`cashback`, `dapatkan`, `koin`, `voucher`, `promo`) if an authoritative payment verb is present (`kamu telah membayar`, `telah membayar`, `berhasil bayar`, `transfer berhasil`, `berhasil transfer`, `kirim saldo berhasil`, `transaksi berhasil`). Only drop if negative words occur WITHOUT any positive payment verbs.

### Multi-Account & Multi-Wallet Isolation (SeaBank, ShopeePay, DANA, GoPay, Tunai)
- **Monolithic Balance Anti-Pattern**:
  Aggregating all liquid funds into a single generic "Active Balance" obscures per-channel liquidity. Each transaction must record `wallet_source`: `seabank` | `shopeepay` | `dana` | `gopay` | `cash` | `other`.
- **E-Wallet & Bank Real-Time Sync Reality**:
  Personal, zero-budget applications CANNOT directly access official real-time Bank/E-Wallet APIs. Open Finance / SNAP BI protocols and corporate banking APIs mandate business registration (PT/CV), PJP licensing from Bank Indonesia, extensive security audits, and paid aggregator subscription fees (e.g. Brick, Ayoconnect, OneLink).
  **Verified Architecture**: `NotificationListenerService` background interception + local parsing is the only viable zero-cost, privacy-respecting automation for individual accounts. When transactions fail to draft:
  1. Verify the exact package name (`com.seabank.id`, `com.shopee.id`, `id.dana`).
  2. Audit notification keywords (`Transfer Masuk`, `Pembayaran Berhasil`, `QRIS Berhasil`, `Kamu telah membayar`).
  3. Ensure Android 13+ "Restricted Settings" (Setelan Terbatas) is explicitly bypassed and battery optimization is disabled.

### Zero-Confirmation Auto-Commit Architecture (No Staged Draft Blocking)
- **Zero-Confirmation Mandatory Rule**:
  Never trap automated payments (QRIS, peer transfers, top-ups) in an uncommitted "Draft Inbox" that requires manual user review or 1-tap approval before updating the ledger. Users want instant zero-effort recording where balances are deducted or credited immediately without forgetting.
- **Immediate Balance Mutation & Ledger Commit**:
  When `QrisNotificationListenerService` parses a valid transaction, immediately invoke `processAutoTransaction(result)`:
  1. Append directly to active ledger transactions.
  2. Mutate liquid wallet balances and total available balance immediately.
  3. Persist data to storage synchronously.
- **Safety Safeguard via Notification Undo (`[Batalkan Transaksi]`)**:
  Rather than requiring pre-commit approval, post a high-priority status notification stating:
  `"⚡ FinSmart: QRIS Rp 15.000 ke Teh Sri otomatis dicatat! Saldo terpotong."`
  Include an interactive action button `[Batalkan Transaksi]` that triggers a broadcast receiver to roll back the entry and refund the balance if the capture was accidental.

### The In-App Only Receipt Gap & Fallback (e.g. SeaBank QRIS)
- **The Missing Push Notification Reality**:
  Certain Indonesian banking apps (notably SeaBank) **never dispatch an Android status bar push notification for outbound QRIS transactions**. When a user scans and pays, the bank only renders an in-app receipt screen.
- **Resilient Fallback Protocols**:
  Because `NotificationListenerService` cannot see transactions without a status bar notification, provide two essential fallbacks:
  1. **"Tempel Struk / Clipboard Auto-Detect"**: Expose a quick receipt paste button on the dashboard. When the user copies transaction details or shares the receipt, parse it immediately with `QrisNotificationParser.parseReceipt(text)` and auto-commit.
  2. **Dedicated Receipt Regex**: Ensure regex handles common receipt labels (`Merchant:`, `Nama Penerima:`, `Total Pembayaran:`, `Waktu Transaksi:`).

### Official Bank & E-Wallet Vector Asset Integration (No Emoji / Generic Shapes Trap)
- **The Emoji / Generic Clipart Anti-Pattern**:
  Never rely on standard Unicode emojis (`🏦`, `🟠`, `🟢`, `🏛️`, `💵`) or flat unbranded shapes for banking partners in fintech applications. Users expect authentic brand identity.
- **Authentic Vector Specifications (Verified Against Real Brand Kits & Photos)**:
  * **SeaBank**: Red-Orange (`#FF5722`) sun/coin circle with white concentric divider and inner disk containing bold white capital 'S', partially submerged above two parallel royal blue (`#0066FF`) ocean waves with smooth rounded caps and a white separation contour.
  * **ShopeePay**: Iconic Shopee Red-Orange (`#EE4D2D`) stylized bifold wallet (angled back flap + front pocket with card fold line) containing a bold, solid black capital 'S' (`#000000`) centered on the front face.
  * **GoPay**: Vibrant Cyan (`#00AAD8`) squircle container with a clean white puffy rounded wallet silhouette, horizontal cyan flap/slot line, vertical keyhole cutout on the right edge, and lowercase bold white `gopay` wordmark underneath.
  * **DANA**: Official DANA Royal Blue (`#118EEA`) squircle container with a centered solid white circle in the upper portion containing a blue waving ribbon/banner, and bold uppercase white `DANA` wordmark underneath.
  * **BCA**: Corporate Navy Blue (`#00388A`) with high-contrast bold geometric 'BCA' lettering (exclude from default wallets unless explicitly requested by user).
  * **Cash / Tunai**: Crisp Emerald Green (`#10B981`) with layered banknote vector geometry and centered currency emblem.
- **Systemic App Parity**:
  Deploy these vector drawables consistently across:
  1. Horizontal multi-wallet carousel cards (`item_wallet.xml`).
  2. Staged notification draft cards (`item_draft.xml`).
  3. Transaction history avatars (`item_transaction.xml`), dynamically switching between the source wallet vector for automated bank events and category monograms for manual entries.

### Regex Extraction Recipes
1. **Inbound vs Outbound Detection**:
   ```kotlin
   val isIncoming = lowerText.contains("transfer masuk") ||
           lowerText.contains("dana masuk") ||
           lowerText.contains("menerima uang") ||
           lowerText.contains("rekening dikredit") ||
           lowerText.contains("saldo masuk")
   ```
2. **Amount Extraction**:
   - Strip punctuation: match currency groups `(?:rp|idr|sebesar\\s+rp|bayar\\s+rp|transfer\\s+rp|sebesar)\\s*[:.]?\\s*([0-9]{1,3}(?:\\.[0-9]{3})+|[0-9]{4,})` and clean periods (`.`) before parsing to integer.
   - Fallback: match standalone formatted currency figures `([0-9]{1,3}(?:\\.[0-9]{3})+)`.
3. **Recipient vs Sender Target Extraction**:
   - Outbound recipient / merchant: match `(?:ke|pada|di|kepada)\\s+([^,.\\n]+?)(?:\\.|\\s+telah|\\s+berhasil|\\s+sukses|\\s*dgn|\\s*dengan|\\s*sebesar|$)`.
   - Inbound sender: match `(?:dari|oleh)\\s+([^,.\\n]+?)(?:\\.|\\s+telah|\\s+berhasil|\\s+sebesar|$)`.
   - Strip trailing stopwords (`telah`, `berhasil`, `sukses`, `sebesar`, `menggunakan`, `rekening`).
4. **Sliding Deduplication Ring Buffer**:
   - E-wallets often fire secondary notifications within seconds of payment (e.g. cashback rewards, coin receipts).
   - Compute deduplication hash: `"${packageName}_${amount}_${timestamp / 60000}"` (quantized to 60-second windows).
   - If hash exists in the local 2-minute memory buffer, discard to prevent deducting user balance twice.
5. **Decoupled JVM Unit Testing**:
   Always write JUnit tests in `src/test/java/.../` validating each bank and e-wallet sample string (outbound transfer, inbound funds, QRIS, and negative promo filters) before running Gradle APK compilation:
   ```bash
   ./gradlew testDebugUnitTest --no-daemon
   ```

---

## 3. Zero-Budget Multi-Device Synchronization & Hosting

For personal projects where users lack international credit cards and have zero hosting budget:
- **Cardless Cloud Database**: Use Supabase Free Tier (PostgreSQL + Row-Level Security + Auth). Registration supports GitHub OAuth without credit card verification.
- **Cardless Web Hosting (Vercel / Cloudflare Pages)**:
  - Deploy Vite/React frontend to Vercel connected to GitHub with zero cost.
  - **SPA Rewrite Rule in `vercel.json`**: Always add rewrite rules to prevent 404 errors on browser refresh:
    ```json
    {
      "rewrites": [{ "source": "/(.*)", "destination": "/" }]
    }
    ```
  - **Client-Side Supabase Key Configuration**: Provide an in-app settings UI saving `supabase_url` and `anon_key` to `localStorage` so users can link cloud databases without having to modify hosting build environment variables.
- **Local-First SQLite & Room Persistence**:
  - Offline mode writes to local SQLite (Android Room) or LocalStorage (Web) immediately.
  - Transactions carry UUID `id`, `updated_at`, `is_deleted` (soft delete), and `source` (`manual` | `template` | `qris_auto`).
  - Auto-captured payments commit immediately to local DB and adjust balance (+ for income, - for expense) so no transaction is forgotten. Users can edit details (merchant notes, menu items, categories) post-transaction.
  - When network is restored and user is authenticated, background workers sync pending deltas to Supabase via upsert.

---

## 4. Android Build, Gradle & Layout Toolchain Rules on Windows

- **Separate Package Guard for Companion Apps**:
  Never compile different companion apps (e.g. TaskFlow vs Voice Assistant vs Bible) under the same `applicationId`. Sideloading via `adb install -r` replaces the earlier app, deleting its launcher icon and data. Always maintain distinct package namespaces (e.g. `com.ferdinand.mahiru` vs `com.ferdinand.taskflow`).
- **Button Vertical Text-Clipping Trap**:
  Never set fixed `android:layout_height="46dp"` or similar hardcoded heights on buttons containing localized multi-word text. When text wraps to two lines on compact mobile viewports, the second line is clipped at the bottom. Use `android:layout_height="wrap_content"` with `android:minHeight="48dp"` and vertical padding (`android:paddingVertical="10dp"`).
- **Android Studio JBR for CLI Builds**:
  When building without system Java in PATH, export the bundled JBR from Git-Bash:
  ```bash
  export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
  export PATH="$JAVA_HOME/bin:$PATH"
  ./gradlew assembleDebug --no-daemon
  ```
- **AGP 9.4+ Kotlin Compilation**:
  In Android Gradle Plugin 9.4+, Kotlin compilation is built directly into `alias(libs.plugins.android.application)`. Do not declare redundant standalone Kotlin Gradle plugins in `app/build.gradle.kts`.
- **AAPT2 Adaptive Icon Resource Linking Trap**:
  When `mipmap-anydpi-v26/ic_launcher.xml` references `@drawable/ic_launcher_background` or `@drawable/ic_launcher_foreground`, Gradle build fails during `processDebugResources` if those XML drawables are missing from `res/drawable/`. Ensure both background and foreground vector drawables are present.
- **Top Bar & Horizontal LinearLayout Character-Squeezing Bug**:
  When placing multiple buttons with `wrap_content` alongside an app title or text container with `layout_width="0dp"` and `layout_weight="1"` in a horizontal `LinearLayout`:
  The buttons consume all horizontal space on typical phone viewports. The `weight="1"` text container is squeezed down to single-character width, forcing titles like `"FinSmart Native Android & QRIS"` to wrap vertically character-by-character (`F ir S a r t N a t iv e...`).
  **Fix**: Set compact padding and dimensions on header action buttons:
  `android:minWidth="0dp"`, `android:minHeight="0dp"`, `android:paddingHorizontal="6dp"`.
  Set the title container to `layout_width="wrap_content"`, and place an expanding spacer `<View android:layout_width="0dp" android:layout_height="1dp" android:layout_weight="1" />` between the title and the action buttons so the title never gets compressed.
- **Android 15 (targetSdk 35+) Enforced Edge-to-Edge & WindowInsets Collision**:
  On Android 15 (API 35+ / targetSdk >= 35), Edge-to-Edge rendering is mandatory and enforced by the OS framework by default, even without calling `enableEdgeToEdge()`. Layouts using `match_parent` without window insets render behind the system status bar and navigation bar. Top headers collide with the clock, camera cutout, and battery icons; bottom navigation bars and submit buttons are covered by the 3-button system navigation bar (Back, Home, Recents).
  **Fix**:
  Programmatically apply WindowInsets directly to the outer edges of the content containers rather than setting flat root container padding:
  ```kotlin
  enableEdgeToEdge()
  ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.rootContainer)) { _, insets ->
      val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
      topHeader.setPadding(topHeader.paddingLeft, bars.top + defaultPaddingTop, topHeader.paddingRight, topHeader.paddingBottom)
      bottomNav.setPadding(bottomNav.paddingLeft, bottomNav.paddingTop, bottomNav.paddingRight, bars.bottom + defaultPaddingBottom)
      insets
  }
  ```
  This ensures status bar icons and navigation gestures never occlude interactive elements or brand headers.

- **Adaptive Launcher Icon & In-App Brand Identity Trap (Human Designer Grade vs Clipart)**:
  In Android 8.0+ (API 26+), the system strictly resolves app icons via `res/mipmap-anydpi-v26/ic_launcher.xml` and `ic_launcher_round.xml`, which point to `@drawable/ic_launcher_background` and `@drawable/ic_launcher_foreground`. Leaving default Android Studio boilerplate renders the generic green robot on the user's phone home screen.
  1. **Enforce Strategic Unity**: Never slap disjointed symbols together (e.g. generic clipart dollar sign in a circle). Craft a unified geometric mark (e.g. an architectural foundation pillar combined with a kinetic 45° growth blade and an illuminated keystone beacon dot).
  2. **1:1 Visual Parity**: Deploy the exact same vector emblem across both the in-app top header (`34dp` container) and Android adaptive launcher icons (`ic_launcher_foreground.xml` and `ic_launcher_background.xml` with deep luxury obsidian `#0B0C10` and ambient halo glow).
  3. **Visual Verification Protocol**: When requested, generate an interactive local HTML/SVG preview board (`PREVIEW_LOGO_IKON.html`) on the desktop so users can inspect vector precision and brand parity directly in their browser.

- **Deliverable Artifact Reporting Protocol**:
  When compiling and producing APKs or standalone installers, always state the complete absolute path to the ready-to-run artifact in plain text (e.g. `C:\Users\User\...\app-vX.Y.apk`), along with file size, mirror paths, and git commit. Never ask the user to find the file inside nested Gradle `build/outputs/apk/debug/` folders.

---

## 5. Dual-Mode (DayNight) Android & Web Fintech Theming Architecture

### Native Android DayNight Token Structure
To support system dark mode without complex runtime activity recreation:
1. **Inherit from DayNight in `res/values/themes.xml`**:
   ```xml
   <style name="Theme.FinSmart" parent="Theme.Material3.DayNight.NoActionBar">
       <item name="colorPrimary">@color/emerald_primary</item>
       <item name="android:statusBarColor">@color/bg_canvas</item>
       <item name="android:windowBackground">@color/bg_canvas</item>
   </style>
   ```
2. **Mirror Semantic Tokens in `res/values-night/colors.xml`**:
   - `bg_canvas`: Light `#F9F8F6` -> Night `#121316` (warm dark slate, never `#000000` pitch black).
   - `card_surface`: Light `#FFFFFF` -> Night `#1A1B1F`.
   - `text_primary`: Light `#18181B` -> Night `#EDEDED`.
   - `border_subtle`: Light `#EBE8E1` -> Night `#26282E`.
3. **The Hardcoded Drawable Color Trap**:
   Never use raw hex colors (`#F4F4F5`, `#E4E4E7`) inside custom XML shape drawables (`shape_icon_badge.xml`, `shape_type_badge.xml`). Always reference semantic resources (`@color/bg_canvas`, `@color/border_subtle`). Hardcoded colors in drawables will cause icon containers to burn with glaring light backgrounds when the phone is in dark mode.

### Web (Tailwind v4) Class-Based Dark Mode Setup
In Tailwind CSS v4, class-based toggling (`<html class="dark">` or `<body class="dark">`) requires registering the custom variant in the global stylesheet:
```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));
```
Without `@custom-variant dark`, Tailwind v4 defaults to `@media (prefers-color-scheme: dark)` and ignores DOM class additions. Couple this with a custom hook checking `localStorage` and `window.matchMedia` on initial load.

---

## 6. Fintech UX Safety & Ledger Integrity Controls

### Direction-First Transaction Hierarchy (Income vs Expense vs Transfer)
- **The Category-Type Flattening Trap**:
  Never mix transaction direction (Income vs Expense) with expense budget classification (Needs vs Wants) in a single flat selector row (e.g. `[Needs] [Wants] [Pemasukan]`). Needs and Wants are classifications of Expenses, not peers to Income. This confuses users and causes label truncation on standard mobile viewports.
- **Two-Tier Flow**:
  1. **Tier 1 (Cash Flow Direction)**: Top tab selector clearly distinguishing `[ Pengeluaran (-) ]` vs `[ Pemasukan (+) ]` vs `[ Transfer / Investasi (⇄) ]`.
  2. **Tier 2 (Budget Allocation)**: Only when `Pengeluaran` is active, display budget allocation chips (`Needs 50%` vs `Wants 30%`).
  3. **Contextual Action Button**: Submit button label and color must dynamically reflect the active flow (e.g. emerald "Simpan Pemasukan (+)" vs rose "Simpan Pengeluaran (-)").

### Confirmation Gates for Recurring / Routine Actions
- **The Accidental 1-Tap Deduction Trap**:
  Never execute one-tap expense deductions directly on item click for routine templates or quick-add action cards. Users scrolling or handling their phones casually will mis-tap and pollute their ledger balance.
- **Explicit Modal / Dialog Prompt**:
  Always route routine template clicks through an intermediate confirmation dialog displaying:
  1. Transaction title and merchant name.
  2. Formatted deduction amount (`-Rp X.XXX`).
  3. Category and budget classification tag (`Needs` vs `Wants`).
  4. Explicit **Batal (No)** and **Ya, Catat (Yes)** action buttons.
  Deduct the balance and persist the transaction record *only* after affirmative confirmation.

### Destructive Factory Reset Flow
- **Clean Slate for Seeded / Demo Ledgers**:
  When transitioning a demo/seeded app to genuine personal use, provide a complete Factory Reset flow that clears all transactions, goals, and resets active balance to 0.
- **Frictional Confirmation Safeguard**:
  Prevent catastrophic data loss by requiring high-friction confirmation:
  - On Web: Require typing the uppercase word `"RESET"` into a text field before enabling the final delete button.
  - On Native Android: Trigger an explicit two-step high-contrast warning alert dialog explaining the permanent loss of transaction history and zeroing of balance.

### Third-Party Cloud Auth Security & Provisioning Reality
- **Never Attempt Headless OAuth / CLI Scraping with Passwords**:
  Third-party developer platforms (such as Supabase, GitHub, Vercel) deploy strict anti-bot mechanisms: Cloudflare Turnstile, Arkose CAPTCHAs, and out-of-band email/authenticator 2FA prompts. Headless automation scripts or browser sessions cannot bypass these interactive gates.
- **The Zero-Card Baked Client Key Pattern**:
  Instruct the user to complete the 1-click browser OAuth login on Supabase (which requires no credit card on free tiers), retrieve the public Project URL and Anon API Key, and either:
  1. Bake those keys directly into build-time environment variables / constants for a ready-to-run APK and web deployment.
  2. Or store them client-side in the app's settings storage (`localStorage` / `SharedPreferences`) without exposing server secrets.
- **Deterministic Supabase Project URL Derivation from Anon Key**:
  When a user only provides the `anon` JWT key and dashboard URL, extract the project ref directly from the JWT payload (`ref` claim) or from `supabase.com/dashboard/project/<project-ref>/`. The Project URL is deterministically `https://<project-ref>.supabase.co`.
- **The Supabase "Confirm Email" Default Trap & Frictionless Auto-Confirm Trigger**:
  New Supabase projects enable "Confirm email" by default. Immediate login right after signup fails with `error_code: "email_not_confirmed"`.
  - *The UI Navigation Trap*: If directing users to the dashboard, warn that the toggle is NOT in `NOTIFICATIONS > Emails` (which only edits SMTP email templates), but under `CONFIGURATION > Sign In / Providers > Email`. Searching for "confirm" in page search often lands on SMTP template cards.
  - *Headless Pooler Direct Connection*: If the database password and project ref are known, never force non-technical users to manually run SQL in the web editor or hunt dashboard toggles. Direct DB hosts (`db.<ref>.supabase.co`) are IPv6-only on free tier; connect via the IPv4 connection pooler (`aws-0-<region>.pooler.supabase.com` on port `6543`, user `postgres.<project_ref>`, ssl `{ rejectUnauthorized: false }`) using Node `pg` or Python `psycopg2`.
  - *Permanent Auto-Confirm Database Trigger*: Install a database trigger directly on `auth.users` so all future signups (including `@gmail.com` or custom domains) are auto-confirmed at insertion time:
    ```sql
    CREATE OR REPLACE FUNCTION public.auto_confirm_user()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.email_confirmed_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;

    DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
    CREATE TRIGGER on_auth_user_created
    BEFORE INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.auto_confirm_user();
    ```
    *Note*: Never include `confirmed_at = NOW()` in updates on `auth.users`; PostgreSQL rejects it because `confirmed_at` is a generated column. Update only `email_confirmed_at = NOW()`.
- **Consumer Email Domain Placeholders**:
  Avoid domain-specific placeholders (such as `@campus.id` or `@corp.com`) on auth forms. Use standard consumer examples (`@gmail.com`) so users do not falsely conclude that account creation is restricted to institutional domains.

