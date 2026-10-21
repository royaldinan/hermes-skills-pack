---
name: android-payment-automation
description: Use when building Android payment and transfer automation.
version: 1.5.0
author: Ferdinand Manurung
license: MIT
metadata:
  hermes:
    tags: [android, fintech, qris, seabank, shopeepay, gopay, dana, notifications, double-entry, accessibility, dca, paylater, pnl, reconciliation]
    related_skills: [android-sideload-automation, cross-device-local-app, systematic-debugging]
---

# Android Payment Automation (QRIS, Bank Transfers, E-Wallet Notification Parsing & Offline-First Fintech)

Comprehensive architectural and implementation patterns for zero-touch background financial notification interception, regex parsing heuristics, double-entry multi-wallet balance reconciliation, and offline-first mobile fintech architectures (SeaBank, ShopeePay, GoPay, DANA, BCA, Livin Mandiri).

## When to Use
- Intercepting background payment and transfer notifications via native Android `NotificationListenerService`.
- Designing multi-wallet mobile finance systems with active cash balances vs. detached investment assets (Crypto, Gold, Bank Savings).
- Distinguishing merchant QRIS payments, person-to-person transfers, and internal self-transfers between user accounts.
- Preventing phantom balance inflation, false negative balances, and double-crediting in double-entry bookkeeping.
- Implementing transaction auto-logging and interactive draft inboxes with quick-action status bar notifications.

---

## 1. Notification Parsing Heuristics & Pitfalls

### Dynamic Regex for Separated Phrasing
E-wallet and banking notifications (notably ShopeePay, GoPay, and SeaBank) frequently separate transaction verbs with dynamic amounts, tenant names, or date/time stamps:
`"Pembayaran sebesar Rp 18.000 ke Dimsum Goreng Mentai telah berhasil. Dapatkan voucher cashback 50%!"`
- **Pitfall**: Checking strictly for contiguous substrings like `lowerText.contains("pembayaran berhasil")` evaluates to `false`. If the parser then applies a negative promo keyword filter (`"cashback"`, `"voucher"`, `"promo"`), the transaction is falsely dropped as spam.
- **Rule**: Positive confirmation checks must use case-insensitive dynamic regex patterns that tolerate intervening text:
  ```kotlin
  val POSITIVE_REGEX_PATTERNS = listOf(
      Pattern.compile("(pembayaran|transaksi|pesanan|order).*?(berhasil|sukses|selesai)", Pattern.CASE_INSENSITIVE),
      Pattern.compile("(berhasil|sukses).*?(bayar|membayar|dibayar|kirim|transfer)", Pattern.CASE_INSENSITIVE),
      Pattern.compile("(telah|sudah)\\s+(berhasil|membayar|dibayar|selesai)", Pattern.CASE_INSENSITIVE),
      Pattern.compile("(kamu|anda)\\s+telah\\s+(membayar|bayar)", Pattern.CASE_INSENSITIVE),
      Pattern.compile("bayar\\s+rp\\s*[0-9]", Pattern.CASE_INSENSITIVE),
      Pattern.compile("pembayaran\\s+(sebesar|rp)", Pattern.CASE_INSENSITIVE),
      Pattern.compile("menerima\\s+(dana|uang|saldo)", Pattern.CASE_INSENSITIVE)
  )
  ```
- **Rule**: If a positive confirmation regex matches and a valid amount (`amount > 0`) is extracted, never discard the notification based on trailing promotional/cashback teasers.

