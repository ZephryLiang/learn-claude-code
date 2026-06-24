---
name: Resume AI Editor
description: AI-powered resume workspace for job seekers
colors:
  primary: "#2b7a4b"
  primary-hover: "#23663e"
  primary-muted: "oklch(70% 0.1 155 / 0.15)"
  neutral-bg: "oklch(14% 0.005 160)"
  neutral-surface: "oklch(18% 0.006 160)"
  neutral-raised: "oklch(21% 0.008 160)"
  neutral-border: "oklch(27% 0.008 160)"
  neutral-text: "oklch(88% 0.005 160)"
  neutral-muted: "oklch(65% 0.008 160)"
  neutral-dim: "oklch(45% 0.006 160)"
  danger: "oklch(58% 0.18 25)"
  warning: "oklch(68% 0.14 85)"
  info: "oklch(60% 0.12 255)"
typography:
  body:
    fontFamily: "'Inter', 'SF Pro', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  code:
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace"
    fontSize: "13px"
  label:
    fontFamily: "'Inter', 'SF Pro', -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    letterSpacing: "0.02em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "10px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.neutral-muted}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  input:
    backgroundColor: "{colors.neutral-surface}"
    textColor: "{colors.neutral-text}"
    borderColor: "{colors.neutral-border}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  card:
    backgroundColor: "{colors.neutral-raised}"
    rounded: "{rounded.md}"
    borderColor: "{colors.neutral-border}"
    padding: "12px"
  modal:
    backgroundColor: "{colors.neutral-raised}"
    rounded: "{rounded.lg}"
    borderColor: "{colors.neutral-border}"
  header:
    height: "48px"
    backgroundColor: "{colors.neutral-bg}"
    borderColor: "{colors.neutral-border}"
---

# Design System: Resume AI Editor

## 1. Overview

**Creative North Star: "The Nail"**

A precision tool for career craftsmanship. Every pixel is deliberate, every interaction purposeful — like a master tradesperson reaching for the right tool. The workspace is dark, focused, and unintimidating: a dim workshop where the task at hand is the only thing that matters.

This system explicitly rejects: dated enterprise clutter (heavy borders, crowded toolbars), minimal SaaS platitudes (giant metrics, generic gradients), and the cookie-cutter AI aesthetic (purple neon, glassmorphism, sparkle icons). Instead, it carries the authority of a well-organized workbench — professional without being stiff, sharp without being cold, informed by a restrained green palette that signals growth and confidence rather than dashboard-neutrality.

**Key Characteristics:**
- Dark-anchored but warm — Deep surfaces with subtle green tint, not pure gray
- Typographic hierarchy — Small but mighty: compact UI with clear size/weight contrast
- Intentional color — Green as a signal of action and growth, used sparingly for maximum impact
- Precision spacing — Tight rhythm with deliberate breathing room between sections
- Substance over chrome — No decorative gradients, no glass effects, no gratuitous animation

## 2. Colors: The Viridian Edge

A green-anchored dark palette. The green is a professional viridian — not emerald-bright, not olive-muddy — that reads as growth, confidence, and execution. Neutrals carry a microscopic green lean (chroma 0.005–0.008) to harmonize with the accent without looking tinted.

