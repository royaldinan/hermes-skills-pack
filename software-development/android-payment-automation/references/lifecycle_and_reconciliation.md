# Android Banking Service Lifecycle, Sensitive Notifications & In-App Reconciliation

Deep-dive operational patterns for Android 13/14+ banking notification capture, OEM power-saver survival, accessibility history reconciliation, and storage persistence.

---

## 1. NotificationListenerService Rebind Watchdog (Ultra Power Saver Survival)

### Root Cause of Service Death
On aggressive OEM Android distributions (Infinix XOS, Xiaomi HyperOS, Samsung OneUI), entering Ultra Power Saver, closing recent apps, or long sleep states silently unbinds `NotificationListenerService`.
When inspecting via `adb shell dumpsys activity services <pkg>`:
```text
Bindings:
* IntentBindRecord{...}:
  binder=null requested=false received=false hasBound=false doRebind=false
```
Android's `NotificationManagerService` WILL NOT deliver notifications to an unbound listener (`hasBound=false`). The service appears registered in `enabled_notification_listeners`, but is functionally dead.

### Recovery Architecture: Lifecycle Rebinding
Always invoke `NotificationListenerService.requestRebind()` on both application cold-start and every activity resume:
```kotlin
// In FinSmartApplication.kt
override fun onCreate() {
    super.onCreate()
    requestNotificationListenerRebind()
}

// In MainActivity.kt
override fun onResume() {
    super.onResume()
    requestNotificationListenerRebind()
}

private fun Context.requestNotificationListenerRebind() {
    try {
        val component = ComponentName(this, QrisNotificationListenerService::class.java)
        NotificationListenerService.requestRebind(component)
    } catch (e: Exception) {
        // Silently caught if notification listener permission is not yet granted by user
    }
}
```

---

## 2. Android 14+ Sensitive Notifications & Banking Permissions

Android 14 (API 34) and Android 15 introduce a dedicated security restriction: `RECEIVE_SENSITIVE_NOTIFICATIONS`.
By default, sideloaded applications have this mode set to `ignore`:
```bash
adb shell appops get <pkg> RECEIVE_SENSITIVE_NOTIFICATIONS
# Output: RECEIVE_SENSITIVE_NOTIFICATIONS: ignore
```
When ignored, banking notifications (SeaBank, BCA, Mandiri) containing financial transactions, balances, or OTPs are stripped or dropped before reaching `onNotificationPosted()`.

### Unlocking Headless via ADB
```bash
# Allow sensitive notification reception for banking/OTP
adb shell appops set <pkg> RECEIVE_SENSITIVE_NOTIFICATIONS allow

# Ensure notification posting is allowed
adb shell appops set <pkg> POST_NOTIFICATION allow
adb shell pm grant <pkg> android.permission.POST_NOTIFICATIONS

# Exempt from battery doze / ultra power saver kills
adb shell dumpsys deviceidle whitelist +<pkg>
adb shell appops set <pkg> RUN_IN_BACKGROUND allow
adb shell appops set <pkg> RUN_ANY_IN_BACKGROUND allow
```

---

## 3. Hybrid Real-Time Notification + Accessibility In-App History Reconciliation

### The Missing Merchant Name Blind Spot
Direct debit and instant bayar notifications often omit the counterparty/merchant name:
`"SeaBank Bayar Instan: Pembayaran QRIS ShopeePay kamu sebesar Rp3.000 pada 19 Okt 2026 23:31 WIB berhasil."`
- The push notification only knows `"QRIS ShopeePay"`, not the true physical or online merchant (e.g. `"Ayam Bakar Teh Sri"` or `"Indomaret"`).
- However, when the user opens the bank's active in-app transaction history (*Riwayat Transaksi*), the full counterparty/merchant name IS present on screen.

### The Anti-Duplication vs. Enrichment Trap
- **Pitfall**: When an AccessibilityService reads in-app transaction history, naive deduplication checks if a transaction with the same amount and wallet exists within 1-24 hours. If it exists, it returns `false` (drop duplicate). This prevents double-charging, but permanently freezes the generic name (`"Merchant Pembayaran"` or `"QRIS ShopeePay"`).
- **Rule (Reconciliation & Enrichment)**:
  When reading transaction history:
  1. Check if a recent transaction exists with matching `walletId` and `amount` within 24 hours.
  2. If found, check if its current merchant name is generic (`"Merchant Pembayaran"`, `"Rekening Tujuan"`, or generic wallet name).
  3. If generic, **ENRICH** the transaction: update `merchant`, `name`, `category`, and `icon` using the specific merchant scraped from the history view, and commit to disk.
  4. Only drop if the transaction already has an accurate, specific merchant name.
  5. If NO recent transaction exists (e.g. notification was lost during offline/power saver), record it as a new transaction and update wallet balance.

