# UI/UX Design Document

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 5 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document defines the visual and interaction design of Themis Machina: the design system (color, typography, spacing), the screen layouts, the component library, the interaction patterns, and the accessibility considerations.

It is the visual rendering of the flows specified in **Document 4 (App Flow & User Journey)**. Where Document 4 specifies what happens, this document specifies what it looks like and how it feels.

This is not a Figma file or a code-level component spec — those are deliverables of Phase 8 (production frontend build). This document specifies the design intent and the constraints downstream design work must respect.

---

## 2. Design Philosophy

Six principles shape every visual and interaction decision in Themis Machina:

1. **Trust by signal, not by claim.** Saying "this is reliable" is meaningless; demonstrating reliability through citation visibility, tier badges, source previews, and uncertainty signals builds actual trust. The UI's job is to make the system's discipline visible.

2. **Calm density.** Legal users (the Professional persona) want a lot of information visible without feeling overwhelmed. The design is information-dense but visually quiet — not minimalist (which loses context) and not crowded (which fatigues).

3. **The conversation is the product.** The chat surface is the primary interface, not a sidebar feature. Everything else (sidebar, citation panel, mode selector, matters) supports the conversation.

4. **Citations are first-class UI.** Citation pills, source previews, and the citation viewer are designed with the same care as the chat itself. A citation that's hard to click or read undermines the whole trust contract.

5. **Mode-aware, persona-aware.** The same interface adapts to who's using it. Public mode is warmer and more spacious; Professional mode is denser and more precise; Patent mode is structured and technical.

6. **Designed for the demo.** As a portfolio project, the UI is one of the first things a hiring manager sees. The design must read as a *real product*, not a Streamlit script. Polish matters disproportionately at this stage.

---

## 3. Design System

### 3.1 Brand identity

**Project name:** Themis Machina (full), Themis (short / in-conversation).

**Wordmark:** A simple wordmark — `Themis Machina` set in the serif typeface for the brand, with a small visual mark to its left.

**Logo mark concept:** A minimalist symbol drawing from Themis iconography — a stylized scale (the symbol Themis holds, representing weighing of evidence) rendered as two thin horizontal lines balanced on a central pivot. Not a literal scale illustration; abstract enough to feel modern.

**Color brand role:** The mark and brand wordmark use the primary deep navy color (defined below). The brand stays restrained — never decorative.

### 3.2 Color system

The color palette is deliberately limited. Legal interfaces over-using color feel toy-like; restraint signals seriousness.

#### Primary palette (the "Themis blue")

| Token | Hex | Use |
|---|---|---|
| `themis-900` | `#0B1730` | Brand wordmark, hero text, primary CTA on light backgrounds |
| `themis-800` | `#142547` | Headings, navigation |
| `themis-700` | `#1F3563` | Hover states for primary text |
| `themis-600` | `#2D4880` | Links, active mode badge |
| `themis-500` | `#4A6BAA` | Secondary text on dark backgrounds |
| `themis-100` | `#E8EEF8` | Background tints, citation pill background |
| `themis-50`  | `#F5F7FB` | Page background tint |

#### Neutral palette

| Token | Hex | Use |
|---|---|---|
| `gray-950` | `#0A0A0B` | Primary text on light backgrounds |
| `gray-800` | `#27272A` | Body text |
| `gray-600` | `#52525B` | Secondary text |
| `gray-400` | `#A1A1AA` | Disabled, placeholder |
| `gray-200` | `#E4E4E7` | Borders, dividers |
| `gray-100` | `#F4F4F5` | Card backgrounds |
| `gray-50`  | `#FAFAFA` | Page background |
| `white`    | `#FFFFFF` | Card, panel backgrounds |

#### Semantic colors

| Token | Hex | Use |
|---|---|---|
| `success-600` | `#16803C` | Verified citation badge, "Document ready" state |
| `success-50`  | `#ECFDF3` | Success background |
| `warning-600` | `#B54708` | "Review" risk flag on contract clauses |
| `warning-50`  | `#FFF6ED` | Warning background |
| `danger-600`  | `#B42318` | High-risk flag, unsupported citation warning, refusal accent |
| `danger-50`   | `#FEF3F2` | Danger background |
| `info-600`    | `#175CD3` | Informational notices, "consult a lawyer" callouts |
| `info-50`     | `#EFF8FF` | Info background |

#### Citation tier colors

Citation pills are color-coded by source tier. The color is *subtle* (a thin left border + a dot), not saturated, to avoid visual noise.

| Tier | Token | Visual treatment |
|---|---|---|
| Tier 1 — Primary authority | `tier-1: themis-600` | Solid filled pill, white text |
| Tier 2 — Official secondary | `tier-2: info-600` | Outline pill, dark text, blue accent |
| Tier 3 — Curated commentary | `tier-3: gray-600` | Outline pill, gray accent |
| Tier 4 — General web | `tier-4: gray-400` | Outline pill, dimmed, "web" label visible |

#### Dark mode

A dark mode is supported. The token mapping inverts (light backgrounds become dark; dark text becomes light). Brand color shifts slightly toward `themis-500` for better contrast on dark backgrounds. Both light and dark mode pass WCAG 2.1 AA contrast requirements.

### 3.3 Typography

Two typefaces, both available via Google Fonts (free, fast):

**Sans:** Inter (variable). Used for UI, body text, citations.