### Primary
- **Viridian** (oklch(58% 0.16 165) / #2b7a4b): Primary action color. Used for buttons, active states, and link text. Its muted saturation keeps it professional, not playful.
- **Viridian Deep** (oklch(50% 0.15 165) / #23663e): Hover and active states for primary actions.
- **Viridian Glow** (oklch(70% 0.10 155 / 0.15)): Subtle background tint behind selected items, focus rings, and success callouts.

### Neutral
- **Workshop Floor** (oklch(14% 0.005 160)): Base surface — the deepest background. Near-black with a whisper of green.
- **Workbench** (oklch(18% 0.006 160)): Elevated surface — cards, panels, sidebar.
- **Raised Surface** (oklch(21% 0.008 160)): Interactive elements — buttons, inputs, dropdowns.
- **Edge** (oklch(27% 0.008 160)): Borders and dividers. Present but not demanding.
- **Steel** (oklch(45% 0.006 160)): Muted icons, placeholder text, disabled content.
- **Silver** (oklch(65% 0.008 160)): Secondary text, metadata, labels.
- **Bright** (oklch(88% 0.005 160)): Primary text. High contrast, warm-toned white.

### Semantic
- **Danger** (oklch(58% 0.18 25)): Errors, destructive actions, warnings that demand attention.
- **Warning** (oklch(68% 0.14 85)): Amber for caution states.
- **Info** (oklch(60% 0.12 255)): Informational accents, assessment indicators.

### Named Rules
**The Rarity Rule.** Primary green appears on ≤15% of any given screen. Its scarcity is what makes it read as a signal. If everything is green, nothing is.

## 3. Typography

**Body Font:** Inter, SF Pro, –apple-system, BlinkMacSystemFont, sans-serif
**Code/Mono Font:** JetBrains Mono, Fira Code, monospace
**Label Font:** Inter (500 weight, 0.02em letter-spacing)

**Character:** Precise and efficient — the typography of a well-designed tool. No display faces, no decorative weights. Hierarchy is achieved through deliberate size steps and weight contrast rather than font switching.

### Hierarchy
- **Title** (600 weight, 14px, 1.4 line-height): Panel headings, section titles. Only text at this size gets medium-bold weight.
- **Body** (400 weight, 14px, 1.6 line-height): Primary reading size for content areas, AI analysis output, and form labels.
- **Code** (400 weight, 13px, 1.5 line-height): LaTeX source, error messages, structured output. JetBrains Mono for legibility at small sizes.
- **Label** (500 weight, 12px, 0.02em letter-spacing, uppercase): Small labels, tab text, metadata, button text. The extra letter-spacing gives it an engineered feel.
- **Caption** (400 weight, 11px, 1.4 line-height): Timestamps, secondary metadata, helper text. The smallest size; used sparingly.

### Named Rules
**The 12px Shelf.** Labels and tabs sit at 12px. Body text at 14px. These two sizes carry 90% of the UI. The jump from 12→14 (1.17 ratio) with a weight shift (500→400) provides clear hierarchy without a sprawling scale.

## 4. Elevation

Dark-anchored, flat-by-default, selectively lifted. Depth is conveyed through **tonal layering** (background lightness steps) rather than shadows. The surface hierarchy is implicit in the palette:

- Workshop Floor (14% lightness): deepest background
- Workbench (18%): cards and panels
- Raised Surface (21%): interactive controls

Shadows, when used, are reserved for transient overlays only:

- **Modal Overlay** (`0 16px 48px oklch(0% 0 0 / 0.4)`): For modal dialogs and dropdown menus. The only surface that casts a real shadow.
- **Hover Lift** (`0 2px 8px oklch(0% 0 0 / 0.2)`): Optional micro-lift on clickable cards. Use sparingly — tonal highlighting is preferred.

**The Flat-By-Default Rule.** Surfaces at rest are flat. Shadows appear only for transient states (hover, focus, modal). If a surface needs to stand out, lighten its background — don't throw a shadow on it.

## 5. Components

### Buttons
- **Shape:** Clean rects with gentle rounding (6px). No pill shapes, no heavy borders.
- **Primary:** Viridian background (#2b7a4b), white text (13px, 500 weight, 0.01em spacing). Hover deepens to Viridian Deep (#23663e). Active press at 90% scale for tactile feedback. 32px height.
- **Ghost / Secondary:** Transparent background, Silver text. Hover fills to Workbench background + Bright text. For non-primary actions and toolbar items.
- **Danger:** Red background. For destructive confirmations. Same shape as primary.

### Tabs
- **Structure:** Bottom-border indicator. Active tab gets a 2px Viridian strip + Bright text. Inactive tabs are Dim text with no border.
- **Height:** 40px tab bar with comfortable padding (12px horizontal per tab).
- **States:** Hover fades inactive text to Silver. A pulsing dot indicates loading state for AI-powered tabs.

### Cards / Containers
- **Treatment:** Workbench background, Edge border (1px), 6px radius. No shadow at rest.
- **Internal Padding:** 12px (comfortable for compact content), 16px (for text-heavy analysis output).
- **States:** Selected cards swap to Viridian Glow background tint + Viridian border.

### Inputs / Textareas
- **Style:** Raised Surface background, Edge border (1px), 6px radius. Internal padding 8px vertical × 12px horizontal.
- **Focus:** Viridian Glow border — the green glow replaces the border color, no additional ring. Inset trace of light.
- **Placeholder:** Steel text color. Keeps the field looking filled-in, not empty.
- **Disabled:** Reduced opacity to 40%, no border change.

### Monaco Editor (LaTeX)
- **Theme:** "vs-dark" custom — map the dark surface colors to editor chrome. Green accent for LaTeX commands. Dim for comments.
- **Padding:** 12px top padding for breathing room.
- **Minimap:** Disabled by default (consistent with current behavior).

### Dropdown / Select
- **Trigger:** Ghost button style. Chevron icon (lucide `chevron-down`) as the affordance.
- **Menu:** Raised Surface background, Edge border, 6px radius, 4px internal padding. Items are 32px tall with 8px horizontal padding.
- **Item states:** Hover fills the item row with Viridian Glow tint. Active/selected item gets a Viridian dot indicator.

### Modal
- **Overlay:** 60% opacity black. No blur (keeps context visible).
- **Dialog:** Raised Surface background, Edge border, 10px radius, 24px padding. 480px max-width. Shadow cast under Modal Overlay rules.

### Named Rules
**The 32px Rhythm.** Buttons, input fields, dropdown items, and tab bar all share a 32px height. The consistency makes the UI feel engineered rather than assembled.

## 6. Do's and Don'ts

### Do:
- **Do** use Viridian green sparingly (≤15% per screen) — its rarity signals action and focus.
- **Do** use tonal layering (lightness steps) over shadows for surface hierarchy.
- **Do** keep buttons at 32px height with consistent padding — the "32px Rhythm" rule.
- **Do** use 12px labels with uppercase + letter-spacing for navigation and metadata hierarchy.
- **Do** show AI reasoning — the "知其所以然" principle means outputs must explain why.
- **Do** tint neutrals toward green (chroma 0.005–0.008) even when they look gray.

### Don't:
- **Don't** use dated enterprise patterns — heavy borders, cluttered toolbars, gray table stripes.
- **Don't** use over-minimalist "SaaS template" tropes — giant hero metrics, generic gradients, Inter-default with no character.
- **Don't** use cookie-cutter AI aesthetics — purple gradients, glassmorphism, sparkle icons, neon on black.
- **Don't** use side-stripe borders (border-left > 1px as a colored accent on cards or list items).
- **Don't** animate CSS layout properties (width, height, top, left, margin, padding).
- **Don't** use pure #000 or #fff — tint every dark/light extreme toward the brand hue.
- **Don't** wrap everything in a container card — nested cards are always wrong.
- **Don't** default to a modal — exhaust inline and progressive disclosure alternatives first.