### Clean Merchant & Promo Trailer Suffix Stripping
In real-world merchant payments, notification bodies frequently append promotional teaser trailers:
`"Kamu telah membayar Rp 15.000 ke AYAM BAKAR MA YUYUM BNI. Total Penghematan Rp5. Cashback Rp5."`
- **Pitfall**: If the merchant regex matches greedily or without strict boundaries, it captures the entire promo suffix into the merchant name (`"AYAM BAKAR MA YUYUM BNI. Total Penghematan Rp5. Cashback Rp5."`).
- **Rule**: Explicitly strip promo tokens, trailing dots, and punctuation in `cleanMerchantName`:
  ```kotlin
  private fun cleanMerchantName(raw: String): String {
      var cleaned = raw.trim()
      cleaned = cleaned.replace(Regex("\\s*\\([0-9-]+\\)"), "").trim()
      val stopwords = listOf("telah", "berhasil", "sukses", "dengan", "dgn", "sebesar", "menggunakan", "rekening", "nomor", "pada")
      for (stop in stopwords) {
          if (cleaned.lowercase().endsWith(" $stop")) {
              cleaned = cleaned.substring(0, cleaned.length - stop.length - 1).trim()
          }
      }
      if (cleaned.contains("Total Penghematan", ignoreCase = true)) {
          cleaned = cleaned.split(Regex("Total\\s+Penghematan", RegexOption.IGNORE_CASE))[0].trim()
      }
      if (cleaned.contains("Cashback", ignoreCase = true)) {
          cleaned = cleaned.split(Regex("Cashback", RegexOption.IGNORE_CASE))[0].trim()
      }
      cleaned = cleaned.trimEnd('.', ',', ' ')
      return cleaned.ifEmpty { "Tujuan" }
  }
  ```

### The Title + Body Concatenation String Collision
- **Pitfall**: When gluing the notification title and body as `"$title $text"` (e.g., Title = `"ShopeePay"`, Body = `"Kamu telah membayar Rp 15.000 ke Teh Sri"`), the resulting string begins with `"ShopeePay Kamu telah membayar..."`. Any naive check for `"shopeepay kamu"` (intended to detect top-ups like *"telah ditambahkan ke ShopeePay kamu"*) evaluates to `true` on EVERY normal outbound expense. The expense is erroneously flagged as an inbound top-up (`isTopUp = true`), reversing debit logic.
- **Rule**: Inbound wallet destination checks (`"ke shopeepay"`, `"saldo shopeepay"`, `"ke akun shopee"`) must ONLY be tested against the notification BODY text (`text?.lowercase()`), never against the concatenated `title + text`.

### Clean Merchant & Sender Extraction
- **Merchant / Target Regex**:
  ```kotlin
  // Pattern 1: Direct "untuk <Merchant>" (e.g. "Pembayaran QRIS untuk PT Ajaib Futures Asia sebesar...")
  val untukRegex = Pattern.compile(
      "untuk\\s+([^,.\\n]+?)(?:\\s+sebesar|\\s+rp|\\.|\\s+telah|\\s+berhasil|\\s+pada|$)",
      Pattern.CASE_INSENSITIVE
  )

  // Pattern 2: Specific merchant prefixes (excluding 'pada' which introduces timestamps)
  val merchantRegex = Pattern.compile(
      "(?:ke|di|kepada|merchant:|toko:|nama merchant:|penerima:)\\s+([^,.\\n]+?)(?:\\.|\\s+telah|\\s+berhasil|\\s+sukses|\\s*dgn|\\s*dengan|\\s*sebesar|\\s+pada|$)",
      Pattern.CASE_INSENSITIVE
  )
  ```
- **Date/Time Stamp False-Positive Filtering**: Notifications often contain `"pada 16 Okt 2026 13:36 WIB"`. Never allow words preceded by `"pada"` to be extracted as a merchant name. Exclude month abbreviations (`jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des`) and time markers (`wib`, `wita`, `wit`, `pukul`, `jam`).
- **Sender Regex (Inbound)**:
  ```kotlin
  val senderRegex = Pattern.compile(
      "(?:dari|oleh)\\s+([^,.\\n]+?)(?:\\.|\\s+telah|\\s+berhasil|\\s+sebesar|\\s+pada|$)",
      Pattern.CASE_INSENSITIVE
  )
  ```
- **Stopwords & Account Number Stripping**: Always strip trailing stopwords (`"telah"`, `"berhasil"`, `"sukses"`, `"sebesar"`, `"pada"`) and bracketed account/phone digits (`Regex("\\s*\\([0-9-]+\\)")`) so raw strings like `"Satrio Makhbut (081234567890) telah"` clean to `"Satrio Makhbut"`.