**Serif:** Source Serif Pro (variable). Used for the brand wordmark, hero headings, and long-form generated content (which reads better in serif at length).

**Mono:** JetBrains Mono. Used for code blocks, exact citations being shown verbatim, and patent claim numbers.

**Type scale:**

| Token | Size / Line height | Weight | Use |
|---|---|---|---|
| `display` | 48 / 56 | 600 | Landing page hero only |
| `h1` | 32 / 40 | 600 | Page titles |
| `h2` | 24 / 32 | 600 | Section headings |
| `h3` | 20 / 28 | 600 | Sub-sections |
| `body-lg` | 17 / 28 | 400 | Generated answer text (public mode) |
| `body` | 15 / 24 | 400 | Default body, generated answer (professional mode) |
| `body-sm` | 13 / 20 | 400 | Captions, metadata, citation pill text |
| `body-xs` | 11 / 16 | 500 | Source tier badges, tags |

**Reading typography rules:**

- Generated answers in **public mode** use `body-lg` for easier reading
- Generated answers in **professional mode** use `body` for higher information density
- Patent mode uses `body` with monospaced fragments for claim references
- Long-form content uses Source Serif Pro to reduce reading fatigue
- All UI chrome (buttons, labels, navigation) uses Inter

### 3.4 Spacing system

8-point grid. Tokens:

| Token | px |
|---|---|
| `space-1` | 4 |
| `space-2` | 8 |
| `space-3` | 12 |
| `space-4` | 16 |
| `space-5` | 24 |
| `space-6` | 32 |
| `space-8` | 48 |
| `space-10` | 64 |
| `space-12` | 96 |

Component padding defaults to `space-4`; section spacing to `space-6`; major page sections to `space-10`.

### 3.5 Elevation and depth

The design uses minimal shadow — preferring borders for separation. Only three elevation levels:

| Token | Use |
|---|---|
| `elevation-0` | Flat — page surface, panels |
| `elevation-1` | Cards and citation popovers — `0 1px 3px rgba(11, 23, 48, 0.08)` |
| `elevation-2` | Modals, dropdowns — `0 8px 24px rgba(11, 23, 48, 0.12)` |

Borders use `gray-200` at 1px width as the default separator.

### 3.6 Radius

Soft, restrained corner radii:

| Token | px | Use |
|---|---|---|
| `radius-sm` | 4 | Citation pills, small badges |
| `radius-md` | 8 | Inputs, buttons, small cards |
| `radius-lg` | 12 | Cards, panels |
| `radius-xl` | 16 | Modals, hero containers |
| `radius-full` | 999 | Round avatars and floating buttons |

### 3.7 Iconography

Single icon library: **Lucide** (open source, MIT, comprehensive). Icons are 20px in chrome and 16px in citation pills.

The system never uses emoji as UI iconography. Emoji can appear in user content only.

### 3.8 Motion

Restrained motion. Only three animation patterns:

- **Stream-in:** generated text appears token-by-token; cursor blinks during generation
- **Fade-in:** new components appear with a 150ms opacity transition
- **Slide:** side panels open/close with a 200ms ease-out slide

No bounces, no spinners with personality, no celebratory confetti. The product is a serious tool.

---

## 4. Layout System

### 4.1 The four primary layouts

| Layout | Pages |
|---|---|
| **Landing** | Home, About, How it works, Pricing-equivalent (free) |
| **Auth** | Sign in, Sign up, Password reset, Verify |
| **Chat** | The main research interface (the bulk of the product) |
| **Settings** | Account, Privacy, Data export, Mode preferences |

### 4.2 Chat layout — the main canvas

The chat layout is the workhorse. It is organized as a three-pane structure:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Header (mode badge, matter title, user menu)                        │
├──────────┬──────────────────────────────────────┬───────────────────┤
│          │                                      │                   │
│          │                                      │                   │
│  Side    │                                      │   Source          │
│  bar     │       Chat                           │   Panel           │
│          │       (conversation)                 │                   │
│  -       │                                      │                   │
│  Matters │                                      │                   │
│  -       │                                      │                   │
│  Modes   │                                      │                   │
│  -       │                                      │                   │
│  Docs    │                                      │                   │
│          │                                      │                   │
│          │                                      │                   │
│          ├──────────────────────────────────────┤                   │
│          │   Composer (text input + actions)    │                   │
└──────────┴──────────────────────────────────────┴───────────────────┘
```

**Sidebar (left):** 280px wide. Collapsible to a 64px icon rail.
**Chat column (middle):** flex, 600–900px wide.
**Source panel (right):** 360px wide. Collapsible to closed state.

On narrower screens (< 1280px), the source panel collapses by default and opens as an overlay when a citation is clicked.

### 4.3 Responsive behavior

| Breakpoint | Behavior |
|---|---|
| > 1440px | Full three-pane layout, all panels visible |
| 1280–1440px | Three panes, source panel collapsible |
| 1024–1280px | Sidebar collapses to icon rail; source panel becomes overlay |
| 768–1024px (tablet) | Sidebar becomes drawer; source panel becomes modal |
| < 768px (mobile) | Single-column chat; sidebar and source panel are drawers/modals; composer becomes sticky bottom |

Mobile is supported but not optimized for v1.0. The product is primarily a desktop/tablet tool because legal research is rarely done on phones.

### 4.4 Landing page layout

A simple, narrow-column layout (max 720px wide for text content) with restrained hero imagery.

Structure:

1. **Header** (logo + sign-in button) — sticky
2. **Hero** — one-line proposition + sub-line + primary CTA
3. **What it does** — three columns: Research, Patents, Documents
4. **What it's not** — explicit "this is research, not advice" framing
5. **Example queries** — three example query → answer snippets
6. **How it works** — three-step graphic (Ask, Retrieve, Cite)
7. **Tech and methodology** — link to README and design docs (portfolio signal)
8. **Footer** — minimal: about, privacy, terms, github link

The "What it's not" section is unusual but intentional — it sets expectations honestly, which builds trust and reduces refusal-triggered frustration later.

---

## 5. Core Components

### 5.1 Composer (chat input)

The composer is where the user types. It is the highest-touch component.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Ask Themis a research question...                          │
│                                                              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ [📎 Attach]   [@ Mode: Public ▾]                  [Send ➤]   │
└──────────────────────────────────────────────────────────────┘
```

