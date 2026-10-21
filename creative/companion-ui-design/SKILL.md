---
name: companion-ui-design
description: Use when designing companion or anime assistant UIs.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ui, design, companion, anime, assistant, frontend, html, css, responsive]
    related_skills: [claude-design, popular-web-designs, cross-device-local-app]
---

# Companion & Anime Assistant UI Design

Use this skill when designing, overhauling, or enhancing user interfaces for companion apps, anime-themed assistants, or lifestyle productivity dashboards. It guides the creation of emotionally resonant, warm, and tactile interfaces while maintaining professional structural rigor.

## Core Principle: Emotional Persona Matching

Standard developer tools and dashboards default to cold dark-slate or void-black palettes (`#08090d`, `#0a0c12`) with tech-indigo accents. For companion and anime assistant applications, this creates a sterile, stiff, and impersonal experience ("AI slop").

A companion interface must reflect warmth, care, and presence:
- **Canvas:** Warm cream / peach-tinted ivory (`#fff1eb`, `#fff5f0`).
- **Surfaces & Cards:** Frosted rose-white panels (`rgba(255, 255, 255, 0.9)` to `#fff0f3`) with delicate rose borders (`rgba(244, 114, 182, 0.25)`).
- **Typography:** High-contrast espresso plum (`#2b1320`) for primary text, warm mauve/slate (`#6e465a`) for secondary text.
- **Accents:** Sakura rose (`#fb7185`, `#f43f5e`), soft blush (`#fbcfe8`), and warm glow highlights.
- **Micro-Interactions:** Tactile keycaps, subtle elevation shadows, and smooth spring transitions.

## Workflow

### 1. Research & Design Intent
- Identify the persona's emotional tone and core user tasks.
- Avoid jumping directly to minor visual tweaks. Establish a clear design direction (palette, card elevation, typography, and layout archetype).

### 2. Layout & Surface Structure
- **Command Deck / Overview:** Keep essential status metrics and quick controls glanceable at the top.
- **Visual Novel Chat Studio:** For companion dialog, structure messages with distinct visual identity:
  - Companion bubbles: Soft cream/rose frosted card with character badge, subtle border, and cozy dialogue styling.
  - User bubbles: Saturated rose/accent pill with crisp white text for clear role separation.
  - Header & Footer: Maintain seamless color continuity with the active theme; do not leave hard black bars.
- **Surveillance / Hardware Cockpit (Monitor Surface):**
  - Keep camera/video feeds 100% unobstructed. Place stream labels, clocks, and telemetry status on an external bar above or below the video container.
  - For fullscreen mode, provide both native Fullscreen API and CSS overlay fallbacks, always including a visible floating exit button for mobile users.

### 3. Mobile Responsiveness (360px–412px Viewports)
- **Button Grids:** Desktop 4-column or 5-column action grids must wrap to 2 columns on mobile (`grid-cols-2 sm:grid-cols-4`) to prevent label truncation.
- **Card Action Rows & Anti-Overflow (<400px)**:
  - Never place 3+ labeled action buttons in a bare horizontal row (`flex items-center gap-2`). On viewports under 400px, buttons push past card borders.
  - Use a 2-tier responsive pattern: prominent full-width primary button on top, followed by a 2-column symmetric grid (`grid grid-cols-2 gap-2`) for secondary actions (e.g. Download, Share/WA), with text `truncate`.
- **Remote Control & Visual Feedback Layout Hierarchy**:
  - When designing remote monitoring dashboards, arrange cards so the active touch control surface sits immediately below its corresponding visual display (e.g. Live Screen above -> Touchpad directly below) to prevent vertical scrolling during interaction.
- **Bottom Navigation Bar:** Ensure fixed bottom navbars adopt the warm theme's background blur and border colors, rather than defaulting to pitch black.
- **Viewport Clearances:** Add adequate bottom padding (`pb-24` on mobile) to main content containers so fixed bottom bars never obscure controls or task lists.

### 4. DOM & API Contract Preservation
When redesigning an existing web application:
1. Extract and inventory all existing DOM IDs and event listener targets before editing markup.
2. Verify that 100% of functional IDs survive the redesign (form inputs, toggle buttons, modal IDs, telemetries).
3. Confirm that inline scripts or external JS selectors match the new HTML structure.

### 5. Verification
- Validate inline scripts with a JS syntax checker (e.g. `node -c`).
- Audit DOM IDs against the pre-redesign inventory.
- Test server responses for static assets and API endpoints (`GET /`, `GET /api/...`).

## Pitfalls

- **Do not default to cold pitch-black palettes for companion apps.** Pitch-black developer themes feel cold and stiff for companion or anime personas; use warm cream, frosted rose-white, and plum typography.
- **Do not overlay telemetry text inside video streams.** Video feeds must remain clean; position telemetry bars outside the stream container.
- **Do not rely solely on keyboard ESC for fullscreen exit.** Mobile and touch devices lack an ESC key; always render a floating exit button.
- **Do not use 4+ column button grids on mobile.** Screens under 420px will truncate button text; use responsive 2-column breakpoints.
- **Do not place 3+ labeled action buttons horizontally inside mobile cards.** On screens under 400px, horizontal button rows overflow borders and clip; use a 2-tier layout or a 2-column responsive grid with `truncate`.
- **Do not separate visual feed cards from their direct touch controllers.** Placing live screen displays and virtual touchpads in disconnected decks forces jarring scroll navigation.
- **Do not break DOM element IDs during visual overhauls.** A cosmetic rewrite that renames or drops IDs breaks client-server event bindings.
- **Do not use light pastel text classes on white/cream keycaps.** Classes like `text-rose-300` or `animate-pulse` wash out against warm cream and white gradient button surfaces, appearing pure white and illegible; explicitly style buttons with dark contrast (`text-neutral-900` or `#2b1320`).
- **Do not use loose CSS attribute substring selectors for theme text color overrides.** Writing rules like `body.theme-cream [class*="bg-rose-500"] * { color: #ffffff !important; }` accidentally captures buttons with hover classes (`hover:bg-rose-500/10`) or indicator dots, forcing button text to white-on-white. Always use exact class selectors (e.g. `.bg-rose-500:not(.keycap-btn):not([class*="/"]) *`).