### PayLater (SPayLater) vs. Cash Wallet Double-Deduction Trap
When a user pays a merchant using SPayLater or PayLater credit, the e-wallet (e.g. Shopee) often dispatches a purchase confirmation:
`"Pembayaran transaksi SPayLater sebesar Rp 25.000 berhasil."`
- **Pitfall**: If the notification listener deducts this from the user's ShopeePay cash wallet, the cash wallet drops into negative (`-Rp 25.000`), even though no cash was withdrawn from ShopeePay. Later, when the user pays off the SPayLater monthly bill from their bank account (e.g., SeaBank Bayar Instan `Rp 35.400`), real cash is debited from SeaBank. Tracking both transactions creates a false double-deduction with mismatched amounts.
- **Rule**: PayLater / SPayLater purchase notifications must be explicitly recognized and excluded from deducting cash balances (`isMatch = false`):
  ```kotlin
  val isShopeePkg = packageName.contains("shopee")
  val mentionsPayLater = lowerText.contains("spaylater") || lowerText.contains("paylater")
  val isBillPayment = lowerText.contains("pembayaran spaylater") || lowerText.contains("bayar tagihan") || lowerText.contains("seabank bayar instan")

  if (isShopeePkg && mentionsPayLater && !isBillPayment) {
      return QrisParseResult(isMatch = false, errorMessage = "Diabaikan: Transaksi SPayLater kredit")
  }
  ```
- **Rule**: Only the repayment notification from the funding bank (e.g. SeaBank) represents actual cash expenditure and should be recorded under category `Bills`.

---

## 2. Double-Entry Multi-Wallet Reconciliation & Self-Transfer

### The "Self-Wallet-As-Merchant" Negative Balance Disaster
When a user tops up an e-wallet from their bank account (e.g. SeaBank -> ShopeePay via Virtual Account or direct debit), the destination wallet typically emits an order confirmation notification:
`"Pembayaran sebesar Rp 57.066 ke ShopeePay telah berhasil."` or `"Kamu telah membayar Rp 57.066 ke ShopeePay."`
- **Pitfall**: The parser sees `ke ShopeePay` and extracts `targetName = "ShopeePay"`. If the parser lacks an explicit self-wallet check, it treats this notification as an outbound merchant expense for `"Food"`, subtracting Rp 57.066 from ShopeePay instead of adding it. When starting from Rp 0, ShopeePay balance flips negative (`-Rp 57.066`).
- **Rule**: Guard with `isTargetSameAsWallet`. If a notification from `shopeepay` lists `ShopeePay` as the target (or `gopay` lists `GoPay`, `dana` lists `DANA`), a wallet NEVER pays itself for goods or services. It is ALWAYS a Top-Up / Incoming credit:
  ```kotlin
  val bodyLower = (text ?: "").lowercase()
  val isTargetSameAsWallet = (defaultWalletId == "shopeepay" && (bodyLower.contains("ke shopeepay") || bodyLower.contains("saldo shopeepay") || bodyLower.contains("ke akun shopee"))) ||
          (defaultWalletId == "gopay" && (bodyLower.contains("ke gopay") || bodyLower.contains("saldo gopay"))) ||
          (defaultWalletId == "dana" && (bodyLower.contains("ke dana") || bodyLower.contains("saldo dana"))) ||
          (defaultWalletId == "seabank" && (bodyLower.contains("ke seabank") || bodyLower.contains("rekening seabank")))

  val isTopUp = isTargetSameAsWallet || lowerText.contains("isi saldo") || lowerText.contains("top up") || lowerText.contains("berhasil ditambahkan")
  ```