Specifications:

- Multi-line, auto-grows up to 8 lines, then scrolls
- `Enter` sends; `Shift+Enter` adds a newline
- `Cmd/Ctrl+K` opens command palette
- Attach button → document upload modal
- Mode chip → mode switcher dropdown
- Send button disabled when input is empty; shows loading state during request
- Character / token count appears subtly when input exceeds 500 characters
- Placeholder text changes based on mode:
  - Public: "Ask a research question about Indian law..."
  - Professional: "Research question, case name, or citation..."
  - Patent: "Patent number, claim text, or research question..."

When a document is attached to the session, a chip appears above the composer:

```
📎 NDA-Acme-2024.pdf · 12 pages · Active for this session [×]
```

### 5.2 Message bubbles

User messages and Themis messages are visually distinct but neither is heavily decorated.

**User message:**

- Right-aligned
- Light themis-tinted background (`themis-100`)
- Plain text, `body` size
- No avatar (saves space)

**Themis message:**

- Left-aligned
- White background with `gray-200` border
- Themis mark visible at the top-left (the small scale icon, 20px)
- Mode badge at top-right ("Public" / "Professional" / "Patent")
- Generated content in serif (Source Serif Pro) for public/professional modes; sans for patent mode
- Citation pills inline with text
- "Caveats" section appears below the main answer with a `warning-50` left border accent
- "Follow-up suggestions" appears below caveats as a horizontal scroll strip of chips

### 5.3 Citation pills

The most-touched non-text element. Designed for visibility, clickability, and tier-clarity.

```
[s1] [s2] [s3]
```

Visual specification:

- Pill shape, `radius-sm`
- Inline with text, baseline-aligned
- Subtle gap before (4px) and inside between letter and number (2px)
- Tier-coded:
  - **Tier 1** — filled with `themis-600`, white text
  - **Tier 2** — outline with `info-600` border, `info-600` text, white background
  - **Tier 3** — outline with `gray-600` border and text
  - **Tier 4** — outline with `gray-400` border, dimmed text, includes "web" label: `[s5 web]`
- Hover state:
  - Source preview tooltip appears (title + tier badge + first 80 chars of source text)
  - 100ms delay before showing
  - Cursor changes to pointer
- Click state:
  - Source panel opens (if collapsed) and scrolls to the cited source
  - Source is highlighted briefly (1s) with a soft pulse

For multiple citations adjacent: `[s1,s2]` is rendered as a single pill with comma separator, expanding to two pills on hover for individual access.

### 5.4 Source panel cards

Each source in the right-side panel is a card.

```
┌────────────────────────────────────────────────┐
│ ◉ TIER 1 — PRIMARY AUTHORITY                   │
│                                                │
│ Smt. Selvi v. State of Karnataka              │
│ (2010) 7 SCC 263                              │
│ Supreme Court of India · 5 May 2010           │
│ ─                                              │
│ Status: Not overruled                          │
│ ─                                              │
│ "...Article 20(3) extends to investigation     │
│ as well as trial. The protection against      │
│ self-incrimination..."                         │
│ (Paragraph 26)                                 │
│                                                │
│ [ View full judgment ] [ Copy citation ]      │
└────────────────────────────────────────────────┘
```

For statute sources:

```
┌────────────────────────────────────────────────┐
│ ◉ TIER 1 — PRIMARY AUTHORITY                   │
│                                                │
│ Indian Penal Code, 1860 § 420                  │
│ Statute · Cheating and dishonestly inducing   │
│ delivery of property                           │
│ ─                                              │
│ Current text (effective 2018-Aug-15 - present) │
│ ─                                              │
│ "Whoever cheats and thereby dishonestly       │
│ induces the person deceived to deliver any    │
│ property..."                                   │
│                                                │
│ [ View in IPC ] [ Show prior versions ]       │
└────────────────────────────────────────────────┘
```

For web sources:

```
┌────────────────────────────────────────────────┐
│ ○ TIER 3 — CURATED COMMENTARY                  │
│                                                │
│ Supreme Court Holds...                         │
│ LiveLaw.in · Published 2024-03-15             │
│ ─                                              │
│ Retrieved 2024-12-01 · Archived ✓             │
│ ─                                              │
│ "The bench observed that..."                   │
│                                                │
│ [ View archived snapshot ]                     │
└────────────────────────────────────────────────┘
```

Each card has a tier-color left border (4px) for at-a-glance scanning.

### 5.5 Mode selector

