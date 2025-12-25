# CCFS Branding Guide

Brand assets and design system for AIRecruiter v2. Preserves CCFS corporate identity from v1.

---

## Logo Assets

Copy from v1: `/Users/boydbischke/IdeaProjects/airecruiter/web/public/`

| File | Usage |
|------|-------|
| `ccfs-logo.svg` | Full CCFS logo (header, login) |
| `ccfs-logo-white.svg` | White variant (dark backgrounds) |
| `logos/logo-primary.svg` | AI Recruiter primary (blue) |
| `logos/logo-white.svg` | AI Recruiter white |
| `logos/logo-secondary.svg` | AI Recruiter secondary |
| `logos/logo-black.svg` | AI Recruiter black |

All logos are SVG (519.5 x 170.2 viewBox).

---

## Color Palette

### Primary Brand Colors

| Name | Hex | HSL | Usage |
|------|-----|-----|-------|
| Primary Blue | `#0F5A9C` | 209 81% 34% | Nav bar, buttons, links |
| Primary Blue Light | `#2E7EC8` | 209 63% 48% | Hover states |
| Primary Blue Dark | `#0A3F6B` | 209 82% 23% | Active states |
| Secondary Red | `#AE2326` | 359 65% 41% | Alerts, destructive |

### CSS Variables

```css
:root {
  /* Primary */
  --primary: 209 81% 34%;
  --primary-foreground: 0 0% 100%;

  /* Secondary */
  --secondary: 359 65% 41%;
  --secondary-foreground: 0 0% 100%;

  /* Light Mode */
  --background: 216 20% 98%;
  --foreground: 214 32% 15%;
  --card: 0 0% 100%;
  --card-foreground: 214 32% 15%;
  --border: 214 20% 90%;
  --muted: 214 20% 96%;
  --muted-foreground: 214 10% 45%;

  /* Accents */
  --accent: 209 81% 34%;
  --accent-foreground: 0 0% 100%;
  --destructive: 359 65% 41%;
  --destructive-foreground: 0 0% 100%;

  /* Chart Colors */
  --chart-1: 209 73% 33%;
  --chart-2: 357 67% 41%;
  --chart-3: 157 72% 44%;
  --chart-4: 209 60% 50%;
  --chart-5: 357 60% 50%;

  --radius: 0.5rem;
}

.dark {
  --background: 0 0% 12%;
  --foreground: 0 0% 95%;
  --card: 0 0% 20%;
  --card-foreground: 0 0% 95%;
  --border: 0 0% 25%;
  --muted: 0 0% 15%;
  --muted-foreground: 0 0% 65%;
  --primary: 209 63% 48%;
  --accent: 209 63% 48%;
}
```

### Tailwind Config Colors

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // CCFS Brand
        'ccfs-blue': '#0F5A9C',
        'ccfs-blue-light': '#2E7EC8',
        'ccfs-blue-dark': '#0A3F6B',
        'ccfs-red': '#AE2326',
        'ccfs-red-light': '#D32F2F',
        'ccfs-red-dark': '#7B1818',
        'ccfs-green': '#21BF7D',
      },
    },
  },
};
```

---

## Typography

### Font Stack

```css
font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```

### Scale

| Name | Size | Usage |
|------|------|-------|
| xs | 0.75rem (12px) | Labels, captions |
| sm | 0.875rem (14px) | Secondary text |
| base | 1rem (16px) | Body text |
| lg | 1.125rem (18px) | Emphasized text |
| xl | 1.25rem (20px) | Section headers |
| 2xl | 1.5rem (24px) | Page headers |
| 3xl | 1.875rem (30px) | Large headers |
| 4xl | 2.25rem (36px) | Hero text |

### Heading Styles

```css
h1, h2, h3, h4, h5, h6 {
  font-weight: 600; /* semibold */
  letter-spacing: -0.025em; /* tracking-tight */
}
```

---

## Component Styling

### Navigation Bar

```css
.nav {
  background-color: #0F5A9C; /* light mode */
  /* dark mode: #2B6CB0 */
  height: 64px;
  position: fixed;
  z-index: 50;
  color: white;
}