```kotlin
@Synchronized
fun syncScrapedTransaction(
    walletId: String,
    rawAmount: Long,
    isIncome: Boolean,
    titleOrMerchant: String
): Boolean {
    val now = System.currentTimeMillis()
    val signedAmount = if (isIncome) rawAmount else -rawAmount

    val existingTx = transactions.find { tx ->
        tx.wallet == walletId &&
        Math.abs(tx.amount) == rawAmount &&
        (now - tx.timestamp < 86400_000L)
    }

    if (existingTx != null) {
        val isGeneric = existingTx.merchant.contains("Merchant Pembayaran", ignoreCase = true) ||
                        existingTx.merchant.contains("Rekening Tujuan", ignoreCase = true) ||
                        existingTx.merchant.equals("ShopeePay", ignoreCase = true) ||
                        existingTx.category.equals("Other", ignoreCase = true)

        if (isGeneric && titleOrMerchant.isNotBlank() && !titleOrMerchant.equals(existingTx.merchant, ignoreCase = true)) {
            val classification = SmartCategoryClassifier.classify(
                merchantName = titleOrMerchant,
                rawNotification = titleOrMerchant,
                isInternalTransfer = existingTx.isInternalTransfer,
                isIncome = isIncome
            )
            existingTx.merchant = titleOrMerchant
            existingTx.name = if (isIncome) "Transfer Masuk - $titleOrMerchant" else "QRIS - $titleOrMerchant"
            existingTx.category = classification.category
            existingTx.type = if (isIncome) "income" else classification.type
            existingTx.icon = classification.icon
            existingTx.notes = "Diverifikasi & disinkronkan dari riwayat ${walletId.uppercase()}"
            saveData()
            return true
        }
        return false // Exact transaction already accurately recorded
    }

    // Not previously captured via notification -> Insert cleanly
    val classification = SmartCategoryClassifier.classify(
        merchantName = titleOrMerchant,
        rawNotification = titleOrMerchant,
        isInternalTransfer = false,
        isIncome = isIncome
    )
    val tx = TransactionModel(
        id = "tx-hist-${UUID.randomUUID()}",
        name = if (isIncome) "Transfer Masuk - $titleOrMerchant" else "QRIS - $titleOrMerchant",
        amount = signedAmount,
        category = classification.category,
        type = if (isIncome) "income" else classification.type,
        wallet = walletId,
        icon = classification.icon,
        source = "history_sync",
        merchant = titleOrMerchant,
        timestamp = now
    )
    addTransaction(tx)
    return true
}
```

---

## 4. Zero-Food Default Fallback Rule

- **Pitfall**: In multi-category heuristics, ending the classification cascade with `return CategoryClassification("Food", "needs", "🍔")`. When a user transfers to an acquaintance (`"Satrio Makhbut"`), pays an investment platform (`"Ajaib Futures"`), or pays a local workshop (`"Bengkel Las Berkah"`), defaulting to `"Food"` misleads the user and ruins budget accuracy.
- **Rule**:
  1. Test explicit sector dictionaries: Investment, Bills, Transport, Food, Shopping, Health, Education, Entertainment, Personal Care.
  2. If unmatched, check for human peer transfer indicators: contains `"transfer"`, `"kirim"`, `"rekening"`, `"ke "`, or matches personal name patterns (2+ capitalized words without commercial suffixes). Categorize as `Transfer` (`🔄`).
  3. If completely unknown, fall back STRICTLY to `Other` (`💸`), NEVER `"Food"`.

---

## 5. Synchronous Commit vs Asynchronous Apply for Power Saver Survival

- **Pitfall**: Calling `sharedPreferences.edit().apply()`. In Android, `apply()` commits to in-memory state immediately, but schedules an asynchronous write to disk. When aggressive OEM power management (e.g. Transsion Ultra Power Saver) kills background tasks or puts the device to sleep, the process is terminated before dirty pages are flushed to disk. On reboot or wake, the state reverts to the last disk snapshot, creating the illusion that database sync failed.
- **Rule**: In financial applications, all critical mutations (wallet balances, asset quantities, transaction logs) MUST call synchronous `commit()`:
  ```kotlin
  editor.putString("assets_json", assetArray.toString())
  editor.putString("wallet_balances_json", wbJson.toString())
  editor.commit() // Blocks until written to disk; survives SIGKILL from power manager
  ```