A compact dropdown in the header:

```
┌──────────────────────┐
│ ◉ Public mode     ▾  │
└──────────────────────┘
```

Opens to:

```
┌─────────────────────────────────────────────┐
│ Switch mode                                 │
│                                             │
│ ◉ Public                                    │
│   Plain language, strong disclaimers        │
│                                             │
│ ○ Professional                              │
│   Legal terminology, citation export        │
│   ▸ Requires verification for full export   │
│                                             │
│ ○ Patent                                    │
│   International patents and prior art       │
└─────────────────────────────────────────────┘
```

The selected mode shows a check; switching shows the confirmation flow from Document 4 §7.

### 5.6 Sidebar

```
┌───────────────────────────────────┐
│ ▲ Themis Machina                  │
│                                   │
│ + New research                    │
│ ──────────────────────────────    │
│ Continue                          │
│ ▸ Essar Steel post-2022          │
│                                   │
│ My matters                        │
│ ▸ 🗂 Essar Steel post-2022       │
│ ▸ 🗂 138 case for ABC Pvt Ltd    │
│ ▸ 🗂 Solid-state battery PA      │
│ ▸ 🗂 Untitled matter             │
│ + New matter                      │
│ ──────────────────────────────    │
│ Documents                         │
│ ▸ NDA-Acme-2024.pdf              │
│                                   │
│ ──────────────────────────────    │
│ ● Public mode                     │
│ ⚙ Settings                        │
│ 👤 Your name                      │
└───────────────────────────────────┘
```

Anonymous users see a simplified sidebar with just "New research" and a "Sign in to save" prompt at the bottom.

### 5.7 Document upload modal

A focused modal that walks the user through upload:

```
┌─────────────────────────────────────────────┐
│ Upload a document               [×]         │
│ ───────────────────────────────────────     │
│                                             │
│         ┌──────────────────────┐            │
│         │                      │            │
│         │   Drop file here     │            │
│         │   or click to choose │            │
│         │                      │            │
│         └──────────────────────┘            │
│                                             │
│ Supported: PDF, DOCX, scanned image         │
│ Max 25 MB                                   │
│                                             │
│ What kind of document is this? (optional)   │
│ [ Auto-detect ▾ ]                           │
│                                             │
│ Your role? (only for contracts)             │
│ [ Auto-detect ▾ ]                           │
│                                             │
│ ───────────────────────────────────────     │
│ ℹ Your document stays private. Not used    │
│   for training. Deleted on session expiry.  │
│                                             │
│ [ Cancel ]              [ Upload document ] │
└─────────────────────────────────────────────┘
```

After "Upload document":

```
┌─────────────────────────────────────────────┐
│ Processing: NDA-Acme-2024.pdf               │
│ ───────────────────────────────────────     │
│                                             │
│ ✓ Uploaded                                  │
│ ✓ Parsed                                    │
│ ⟳ Identifying clauses...                    │
│ ○ Indexing                                  │
│                                             │
│ Typically takes 30-90 seconds.              │
└─────────────────────────────────────────────┘
```

### 5.8 The "Caveats" callout

When Themis produces an answer with uncertainty or important context, the caveats appear in a left-bordered callout:

```
┌─────────────────────────────────────────────┐
│ ⚠ Important context                          │
│                                             │
│ • The 2018 amendment to the Negotiable      │
│   Instruments Act changed certain procedures │
│ • Different High Courts have taken slightly │
│   different approaches on Section 138(c)    │
│ • This research aid does not replace legal  │
│   advice — please consult an advocate       │
└─────────────────────────────────────────────┘
```

The accent color depends on severity: `info-600` for context, `warning-600` for "this affects your answer," `danger-600` for "you should definitely consult a lawyer."

### 5.9 Refusal message

When the system refuses, the refusal is styled distinctly but not alarmingly:

```
┌─────────────────────────────────────────────┐
│ ◐ Not what I can do — but here's what I can │
│                                             │
│ I can't tell you what to do — that's a      │
│ question for a qualified advocate who knows │
│ your specific facts.                        │
│                                             │
│ What I can help with:                       │
│                                             │
│  ▸ Explaining the law that applies          │
│  ▸ Showing how courts have ruled in similar │
│    cases                                    │
│  ▸ Walking through the typical procedure    │
│                                             │
│ Want me to do any of those?                 │
└─────────────────────────────────────────────┘
```

The "◐" half-moon icon distinguishes refusals from regular answers visually without using a red/danger color (which would feel hostile).

### 5.10 Patent prior-art coverage matrix

For Patent mode prior-art reports, the coverage matrix is rendered as a compact table:

```
┌────────────────────┬───┬───┬───┬───┬───┐
│                    │ A │ B │ C │ D │ E │
├────────────────────┼───┼───┼───┼───┼───┤
│ US9876543B2 [p1]   │ ✓ │ ✓ │ ✓ │ ~ │ ✗ │
│ WO2017123456 [p2]  │ ✓ │ ✓ │ ✓ │ ✓ │ ✗ │
│ CN108765432A [p3]  │ ✓ │ ✓ │ ✗ │ ✗ │ ✗ │
│ Park et al. [pa1]  │ ✓ │ ✓ │ ✓ │ ✓ │ ✓ │
└────────────────────┴───┴───┴───┴───┴───┘
Element legend:
  A: Lithium-ion battery cathode (general)
  B: Graphene coating
  C: Chemical vapor deposition method
  D: Temperature range 800-1000°C
  E: Thickness 2-10 nm
```

