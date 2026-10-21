---
name: brand-identity
description: Use when designing logos, brand kits, and visual assets.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [branding, logo, brand-kit, visual-identity, svg, design-system, vector, anti-slop]
    related_skills: [claude-design, popular-web-designs, design-md]
---

# Brand Identity & Logo System Skill

Use this skill when tasked with creating or refining a brand identity, logo, brand-kit presentation board, app launcher icon, or vector brandmark. Inspired by elite identity studios and the Leonxlnx `taste-skill` anti-slop principles.

## Core Principle: Strategic Unity Over Clipart Collage

A great logo is not a decoration or a collage of literal icons. It is a visual argument:
- **Never slap disjointed symbols together**: E.g., do not paste cartoon flames behind a shield or glue a padlock on top of a circuit board.
- **Mandatory Real-World Reference Protocol**: When designing or replicating real-world corporate brands, banks, or partner platforms, NEVER extrapolate from memory or invent geometries. Mandatory to search external official media kits, brand guidelines, or inspect user-provided reference photos. Guessing from memory generates counterfeit-looking vectors that instantly break user trust.
- **Corporate Parent vs. Subsidiary Brand Disambiguation**: Subsidiaries within the same parent conglomerate (e.g., SeaBank vs. ShopeePay under Sea Limited) often share brand colors (e.g. orange hues `#EA5F00` / `#EE4D2D`) and identical initial letters ("S"). Always verify exact entity-level iconography against official app stores or Wikimedia master SVG files before mapping them into vector assets: SeaBank = Sun/coin + blue ocean waves (Sea + Bank); ShopeePay = folded leather wallet + "Pay" wordmark.
- **The "Letter + Orbit + Dot" AI Fintech Slop Ban & Category DNA**: Do not slap a circle with a generic letter and a thin orbital swoosh ending in a planetary dot. That is an overused AI crypto cliché. Furthermore, never deliver a plain letterform alone (e.g., "jangan F gitu doang"). A financial app brandmark must integrate authentic domain DNA (such as an ascending 3-bar capital growth staircase, a 45° bullish market breakout vector, or architectural ledger vaults) rather than looking like an uninspired AI font rendering.
- **Enforce Total Unity (Kesatuan Bentuk)**: The contour of the primary shape must flow organically into the secondary metaphor (e.g., the top crest of the shield forms the shackle of the lock; the right wing tapers into an aerodynamic kinetic blade).
- **Embrace Negative Space**: Carve secondary meaning (monograms, data nodes, apertures, keyholes) out of the solid geometry rather than adding more visual elements.
- **Maximum 2 metaphors fused**: (Shield + Flame, Vault + Wing, Compass + Monogram). Adding 3+ distinct shapes creates visual clutter and fails the 16px scalability test.

---

## 5-Part Deliverable Suite

Whenever creating a complete brand identity for a project or hackathon submission, deliver these 5 synchronized assets:

1. **Standalone Emblem (Logo Mark)**:
   - Clean geometric symbol without typography.
   - Must scale down to 16×16 px (browser favicon / status bar) and up to billboard proportions.
   - Formats: SVG and high-res PNG on solid/transparent background.

2. **Primary Horizontal Lockup**:
   - Standalone emblem on the left + refined wordmark on the right.
   - Wordmark in high-contrast geometric grotesque sans-serif (e.g. Monument, Cabinet Grotesk, Inter) with generous letter-spacing (kerning 4–8px).
   - Subtitle / Value Proposition in secondary muted sans-serif + monospace metadata tags for tech credibility.
   - Ideal for: pitch deck headers, proposal document covers, GitHub repo banners.

3. **Adaptive Mobile App Icon (Squircle)**:
   - Android standard 512×512 px with 115px corner radius.
   - Centered mark with subtle elevation/glow and disciplined dark or brand-tinted matte background.

4. **Monochrome / Silhouette Variant**:
   - Pure white `#FFFFFF` or single-color solid fill.
   - Essential for dark mode slides, laser etching, lanyard badges, and single-color print.

5. **Brandkit Presentation Board**:
   - A modular presentation grid (3×3 or 5×3) showcasing the entire brand ecosystem:
     * Logo Mark & 3D bevel render
     * Blueprint construction geometry (circles, 45° angles, alignment grids)
     * Digital applications (mobile app UI, status alerts, notification cards)
     * Brand essence / primary tagline
     * Color system swatches with Hex codes & semantic roles
     * Typography pairing specimen
     * Physical touchpoint mockups (matte lanyard badge, keytag, card)
     * Atmospheric brand imagery reinforcing the core metaphor.

---

## Color Discipline (Anti-Slop Palettes)

Avoid generic rainbow gradients or unearned neon washes. Use a disciplined 4-token system:

| Token | Role | Recommended Tech/Security Values |
|---|---|---|
| **Base / Canvas** | Dark base, quiet backdrop | Obsidian `#07090E`, Void `#0B0F19`, Deep Charcoal `#111827` |
| **Primary Armor** | Trust, system core, structural plate | Electric Cobalt `#2563EB`, Cyber Azure `#0EA5E9`, Royal `#1D4ED8` |
| **Kinetic Accent** | Energy, active intercept, alert, speed | Solar Amber `#F59E0B`, Flame Orange `#EA580C`, Blaze `#FF5500` |
| **Beacon / Signal** | Illuminated core, verification dot | Laser Cyan `#38BDF8`, Platinum `#F8FAFC`, Mint `#10B981` |