.nav-link {
  color: rgba(255, 255, 255, 0.9);
}

.nav-link:hover {
  color: white;
  background-color: rgba(255, 255, 255, 0.1);
}
```

### Buttons

```css
.btn-primary {
  background-color: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  border-radius: var(--radius);
  padding: 0.5rem 1rem;
  font-weight: 500;
  transition: background-color 200ms;
}

.btn-primary:hover {
  background-color: hsl(209 63% 48%); /* lighter */
}

.btn-secondary {
  background-color: hsl(var(--secondary));
  color: hsl(var(--secondary-foreground));
}
```

### Cards

```css
.card {
  background-color: hsl(var(--card));
  border-radius: var(--radius);
  border: 1px solid hsl(var(--border));
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}
```

### Form Inputs

```css
.form-input {
  background-color: hsl(var(--background));
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
  padding: 0.5rem 0.75rem;
}

.form-input:focus {
  border-color: hsl(var(--primary));
  outline: none;
  box-shadow: 0 0 0 2px hsl(var(--primary) / 0.2);
}
```

---

## Login Page Design

Split layout with branded sidebar:

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │                      │  │                             │  │
│  │   [CCFS Logo]        │  │   Welcome Back              │  │
│  │                      │  │                             │  │
│  │   AI Recruiter       │  │   [Email input]             │  │
│  │   ───────────────    │  │   [Password input]          │  │
│  │   Intelligent        │  │                             │  │
│  │   recruitment        │  │   [Sign In button]          │  │
│  │   automation         │  │                             │  │
│  │   platform           │  │   ── or ──                  │  │
│  │                      │  │                             │  │
│  │   Gradient BG        │  │   [SSO Login button]        │  │
│  │   (primary blue)     │  │                             │  │
│  │                      │  │                             │  │
│  └──────────────────────┘  └─────────────────────────────┘  │
│         40%                          60%                     │
└─────────────────────────────────────────────────────────────┘
```

### Sidebar Gradient

```css
/* Light mode */
background: linear-gradient(to bottom right, #0F5A9C, rgba(15, 90, 156, 0.8));

/* Dark mode */
background: linear-gradient(to bottom right, #1a1a1a, #2d2d2d);
```

---

## Email Branding

### Sender Identity

```
From: AI Recruiter System <noreply@ccfs.com>
```

### Subject Line Format

```
AI Recruiter Alert: [Description]
AI Recruiter: [Status Update]
Interview Invitation: [Position Title]
```

### Email Footer

```html
<p style="color: #666; font-size: 12px; margin-top: 24px;">
  This is an automated message from CCFS AI Recruiter.
  Please do not reply to this email.
</p>
```

---

## Dark Mode Support

Full dark mode with CSS variables. Toggle in top-right corner.

| Element | Light | Dark |
|---------|-------|------|
| Background | #F8F9FA | #1f1f1f |
| Foreground | #1A202C | #f1f1f1 |
| Card | #FFFFFF | #323232 |
| Border | #e2e8f0 | #404040 |
| Nav | #0F5A9C | #2B6CB0 |

---

## Public Interview Page

Candidate-facing pages use CCFS logo in header with minimal branding:

```
┌─────────────────────────────────────────────────────────────┐
│  [CCFS Logo White]                              [Dark mode] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                    Interview Chat UI                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Page title: "CCFS - Interview"

---

## Assets to Copy to v2

```bash
# From airecruiter v1 to airecruiter2
cp -r ../airecruiter/web/public/ccfs-logo.svg web/public/
cp -r ../airecruiter/web/public/ccfs-logo-white.svg web/public/
cp -r ../airecruiter/web/public/logos/ web/public/logos/
cp ../airecruiter/web/public/favicon.ico web/public/
```