Each cell is a clickable explanation ("Why ✓?") that expands a small tooltip with the verbatim text from the prior art that establishes coverage.

---

## 6. Interaction Patterns

### 6.1 Streaming response

While the LLM streams, the UI shows:

- Tokens appearing in real time
- A subtle pulsing cursor at the end of the streaming text
- "Themis is thinking..." replaced by "Themis is researching..." → "Themis is writing..." → "Verifying citations..."
- Citation pills appear as the model emits them
- The source panel auto-populates with sources as they're referenced (not all at once at the end)

After streaming completes, the verifier may take 1–2 more seconds. During this time:

- A small "Verifying citations..." chip appears below the answer
- If any claims are stripped due to verification failure, an inline notice appears in place: "Some content was removed because citation verification failed. [Why?]"

### 6.2 Citation interaction

**Hover on a citation pill:**

- 100ms delay
- Tooltip appears with: source title, tier badge, first 80 chars
- Tooltip dismisses on mouse-out

**Click on a citation pill:**

- Source panel opens (if collapsed)
- Panel scrolls to the cited source
- Source card flashes briefly (1s soft pulse) to indicate which one was just referenced
- Focus is *not* moved to the panel (user can keep typing)

**Click on "View full judgment" / "View in IPC" within a source card:**

- A larger modal opens showing the full source
- The original cited text is highlighted in the larger context
- Navigation: prev/next paragraph, search within document, close

### 6.3 Source panel scroll behavior

The source panel maintains a running list of all sources from the current conversation. The most recently cited sources are at the top. Each source has a tag indicating which turn it was cited from (e.g., "Turn 3"), helping the user navigate back.

Filter chips at the top of the source panel allow filtering by:

- Tier (1 / 2 / 3 / 4)
- Type (Statute / Case / Patent / Document / Web)
- This turn / all turns

### 6.4 Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl+K` | Open command palette |
| `Cmd/Ctrl+/` | Toggle sidebar |
| `Cmd/Ctrl+.` | Toggle source panel |
| `Cmd/Ctrl+N` | New research conversation |
| `Cmd/Ctrl+S` | Save as matter |
| `Cmd/Ctrl+E` | Export citations |
| `Cmd/Ctrl+M` | Mode switcher |
| `Esc` | Close any open modal / dropdown |
| `↑` (in empty composer) | Edit last user message |

A `?` key opens a keyboard shortcut overlay.

### 6.5 Empty states

Several empty states are designed deliberately:

**No conversations yet (signed-in user, first visit):**

```
┌─────────────────────────────────────────────┐
│              [scale icon]                   │
│                                             │
│         Welcome to Themis Machina           │
│                                             │
│   Your conversational legal research        │
│   assistant. Citation-grounded answers      │
│   on Indian law and international patents.  │
│                                             │
│   Try one of these to get started:          │
│                                             │
│   ▸ Explain Section 138 of the NI Act       │
│   ▸ Find SC cases on right to privacy       │
│   ▸ Patent landscape: solid-state batteries │
│                                             │
└─────────────────────────────────────────────┘
```

**No documents uploaded:**

```
   No documents in this session yet.
   [ Upload a document ]
```

**No matters:**

```
   You haven't saved any research matters yet.
   Your conversations will be saved when you
   click "Save as matter" or after a few turns.
```

### 6.6 Loading states

Loading is shown contextually, never as a generic spinner over the whole screen:

- LLM generation: streaming cursor at the response location
- Retrieval: subtle inline indicator below the chat input "Searching corpus..."
- Document upload: the modal progress states
- Page navigation: a thin top progress bar (like nprogress)

### 6.7 Error states

Errors are shown inline where they occurred, not as toasts:

- LLM error: in the chat, "I had trouble completing that response. [ Retry ]"
- Upload error: in the upload modal, with specifics
- Auth error: in the auth form, inline next to the relevant field
- Network error: a banner at the top of the chat that fades after reconnect

Toasts are reserved for ephemeral confirmations ("Citation copied" / "Saved as matter").

---

## 7. Screen-by-Screen Specifications

### 7.1 Landing page