Rules:
- 80% canvas & neutrals, 15% primary structural tone, 5% kinetic accent.
- Never use more than two high-chroma accent colors simultaneously.

---

## Execution Workflow

1. **Infer Brand DNA & Competitive Positioning**:
   - Read project brief/proposal for: Category, Audience, Core Action, and Cultural Stance.
   - Identify the primary metaphor (e.g., Bulwark = impenetrable barrier + real-time packet drop).

2. **Draft Geometric Vector in Code (SVG)**:
   - Use standard `<path>`, `<rect>`, and `<circle>` with consistent stroke weights and 45°/60° bevel cuts.
   - Use `<linearGradient>` with matching light-source angles (e.g. top-left to bottom-right).
   - Test silhouette readability by converting to pure solid fill.

3. **Generate Visual Brandkit Board**:
   - Use `image_generate` with the disciplined prompt structure:
     `"A premium brand-kit overview board for [Brand] in modular grid layout on [dark/light] background. Panels: main emblem, construction blueprint, mobile UI mockup, tagline, color swatches, typography specimen, physical badge, atmospheric scene. Minimalist, intentional, vector art, high contrast."`
   - Save output image directly into the user's project directory.

4. **Build Interactive HTML Showcase**:
   - Create a single-file `Brand_Identity.html` containing live SVG embeds, color cards, font specimens, interactive UI mockup alert, and download buttons.
   - Ensure the user can double-click and open it in any standard browser.

---

## Pitfalls & Lessons

- **Optical Balance of S-curves (The Top-Heavy Inversion Trap)**: In typography and monoline icon marks, an "S" must never be top-heavy. The lower bowl must always be noticeably wider, deeper, and better grounded than the upper bowl (e.g. upper span 16px, lower span 20px). An oversized upper bowl violates visual gravity and creates an unmistakable optical illusion that the character is upside-down or inverted.
- **Negative-space slits vs. harsh stroke artifacts**: When representing layered folds, card slots, or wallet flaps on dark-mode containers, never draw a hard white `stroke="#FFFFFF"` line unless the entire icon sits on a white canvas. On dark backgrounds, a white stroke renders as an unnatural glowing scar that visually severs the icon in half. Use negative-space cutouts or a natural darker shadow tone (e.g. a 15% deeper shade of the base leather/fill).
- **Kerning and bounding box clearance in wordmarks**: When crafting custom vector lettering (e.g. "Pay"), calculate explicit horizontal bounding boxes for each glyph. Never allow adjacent paths to collide or overlap (e.g., the bowl of 'P' crashing into 'a'); enforce a strict 3.5–4.5px clearance buffer between glyph boundaries.
- **Micro-cutout geometric integrity (Keyholes & Apertures)**: Hand-traced or freehand beziers for small cutouts (like keyholes or notches) look lumpy and distorted. Construct them via exact geometric primitives: a true circle (`<circle>`) fused with a symmetrical trapezoid and a rounded semicircular bottom cap.
- **Flap and hinge orientation verification**: When rendering bifold wallets or folding cardholders, verify the physical hinge: the solid fold/spine connects on the left, and the opening flap slopes/tapers upward toward the right. Reversing this flips the physical metaphor and destroys brand fidelity.
- **Never hand-approximate corporate partner SVG paths from visual memory**: Hand-tracing or guessing bezier curves for well-known trademarks (like bank or e-wallet logos) results in distorted, unrecognizable shapes (such as an "S" looking like a number "2", or wrong flap creases). Fetch the verified corporate master SVG directly (from Wikimedia Commons, official developer portals, or extracted APK vector drawables) and normalize viewports/translations cleanly.
- **Provide candid, blunt visual discrepancy reports**: When visual bugs or swapped brand assets occur, report the root cause and official specifications directly and transparently without defensive phrasing or artificial flattery.
- **Do not rely on browser harnesses to preview local HTML/SVG**: Browser automation tools (e.g. `browser-use`, CDP) often block `file:///` and internal loopback (`127.0.0.1`, `localhost`) to prevent SSRF. To verify generated visual assets, inspect the image files directly on disk or analyze them with vision tools.
- **Optical center vs. mathematical center**: Logos with asymmetric kinetic elements (e.g. ascending flame on one side) have an optical center shifted away from the geometric bounding box center. Shift the emblem manually by 4–8% along the X/Y axis so it appears visually centered.
- **Keep wordmark typography clean**: Never apply bevels or 3D extrusions to the text wordmark. The mark can have subtle depth, but the accompanying wordmark must remain razor-sharp, flat, and legible.
- **Provide clean production paths**: Always output native SVG files into the user's target folder alongside any AI-rendered mockups so the team has production-ready vector assets for Figma, Canva, and IDE drawable resources.
