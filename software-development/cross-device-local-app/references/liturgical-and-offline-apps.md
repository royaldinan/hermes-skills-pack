# Liturgical, Devotional, & Offline-First Android Apps

Guidelines for building offline-first Android apps with authentic ecclesiastical grounding, Catholic liturgical cycles, exact prayer alarms, and direct client AI exegesis.

## 1. Canonical Ecclesiastical Data Grounding vs LLM Hallucination

### Liturgical Daily Readings (Ordo Lectionum Missae)
- **Zero Generative AI for Scripture Schedules**: Never allow an LLM or local randomizer to synthesize or pick "daily verses" for religious/liturgical apps. In the Catholic Church, daily Mass readings are strictly determined by the Church Liturgical Calendar (*Ordo Lectionum Missae*, adapted nationally by the Episcopal Conference e.g. Komisi Liturgi KWI in Indonesia).
- **Verified Sources**: Scrape or query authenticated ecclesiastical sources (`imankatolik.or.id`, `ekaristi.org`):
  * **Bacaan I**: From the Old Testament or Acts of the Apostles.
  * **Mazmur Tanggapan (Responsorial Psalm)**: Includes the official liturgical Refrain.
  * **Bacaan II**: Epistles / New Testament letters (present on Sundays, Solemnities, and Feasts).
  * **Bait Pengantar Injil**: Alleluia / Verse before the Gospel.
  * **Bacaan Injil**: The high point of the Liturgy of the Word.
  * **Liturgical Color**: Hijau (Ordinary Time), Putih (Christmas/Easter/Solemnities/Confessors), Merah (Palm Sunday/Good Friday/Pentecost/Martyrs), Ungu (Advent/Lent).

### The Complete Catholic Canon (73 Books)
- Alkitab Katolik contains **73 Books**:
  * 46 Old Testament: 39 Protocanonical + 7 Deuterocanonical books (Tobit, Judith, 1 Maccabees, 2 Maccabees, Wisdom of Solomon, Sirach, Baruch) + Greek additions to Esther and Daniel (Prayer of Azariah, Song of the Three Holy Children, Susanna, Bel and the Dragon).
  * 27 New Testament.
- Translation standard in Indonesia: Lembaga Alkitab Indonesia & Lembaga Biblika Indonesia (LAI-LBI) Terjemahan Baru (TB / TB2).
- Omitting Deuterocanonical books breaks Catholic liturgical and Breviary references (e.g. Sirach 15 read in the Office of Readings).

---

## 2. Catholic Theological AI Grounding (System Prompt Architecture)

When deploying conversational AI or reflection engines for Catholic theology and scripture exegesis, enforce strict theological guardrails:
1. **Pillars of Catholic Truth**:
   - Sacred Scripture (73 Books)
   - Catechism of the Catholic Church (KGK / CCC)
   - Sacred Tradition & Church Fathers (Patristics: St. Augustine, St. Jerome, St. John Chrysostom, St. Thomas Aquinas *Catena Aurea*)
   - Magisterium & Ecumenical Councils (especially Vatican II *Dei Verbum*, *Sacrosanctum Concilium*, *Lumen Gentium*).
2. **Exegesis Structure for Daily Readings**:
   - **Benang Merah Sabda**: Typological harmony connecting Reading 1, Responsorial Psalm, and Gospel.
   - **Makna Teologis**: Dogmatic and doctrinal commentary anchored in the Catechism.
   - **Renungan Praktis Harian**: Concrete pastoral application for moral and spiritual life.
   - **Doa Penutup**: Heartfelt devotional conclusion.

---

## 3. Liturgical Seasonal Awareness for Devotional Alarms

Devotional alarm schedules must dynamically adapt to the liturgical calendar:
- **Angelus (Doa Malaikat Tuhan)**: Standard hours are 06:00, 12:00, and 18:00.
- **The Eastertide Substitution (Regina Caeli / Doa Ratu Surga)**:
  Throughout the 50 days of Easter (from Easter Sunday through Pentecost Sunday), Catholic rubrics mandate that the Angelus is replaced by the **Regina Caeli**.
  * Rule: Implement an `isEasterSeason()` check. Automatically switch notification titles and prayer texts to Regina Caeli during Eastertide.
- **Divine Mercy Hour (Jam Kerahiman Ilahi)**:
  Triggered at 15:00 (3:00 PM), commemorating the passion and death of Christ on Calvary (Diary of St. Faustina, 1572). Deliver the 3:00 PM prayer and Chaplet of the Divine Mercy (Doa Koronka).

---

## 4. Direct Client AI REST Calls vs Host Proxy Dependency

For zero-budget, mobile-first users:
- **Consumer Google One AI vs Developer API Keys**: Google One AI Premium ($20/mo consumer subscription) does NOT issue developer API tokens for custom mobile applications. Guide users to obtain a free API key from Google AI Studio (`aistudio.google.com`) using their existing Google account.
- **Direct HTTPS REST Execution**:
  Invoke Google Gemini directly from Android Kotlin via `HttpURLConnection` to:
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}`
  This operates completely independent of any local laptop, proxy, or 9router daemon, providing 24/7 autonomous mobile AI at zero hosting cost.

---

## 5. Multi-Category Highlighting & State Merging in Scripture Readers

When users can mark verses under multiple orthogonal categories:
- **Checkpoint (Reading Progress)**: Bright light green (`#86EFAC`, bg `#DCFCE7`, border `#22C55E`).
- **Favorite Verses**: Bright light yellow (`#FDE047`, bg `#FEF9C3`, border `#EAB308`).
- **State Merging**: If an individual verse is both an active Checkpoint and a Favorite, render a blended dual-tone gradient background (`bg_verse_both`).
- **Deep-Link Checkpoint Resume**: Tapping a checkpoint in the list must programmatically select the book, set the chapter spinner, and scroll the RecyclerView directly to the verse index.
