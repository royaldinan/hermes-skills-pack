---
name: music-lead-sheet
description: "Use when creating not angka, lead sheets, or chord PDFs."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [music, not-angka, chord-chart, lead-sheet, pianika, sheet-music, reportlab, pdf]
    category: creative
    related_skills: [pdf, songwriting-and-ai-music]
---

# Music Lead Sheet & Not Angka PDF Skill

Workflow for transcribing, formatting, and generating clean 1–2 page PDF lead sheets combining guitar chords, numbered notation (*not angka* / Jianpu for pianika/vocal), and romanized lyrics with strict column alignment and reliable font rendering.

## When to Use

- Converting sheet music, video tutorial frames, or song chords into printable *not angka* + chord lead sheets.
- Formatting 3-tier musical notation staves: Guitar Chord (top) $\rightarrow$ Not Angka / Scale Degrees (middle) $\rightarrow$ Lyrical Syllables (bottom).
- Building compact 1–2 page play-along guides for melodica, pianika, piano, or guitar.

## Core Rules & Musical Architecture

### 1. Scale Degree & Not Angka Mapping
- **Scale Mapping (C Major / Natural Scale):**
  - $C=1, D=2, E=3, F=4, G=5, A=6, B=7$
  - Rests: `0` (or `.` for syncopated 1/2 beat rests).
  - Sustains / Held notes: `-` (1 beat hold).
  - Measure separators: `|` (bar lines).
- **Octave Indicators:**
  - Standard / Mid Octave (Octave 4: C4–B4): `1 2 3 4 5 6 7`
  - High Octave (Octave 5: C5–B5): `1̇ 2̇ 3̇ 4̇ 5̇ 6̇ 7̇` (combining dot above `U+0307`) or `1' 2' 3' 4' 5' 6' 7'`
  - Low Octave (Octave 3: C3–B3): `1̣ 2̣ 3̣ 4̣ 5̣ 6̣ 7̣` (combining dot below `U+0323`) or `.1 .2 .3`
- **Accidentals (Chromatics):**
  - Sharp / Kruis: `4#` (F#), `5#` (G#), `1#` (C#), `2#` (D#), `6#` (A#) — or slash notation `4/`, `5/`.

### 2. 3-Tier Grid Alignment Architecture (ReportLab Tables)
Never rely on monospaced spaces or tabs to align chords over numbers over lyrics — proportional font rendering and PDF justification cause horizontal text drift.

Instead, build each musical phrase as a borderless ReportLab `Table` where every syllable/measure is an explicit column:
- **Row 0:** Guitar Chords (Bold, vivid purple `#6F2DBD`, ~10pt)
- **Row 1:** Not Angka (Bold dark charcoal `#111111`, ~10.5pt)
- **Row 2:** Lyrics (Regular dark slate `#2B2D42`, ~9pt, hyphenated per syllable)

```python
def make_phrase_row(cols_data, col_widths):
    # cols_data: list of (chord_str, not_str, lyric_str)
    row_chords = [Paragraph(f'<font color="#6F2DBD"><b>{c}</b></font>', chord_style) if c else Paragraph('', chord_style) for c, n, l in cols_data]
    row_nots = [Paragraph(f'<b>{n}</b>', not_style) for c, n, l in cols_data]
    row_lyrics = [Paragraph(l if l else '&nbsp;', lyric_style) for c, n, l in cols_data]
    
    t = Table([row_chords, row_nots, row_lyrics], colWidths=col_widths)
    t.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 0.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t
```

### 3. Font Selection & Diacritic Pitfalls
- **Type 1 Font Failure:** Standard ReportLab `Helvetica` fails to render Unicode combining diacritics (`U+0307` / `1̇`), producing black "tofu" boxes `■`.
- **Solution:** Register a TrueType font that supports combining marks:
  ```python
  from reportlab.pdfbase import pdfmetrics
  from reportlab.pdfbase.ttfonts import TTFont
  pdfmetrics.registerFont(TTFont('SegoeUI', 'C:/Windows/Fonts/segoeui.ttf'))
  pdfmetrics.registerFont(TTFont('SegoeUI-Bold', 'C:/Windows/Fonts/segoeuib.ttf'))
  ```
- **CJK Titles:** Western fonts lack Japanese/Chinese/Korean glyphs (`光るなら` $\rightarrow$ `□□□□`). Keep header titles in clean Romaji/Latin or register a dedicated CJK font (`msgothic.ttc` / `meiryo.ttc`) if CJK characters are required.

### 4. Dynamic Page Numbering
Use a two-pass canvas to compute total page count (`Halaman X dari Y`):
```python
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
```

## Step-by-Step Procedure

1. **Source Inspection & Transcription:**
   - Transcribe measures sequentially from the source (sheet music / video screenshots).
   - Group measures by song structure: `INTRO`, `VERSE`, `PRE-CHORUS`, `CHORUS`, `OUTRO`.
   - Align chords to the exact starting beat/note of each syllable.
2. **Metadata Card Setup:**
   - Include Key signature (e.g. C Major), Tempo (BPM), Time Signature (4/4), Not Angka legend, and Guitar Chord reference list in a top shaded box.
3. **Draft & Compile PDF:**
   - Place `Intro`, `Verse 1`, `Pre-Chorus` on Page 1.
   - Place `Chorus (Reff)`, `Outro`, and Chord Reference Table on Page 2.
4. **Visual Verification Loop:**
   - Render PDF pages to PNG using PyMuPDF (`pix = page.get_pixmap(dpi=150); pix.save(...)`).
   - Call `vision_analyze` on each page image to check:
     - Vertical alignment of chords $\leftrightarrow$ notes $\leftrightarrow$ lyrics.
     - Absence of tofu boxes (`■` or `□`).
     - Balanced vertical margins and whitespace.