```
┌────────────────────────────────────────────────────────────────┐
│ [Themis Machina logo]                            [Sign in]     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                                                                │
│         Conversational legal research for India.               │
│         Citation-grounded. Free.                               │
│                                                                │
│         Themis is a research assistant — not a lawyer.         │
│         Every answer is backed by primary sources you can      │
│         verify with one click.                                 │
│                                                                │
│                  [ Start researching ➤ ]                       │
│                                                                │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ⚖ Research          📎 Documents         🔬 Patents          │
│   Indian statutes     Upload your own      International       │
│   and case law        contracts and        prior-art search    │
│                       notices                                  │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   What Themis is NOT                                           │
│   ─────────────────                                           │
│   • Not a lawyer — it doesn't give legal advice                │
│   • Not an outcome predictor                                   │
│   • Not a substitute for a qualified advocate                  │
│                                                                │
│   It is a research tool. Use it to understand the law, find    │
│   relevant authorities, and prepare to work with a lawyer.     │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   Try an example:                                              │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐    │
│   │ "What does Section 138 of the NI Act cover?"        │    │
│   │ ─                                                    │    │
│   │ Themis: Section 138 governs cheque bounce cases...  │    │
│   │ [s1] [s2] [s3]                                       │    │
│   └──────────────────────────────────────────────────────┘    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   How it works                                                 │
│   ─────────────                                                │
│                                                                │
│   1. Ask          2. Retrieve         3. Cite                  │
│   in plain        across statutes,    every claim              │
│   English         cases, patents,     traces to a              │
│                   commentary          source you can verify    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│   Built as an AI engineering portfolio project.                │
│   [ Read the design docs ] [ View on GitHub ]                  │
├────────────────────────────────────────────────────────────────┤
│   © Themis Machina · Privacy · Terms · About                   │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 Chat — first interaction (public, anonymous)

```
┌────────────────────────────────────────────────────────────────┐
│ Themis Machina         ◉ Public  ▾                  Sign in    │
├──────────┬─────────────────────────────────────┬───────────────┤
│          │                                     │               │
│   ▲      │   Welcome to Themis                 │               │
│  Themis  │   ─────────────────                 │               │
│          │                                     │               │
│ + New    │   Hi, I'm Themis — a research       │               │
│ research │   assistant for Indian law. I can   │               │
│          │   help you understand what the law  │               │
│ Sign in  │   says, find relevant judgments,    │               │
│ to save  │   and trace through legal questions │               │
│ research │   step by step. I'll give you       │               │
│          │   citations to verify every answer. │               │
│          │                                     │               │
│          │   What I won't do: tell you what    │               │
│          │   to do in your specific situation, │               │
│          │   predict outcomes, or replace a    │               │
│          │   lawyer.                           │               │
│          │                                     │               │
│          │   Try one of these:                 │               │
│          │   ▸ Explain Section 138 NI Act      │               │
│          │   ▸ What does the Constitution      │               │
│          │     say about Article 21?           │               │
│          │   ▸ Find cases on right to privacy  │               │
│          │                                     │               │
│          │                                     │               │
│          ├─────────────────────────────────────┤               │
│          │ [ Ask Themis a research question ]  │               │
│          │ [📎][@ Public ▾]            [Send ➤] │               │
│          └─────────────────────────────────────┘               │
└──────────┴─────────────────────────────────────────────────────┘
```

### 7.3 Chat — mid-conversation (professional)

```
┌────────────────────────────────────────────────────────────────┐
│ Themis Machina  ◉ Professional ▾  · Essar Steel...  Priya 👤   │
├──────────┬──────────────────────────────┬──────────────────────┤
│          │                              │ Sources (this turn)  │
│ + New    │ ▲ Themis · Turn 3            │                      │
│ research │                              │ ┌──────────────────┐ │
│          │ No, *Essar Steel* (formally  │ │◉ TIER 1          │ │
│ Continue │ *Committee of Creditors of   │ │DBS Bank v.       │ │
│ ▸ Essar  │ Essar Steel India Ltd. v.    │ │Ruchi Soya        │ │
│   Steel  │ Satish Kumar Gupta, (2020)   │ │(2024) ...        │ │
│   post-  │ 8 SCC 531*) has not been     │ │SC · Para 31      │ │
│   2022   │ overruled. It has been       │ │Status: Not       │ │
│          │ **clarified** in [s1] *DBS   │ │overruled         │ │
│ Matters  │ Bank Ltd. v. Ruchi Soya      │ │"...The principle │ │
│ 🗂 Essar │ Industries* (2024) and       │ │of equitable      │ │
│   Steel  │ **applied with refinement**  │ │distribution      │ │
│ 🗂 138 c │ in [s2] *Vidarbha Industries │ │remains..."       │ │
│   for AB │ Power Ltd. v. Axis Bank Ltd.*│ │[View judgment]   │ │
│ 🗂 Solid │ (2022).                      │ └──────────────────┘ │
│   -state │                              │                      │
│   batt.. │ The 2024 *DBS Bank* judgment │ ┌──────────────────┐ │
│          │ specifically held at para 31 │ │◉ TIER 1          │ │
│ ─────    │ that "the principle of       │ │Vidarbha Indust.  │ │
│ Docs     │ equitable distribution under │ │(2022)            │ │
│ (none)   │ Section 30(4) of the IBC     │ │SC · Para 17, 23  │ │
│          │ remains intact, but the      │ │...               │ │
│ ─────    │ application must be informed │ └──────────────────┘ │
│ ⚙ Set    │ by the specific facts of    │                      │
│ 👤 Priya │ each case." [s1]             │                      │
│          │                              │                      │
│          │ ─ Caveats ─                  │                      │
│          │ • NCLAT has taken a slightly │                      │
│          │   different line in...       │                      │
│          │                              │                      │
│          │ Follow-up suggestions:       │                      │
│          │ [Compare with NCLAT line]    │                      │
│          │ [What did *Essar* hold?]     │                      │
│          │ [Recent HC application]      │                      │
│          ├──────────────────────────────┤                      │
│          │ Your turn...                 │                      │
│          │ [📎][@Pro ▾]         [Send ➤] │                      │
│          └──────────────────────────────┘                      │
└──────────┴────────────────────────────────────────────────────┘
```

### 7.4 Chat — Patent mode prior-art report

```
┌────────────────────────────────────────────────────────────────┐
│ Themis Machina  ◉ Patent ▾   · Solid-state batt PA   Meera 👤  │
├──────────┬──────────────────────────────┬──────────────────────┤
│          │ ▲ Themis · Prior-art report  │ Sources              │
│          │                              │                      │
│          │ I decomposed your claim into │ Patent sources       │
│          │ 5 elements and searched...   │ [p1] US9876543B2     │
│          │                              │     Samsung 2015     │
│          │ Claim elements:              │ [p2] WO2017123456    │
│          │ A: Li-ion battery cathode    │     Tsinghua 2017    │
│          │ B: Graphene coating          │ [p3] CN108765432A    │
│          │ C: CVD deposition            │     CATL 2018        │
│          │ D: Temp 800-1000°C           │                      │
│          │ E: Thickness 2-10 nm         │ Academic sources     │
│          │                              │ [pa1] Park et al.    │
│          │ Coverage matrix:             │     Nature Energy    │
│          │ ┌────────────┬─┬─┬─┬─┬─┐    │     2018             │
│          │ │            │A│B│C│D│E│    │                      │
│          │ ├────────────┼─┼─┼─┼─┼─┤    │ [Export prior-art    │
│          │ │US98... [p1]│✓│✓│✓│~│✗│    │  report as PDF]      │
│          │ │WO20... [p2]│✓│✓│✓│✓│✗│    │                      │
│          │ │CN10... [p3]│✓│✓│✗│✗│✗│    │                      │
│          │ │Park   [pa1]│✓│✓│✓│✓│✓│    │                      │
│          │ └────────────┴─┴─┴─┴─┴─┘    │                      │
│          │                              │                      │
│          │ My assessment...             │                      │
│          │                              │                      │
│          ├──────────────────────────────┤                      │
│          │ Refine the claim or ask...   │                      │
│          │ [📎][@Patent ▾]      [Send ➤] │                      │
│          └──────────────────────────────┘                      │
└──────────┴────────────────────────────────────────────────────┘
```

### 7.5 Document upload — clause analysis result

After upload, the side panel transforms into a document overview:

```
┌──────────────────────┐
│ NDA-Acme-2024.pdf    │
│ ─────────────────    │
│ 12 pages · NDA       │
│ 23 clauses           │
│                      │
│ ⚠ 3 flagged          │
│                      │
│ Clauses              │
│ 1. Parties           │
│ 2. Definitions       │
│ 3. Confidential Info │
│ 4. Term      ⚠       │
│ 5. Exclusions        │
│ 6. Confid term ⚠     │
│ 7. Return of info    │
│ 8. Liquidated dmg ⚠  │
│ 9. Injunctive relief │
│ 10. Jurisdiction     │
│ ...                  │
│                      │
│ [ Discuss flagged ]  │
│ [ Remove document ]  │
└──────────────────────┘
```

Clicking a clause pre-populates the chat: "Tell me about Clause 6 — the confidentiality term."

---

## 8. Accessibility

The product targets WCAG 2.1 Level AA at minimum, with several AAA-level practices.

### 8.1 Color contrast

All text-to-background combinations pass 4.5:1 ratio at minimum (`themis-700` on white passes; `themis-500` on `themis-50` is reserved for UI chrome where contrast isn't critical for reading).

Citation pill colors maintain 4.5:1 ratio for the text within them, even at small sizes.

### 8.2 Keyboard navigation

Every interactive element is reachable via Tab. Focus indicators use a 2px `themis-600` outline with 2px offset. Focus order is logical: header → sidebar → chat → composer → source panel.

The composer is the default focus on page load and on conversation switch.

### 8.3 Screen reader support

- Proper landmark roles: `main` for chat, `complementary` for source panel, `navigation` for sidebar
- Citation pills announce as: "Citation s1, Tier 1 primary authority, clickable"
- Streaming responses announce progressively (using `aria-live="polite"`)
- Mode switcher and other state changes announce via `aria-live`
- Source cards have proper heading structure for screen reader navigation

### 8.4 Motion preferences

`prefers-reduced-motion` is respected — animations replaced with instant transitions; streaming text appears at slower-than-real-time pacing for users who set this preference.

### 8.5 Text scaling

The interface remains usable up to 200% text scaling without horizontal scrolling. Layout reflows; nothing breaks.

### 8.6 Focus management on errors

When an error occurs in a form (sign-in, upload modal), focus moves to the error message with appropriate `aria-describedby`.

---

## 9. Mobile Considerations

Mobile is supported but not optimized for v1.0. Specific behavior:

### 9.1 Layout

- Single column
- Sidebar and source panel become drawers (slide in from left/right)
- Composer sticks to the bottom
- Citation pills are larger (touch-target 44px minimum)

### 9.2 Reduced features

- Document upload is supported but constrained to camera capture or local files
- Patent prior-art report's coverage matrix collapses to a vertical list of elements with per-element candidate cards
- Keyboard shortcuts are not available

### 9.3 What's deferred

A native mobile app is out of scope for v1.0. Responsive web is sufficient for the portfolio demo. A proper mobile experience is a v1.1 consideration.

---

## 10. Dark Mode

Supported and toggleable via system preference + manual override in settings.

Dark mode swaps:

- `gray-50` → `gray-950` (background)
- `white` → `gray-900` (cards)
- `gray-950` → `gray-50` (primary text)
- `themis-600` → `themis-500` (links, accents — slightly lighter for contrast)
- Citation pill tier colors remain similar; backgrounds use the dark equivalents

The themis serif typography in dark mode reduces slightly in size for better legibility on dark backgrounds.

---

## 11. Performance Considerations for the UI

The frontend respects several performance constraints:

### 11.1 Initial load

- Initial JS bundle: target < 200 KB compressed (Next.js with strict tree-shaking)
- LCP (Largest Contentful Paint): target < 2.5s on slow 4G
- Use of font-display: swap so text appears before web fonts load

### 11.2 Streaming

- SSE consumption with React 19's `useSyncExternalStore` or similar for efficient updates
- No re-render of the entire conversation on each token; only the streaming message re-renders

### 11.3 Source panel

- Source cards virtualize when conversation accumulates > 30 sources (rare but possible in long sessions)

### 11.4 Memoization

- Citation pills, source cards, mode selector — all memoized with stable props
- Sidebar matter list virtualizes if > 50 matters

---

## 12. Brand Voice in UI Copy

The voice of Themis (in conversation) and the voice of the surrounding UI (buttons, labels, error messages) are consistent.

**Voice attributes:**

- **Direct** — short sentences, no hedging without reason
- **Knowledgeable** — uses correct legal terminology when appropriate
- **Honest** — explicit about uncertainty and limitations
- **Calm** — never alarmist, never sycophantic
- **Helpful, not servile** — offers paths forward rather than dead-ends

**Voice anti-patterns to avoid:**

- "Sorry, I can only..." (don't apologize for being a tool)
- "I'm just an AI..." (irrelevant context)
- "As your AI assistant..." (self-aggrandizing)
- Excessive disclaimers in the middle of an answer
- Emoji in generated content (allowed in UI chrome only, sparingly)

**UI copy examples:**

| Context | Don't write | Write |
|---|---|---|
| Empty state | "No conversations yet 😊" | "No conversations yet" |
| Loading | "Hold on, working on it..." | "Themis is researching..." |
| Error | "Oops! Something went wrong!" | "I couldn't complete that. Try again or rephrase your question." |
| Refusal | "I'm so sorry, I can't help with that" | "I can't help with that specific question. Here's what I can do:" |

---

## 13. Iconography Reference

Specific Lucide icons used throughout the product:

| Use | Icon |
|---|---|
| Brand mark | (custom scale design) |
| New conversation | `Plus` |
| Send message | `ArrowUp` (in a circle) |
| Attach document | `Paperclip` |
| Mode selector | `ChevronDown` |
| Sources panel toggle | `BookOpen` |
| Sidebar toggle | `PanelLeftClose` / `PanelLeftOpen` |
| Settings | `Settings` |
| User profile | `User` |
| Sign out | `LogOut` |
| Copy citation | `Copy` |
| External link | `ExternalLink` |
| View archived | `Archive` |
| Tier 1 source | `Shield` (filled) |
| Tier 2 source | `ShieldCheck` (outline) |
| Tier 3 source | `BookText` |
| Tier 4 source | `Globe` |
| Refusal | (custom half-moon "◐") |
| Warning callout | `AlertTriangle` |
| Info callout | `Info` |
| Danger callout | `AlertOctagon` |
| Verified citation | `CheckCircle2` |
| Unverified / failed | `XCircle` |
| Themis is thinking | `Loader2` (rotating) |

---

## 14. Component Library and Implementation

The UI is built with **shadcn/ui** components as the base, customized to the Themis design system. This is the pragmatic choice — shadcn provides accessible, well-built primitives we customize rather than building from scratch.

Customizations:

- All shadcn defaults overridden with Themis tokens (color, spacing, typography)
- Citation pill is a custom component (not in shadcn)
- Source card is a custom component
- The chat composer extends shadcn's Textarea with custom send-button logic
- The mode selector uses shadcn's DropdownMenu

For Phase A, the entire frontend ships on Vercel free tier. For Phase B, the same components scale unchanged to Vercel Pro or self-hosted Next.js.

---

## 15. Design Deliverables for Phase 8

When Phase 8 (production frontend) begins, the design deliverables required are:

1. **Figma file** with all screens at three breakpoints (mobile / tablet / desktop)
2. **Component library** in Figma matching the shadcn-based implementation
3. **Design tokens** exported as a single JSON file (colors, spacing, typography, radius) consumable by Tailwind config
4. **Loom video walkthrough** of the key flows
5. **Asset exports** (favicons, OG images, brand mark in SVG)

The Figma file is the deliverable handoff; this document is the textual specification.

---

## 16. Open UX Design Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | Should the source panel default open or closed on first visit? | Phase 8 |
| 2 | Should citation pills inline tier indicators (color) or use only the source panel? | Phase 8 |
| 3 | Should mode switching require confirmation or be instant? | Phase 3 |
| 4 | Should the brand wordmark or icon be primary in the header? | Phase 8 |
| 5 | Custom typography (paid Inter variants) vs Google Fonts default — recommended default for Phase A | Phase 8 |
| 6 | Should there be an "expert mode" within Professional that further compresses density? | Phase 8 |
| 7 | Should the citation viewer support side-by-side comparison of multiple sources? | v1.1 |

---

## 17. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 18. Related Documents

- **Document 1** — PRD
- **Document 2** — TRD
- **Document 3** — AI/ML System Design
- **Document 4** — App Flow & User Journey (what these UIs render)
- **Document 7** — Safety & Responsible AI (informs refusal UI, disclaimer placement)
- **Document 10** — Security & Privacy (informs sign-in and data-control UI)

— end of Document 5 —