### Inbound Self-Transfer Detection (The Phantom Money Bug)
When a user moves funds from ShopeePay to SeaBank, SeaBank generates an inbound notification:
`"Kamu menerima dana sebesar Rp57.066 dari ShopeePay FERDINAND MANURUNG pada 14 Okt 2026 10:47 WIB."`
- **Pitfall**: Checking for self-transfers only on outbound notifications (`if (!isIncoming && isTransfer)`) treats this inbound deposit as external income. SeaBank is credited (+57.066) but ShopeePay is never debited, inflating total available balance (e.g. from 57.066 to 114.132).
- **Rule**: Inbound notifications (`isIncoming = true`) MUST be inspected for user identification keywords (user's name, phone core, account number) and supported wallet names (`"shopeepay"`, `"gopay"`, `"dana"`, `"seabank"`).
  ```kotlin
  if (isIncoming && (hasUserName || hasUserAcc || hasUserPhone)) {
      val detectedSource = when {
          lowerText.contains("shopeepay") || lowerText.contains("shopee") -> "shopeepay"
          lowerText.contains("gopay") || lowerText.contains("gojek") -> "gopay"
          lowerText.contains("dana") -> "dana"
          lowerText.contains("seabank") -> "seabank"
          else -> null
      }
      if (detectedSource != null && detectedSource != defaultWalletId) {
          isInternal = true
          sourceWalletId = detectedSource // Debit source e-wallet
          targetWalletId = defaultWalletId // Credit destination bank
      }
  }
  ```
- **Rule**: In double-entry ledger execution:
  ```kotlin
  if (tx.isInternalTransfer && tx.targetWallet != null) {
      val absAmount = Math.abs(tx.amount)
      walletBalances[tx.wallet] = (walletBalances[tx.wallet] ?: 0L) - absAmount
      walletBalances[tx.targetWallet!!] = (walletBalances[tx.targetWallet!!] ?: 0L) + absAmount
  }
  ```
  Total available balance remains mathematically constant (`-absAmount + absAmount = 0`).

### Bi-Directional Deduplication Window (5 Minutes)
When moving funds between two installed apps, both the source app (outbound transfer notification) and destination app (inbound deposit notification) may fire.
- Maintain a 5-minute (300,000ms) deduplication window checking:
  `tx.isInternalTransfer && tx.wallet == result.walletId && tx.targetWallet == result.targetWallet && Math.abs(tx.amount) == result.amount`
- Also drop incoming top-ups if an internal transfer targeting the receiving wallet already occurred within the 5-minute window (`tx.isInternalTransfer && tx.targetWallet == result.walletId && Math.abs(tx.amount) == result.amount`).
- Whichever notification arrives second is dropped as a duplicate, ensuring the double-entry balance adjustment runs exactly once.

---

## 3. Zero-Confirmation Auto-Record vs. Status Bar Quick Undo

For mobile fintech tracking:
- **Rule (Zero-Confirmation Default)**: Incoming payment and transfer notifications must be auto-recorded immediately to active transactions (`repository.processAutoTransaction`), deducting or crediting the corresponding wallet balances instantly. Never gate ledger updates behind an unapproved draft inbox by default.
- **Immediate Undo Notification**: Post an immediate high-priority status bar notification confirming the transaction (`"⚡ FinSmart: QRIS Dicatat & Saldo Terpotong"`) with a 1-tap **[Batalkan Transaksi]** action (`DraftActionReceiver.ACTION_DELETE_TX`) via a dedicated `BroadcastReceiver`. Tapping cancel reverses the transaction and refunds the balance.
- **In-App Receipt Fallback (The Blind Bank Solution)**: If a bank (e.g. SeaBank) does not dispatch push notifications for outbound QRIS, provide a prominent in-app **"📋 Tempel Struk"** option and clipboard detector (`QrisNotificationParser.parseReceipt()`) that extracts the merchant and amount from copied receipt text and auto-records the transaction in 1 tap.

---

## 4. UI Title Formatting & Ellipsis Prevention

- **Standardized Naming Convention**:
  - **Merchant / QRIS**: `QRIS - <Tenant>` (e.g. `QRIS - Teh Sri`, `QRIS - Teh Marni`, `QRIS - Indomaret`).
  - **Person Outbound Transfer**: `Transfer - <Person/Account>` (e.g. `Transfer - Satrio Makhbut Kustriyant`).
  - **Person Inbound Transfer**: `Transfer Masuk - <Sender>` (e.g. `Transfer Masuk - Ayah`).
  - **Internal Self-Transfer**: `<Source Wallet> ➔ <Target Wallet>` (e.g. `ShopeePay ➔ SeaBank`).
- **Ellipsis Truncation Prevention**: Never prefix self-transfers with verbose redundant labels like `"Transfer: SHOPEEPAY ➔ SEABANK"`. In standard 360dp mobile viewports with adjacent amount badges and icons, names exceeding ~22 characters truncate with an ellipsis (`Transfer: ShopeePay ➔ S...`). Use concise `<Source> ➔ <Target>`.
- **RecyclerView View Binding**: In `RecyclerView.Adapter.onBindViewHolder`, always explicitly bind `holder.tvName.text = tx.name`. If omitted, the element silently displays whatever preview string is hardcoded in the layout XML (e.g. `android:text="QRIS - Teh Sri"`), causing all dynamic transactions to display that static preview text.

---

## 5. Active Cash Balances vs. Accumulated Assets

- Saldo Tersedia (Active Operating Cash): Represents liquid cash across everyday spending accounts (SeaBank, ShopeePay, GoPay, DANA, Cash).
- Saving & Investment (Asset Portfolio): Long-term wealth storage (BTC, Physical/Digital Gold, Bank Deposito/Savings, Altcoins, Stocks). Must be kept completely detached from `walletBalances` so daily expense/income reporting does not distort investment valuations.

---

## 6. Semi-Automated Crypto Portfolio & Live DCA Auto-Convert (Ajaib Companion)

### The Walled-Garden Exchange Anti-Fraud Trap
- **Pitfall**: Attempting to automate portfolio scraping from retail crypto exchanges (e.g., Ajaib Kripto) via mobile private API sniffing (Frida, SSL unpinning, token scraping). These venues enforce Cloudflare WAF, device-ID fingerprinting, and strict regulatory anti-fraud checks. Non-official traffic triggers account freezing and locked funds. Third-party aggregators (CoinMarketCap) also cannot auto-sync without public retail API keys.
- **Rule**: Implement a **Smart Semi-Automated Ledger** with live public market tickers instead of reverse-engineering walled-garden exchange apps.

### Natural DCA Auto-Convert Input
- **Pitfall**: Forcing users to enter fractional cryptocurrency units (e.g. `0.00004418 BTC`). Retail users buy in round fiat sums (`Rp 65.000`) or stablecoin units (`5 USDT`). Manual coin unit entry creates friction, calculation errors, and abandoned tracking.
- **Rule**: Accept raw spend amount in fiat (IDR) or stablecoin (USDT) and auto-convert to coin units via live ticker at execution time:
  - **Fiat Buy (`IDR -> BTC`)**: `unitsReceived = nominalIdr / liveBtcIdrPrice`. Increment BTC units, increment `totalCostIdr` by `nominalIdr`.
  - **Stablecoin Buy (`USDT -> BTC`)**: `unitsReceived = nominalUsdt / liveBtcUsdtPrice`. Increment BTC units, decrement USDT balance by `nominalUsdt`.
  - **Fiat Stablecoin Buy (`IDR -> USDT`)**: `unitsReceived = nominalIdr / liveUsdtIdrPrice`. Increment USDT units, increment `totalCostIdr`.
- **DCA Average Buy Price**: `avgBuyPriceIdr = totalCostIdr / totalCoinUnits`.
- **Live Floating PnL on Active Holdings (The Negative Ghost Loss Pitfall)**:
  - **Pitfall**: Calculating global PnL as `totalPortfolioValuation - sum(allHistoricalBuyAmounts)`. When a user deletes an asset (e.g. Bitcoin) or holds 0 units, `totalPortfolioValuation` drops to 0, but historical buy records remain in storage, causing the portfolio to report a false ghost loss of `-Rp 65.000 (-100.0%)`! Similarly, manual asset balance additions without DCA records get falsely counted as 100% pure profit.
  - **Rule**: Floating PnL MUST be calculated strictly across **active holdings** (`unitsHeld > 0`):
    `assetPnL = currentValuation - (unitsHeld * avgBuyPrice)`
    If `unitsHeld <= 0` or the asset is deleted, its cost basis in active PnL is 0, returning clean `+Rp 0 (0.0%)`.
  - **Rule**: Deleting an asset from portfolio MUST prune or zero out orphaned historical purchase transactions for that symbol.
  - **Rule**: Manual asset entry/edits without DCA history set the cost basis baseline equal to user input, so PnL remains 0% until market prices move.

### Two-Way Asset Dialog Sync (The Ticker Overwrite Trap)
- **Pitfall**: When an asset has a live background ticker (BTC, USDT, Gold), allowing the user to edit the fiat amount (e.g. from Rp 65.000 to Rp 1.000.000) WITHOUT recalculating the unit quantity. When the app resumes or recovers from Ultra Power Saver, the ticker fetches fresh prices and recomputes `amount = units * currentPrice`. Because `units` was still `0.00004407 BTC`, the user's Rp 1.000.000 is silently overwritten back to Rp 65.015!
- **Rule**: In asset add/edit dialogs, ALWAYS implement bidirectional live conversion:
  - Editing fiat `amount` MUST automatically recalculate `quantity = amount / livePrice`.
  - Editing unit `quantity` MUST automatically recalculate `amount = quantity * livePrice`.
  - When saved, `amount` and `quantity` remain 100% mathematically coherent, preventing ticker overwrites.

### Commodity Assets (Physical Gold Spot via PAXG)
- Physical gold spot tracking in IDR can be sourced reliably without API keys using Indodax's public PAXG ticker (`https://indodax.com/api/ticker/paxgidr`). PAX Gold represents 1 troy ounce (31.1034768 grams) of fine physical gold backed 1:1.
- `goldPerGramIdr = paxgLastPrice / 31.1034768`.

### Public Ticker API User-Agent Pitfall (HTTP 403)
- **Pitfall**: Querying Indodax public ticker API endpoints (`https://indodax.com/api/ticker/btcidr`, `usdtidr`, `btcusdt`) via standard OkHttp or Java `HttpURLConnection` without headers triggers Cloudflare bot protection returning `HTTP 403 Forbidden`.
- **Rule**: Every HTTP request to public ticker endpoints MUST supply a standard browser User-Agent:
  ```kotlin
  val request = Request.Builder()
      .url("https://indodax.com/api/ticker/btcidr")
      .header("User-Agent", "Mozilla/5.0")
      .build()
  ```

---

## 7. Notification Blind Spots & OS-Level Blocking Diagnostics

### The Outbound QRIS Push Notification Blind Spot
- **Pitfall**: Assuming all banks and e-wallets emit Android push notifications for every transaction. Many digital banking apps (notably **SeaBank** and **BCA Mobile**) emit push notifications for *inbound* deposits (`"Dana Masuk ke Rekeningmu"`), but **DO NOT** emit an Android status bar notification when the user pays via QRIS in-app. Instead, they only render an ephemeral success screen (`"Pembayaran Berhasil"`) inside the active app.
- **Rule**: If a banking app never calls `NotificationManager.notify()`, a `NotificationListenerService` is fundamentally blind to the transaction. Never accuse the parser regex when the root cause is absence of system notification events.
- **Architectural Fallbacks**:
  1. **AccessibilityService (Screen Inspection)**: Listen for `TYPE_WINDOW_STATE_CHANGED` from package `id.co.bankbkemobile.digitalbank` or banking packages, parse root node text for `"Pembayaran QRIS Berhasil"` and extract nominal/merchant from the active view hierarchy.
  2. **Receipt Share-Sheet Intent**: Register an `ACTION_SEND` intent filter in `AndroidManifest.xml` accepting image/text so users can share payment receipts directly to FinSmart to trigger draft creation.
  3. **OCR / Quick-Capture**: Provide a 1-tap floating bubble or Quick Settings tile that takes a screenshot of the banking receipt and extracts transaction details locally.

### OS Notification Channel Blocking (`importance=NONE`)
- **Pitfall**: On aggressive OEM Android distributions (Infinix XOS, Xiaomi MIUI/HyperOS, Oppo ColorOS), e-wallet notifications (e.g. `com.shopee.id`) may be set to `importance=NONE` or have channels muted by OEM battery optimization without user knowledge.
- **Diagnostic Command**: Run ADB command:
  ```bash
  adb shell dumpsys notification --package <package_name>
  ```
  Inspect `AppSettings: <pkg> importance=...` and `mArchive=Archive (N notifications)`. If `importance=NONE` or `mImportance=0`, Android OS drops all notifications before `NotificationListenerService` can receive them.
- **Resolution**:
  - Direct user to app notification settings in OS to enable all channels.
  - Or unblock programmatically/via ADB:
    ```bash
    adb shell cmd notification allow_listener <listener_component>
    adb shell appops set <pkg> ACCESS_RESTRICTED_SETTINGS allow
    ```

### Headless AccessibilityService Activation via ADB (Jailbreaking Permissions)
When deploying background accessibility services (e.g. `FinSmartAccessibilityService`) to read in-app mutasi without requiring manual navigation through nested OEM settings:
```bash
# Read existing enabled accessibility services
CURRENT_A11Y=$(adb shell settings get secure enabled_accessibility_services)

# Append new service without wiping existing OEM/system accessibility tools
adb shell settings put secure enabled_accessibility_services "$CURRENT_A11Y:com.package/com.package.service.AccessibilityService"
adb shell settings put secure accessibility_enabled 1

# Bypass OEM Background Doze & Battery Restriction
adb shell dumpsys deviceidle whitelist +com.package
adb shell cmd appops set com.package BIND_ACCESSIBILITY_SERVICE allow
```

See `references/lifecycle_and_reconciliation.md` for in-depth watchdog lifecycle rebound patterns, Android 14 sensitive notifications, and dual-source history reconciliation.

---

## 8. Smart Multi-Sector Category Classification (Zero "Food" Default Bias)

- **Pitfall**: Falling back unclassified QRIS transactions to a hardcoded `"Food"` category. When users pay investment brokers (e.g. `PT Ajaib Futures Asia`, `Bibit`, `Stockbit`) or pay bills (`SPayLater`, `PLN`), tagging them as `"Food"` destroys budget tracking credibility.
- **Rule**: Implement a dedicated multi-sector category classifier (`SmartCategoryClassifier`) matching normalized merchant names and notification text against distinct financial sectors:
  1. **Investment (`📈 Investment`)**: `ajaib`, `bibit`, `bareksa`, `stockbit`, `pluang`, `indodax`, `tokocrypto`, `rdn`, `sekuritas`, `futures`, `crypto`, `kripto`, `saham`, `reksadana`, `treasury`.
  2. **Bills (`📄 Bills`)**: `spaylater`, `paylater`, `pln`, `listrik`, `token`, `pdam`, `bpjs`, `telkom`, `indihome`, `biznet`, `pajak`, `asuransi`, `cicilan`.
  3. **Transport (`🛵 Transport`)**: `gojek`, `goride`, `gocar`, `grab`, `maxim`, `spbu`, `pertamina`, `shell`, `bensin`, `kai`, `commuter`, `mrt`, `tol`, `parkir`.
  4. **Shopping (`🛍️ Shopping`)**: `indomaret`, `alfamart`, `superindo`, `toko`, `store`, `market`, `shopee`, `tokopedia`, `lazada`, `mall`.
  5. **Health (`💊 Health`)**: `apotek`, `apotik`, `kimia farma`, `k24`, `rs`, `klinik`, `dokter`, `halodoc`, `optik`.
  6. **Education (`📚 Education`)**: `universitas`, `univ`, `sekolah`, `kampus`, `kursus`, `buku`, `gramedia`, `spp`, `ukt`.
  7. **Entertainment (`🎮 Entertainment`)**: `bioskop`, `cinema`, `xxi`, `cgv`, `netflix`, `spotify`, `steam`, `game`, `tiket`.
- **Editable Categories**: Every transaction detail modal must provide a selectable category dropdown so users can immediately reassign misclassified items.

---

## 9. Custom Dialog & Modal Elevation Architecture (Anti-Translucent Text Overlap)

- **Pitfall**: Inflating a custom dialog view with `dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)` while omitting an explicit solid surface background on the root layout of the XML dialog. The dialog content renders 100% translucent, causing form labels, input boxes, and action buttons to visually overlap and collide with underlying dashboard numbers and list items.
- **Rule**: Every custom dialog layout root element (`dialog_*.xml`) MUST explicitly declare a solid, theme-aware surface background and elevation:
  ```xml
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="wrap_content"
      android:orientation="vertical"
      android:background="@drawable/shape_card"
      android:elevation="12dp"
      android:padding="22dp">
  ```
  This creates clean visual separation, drop shadows, and zero bleed-through from background activities.

