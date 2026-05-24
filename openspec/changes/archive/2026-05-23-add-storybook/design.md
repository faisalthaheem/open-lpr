## Context

The SPA (`single-page-ui/`) is a Next.js 16 app using Tailwind CSS 4 with 9 reusable components. All components use `'use client'` directives and Tailwind utility classes exclusively (no CSS modules or CSS-in-JS). Dark mode is toggled via a `dark` class on `<html>`. Components interact with a Django REST API via `src/lib/api.ts`.

Storybook needs to work alongside this setup without disrupting the Next.js build or dev workflow.

## Goals / Non-Goals

**Goals:**
- Set up Storybook 9 with Next.js 16 + Tailwind CSS 4 support
- Write stories for all 9 components with realistic mock data
- Support dark mode stories (both light and dark variants)
- Enable isolated component development outside the full app

**Non-Goals:**
- Visual regression testing / Chromatic integration (can be added later)
- Refactoring existing components to be "Storybook-friendly" — they already have clean props interfaces
- Adding Storybook to the Django backend or Docker deployment
- CI/CD integration for Storybook builds

## Decisions

### 1. Use `@storybook/nextjs-vite` builder

**Decision**: Use the `@storybook/nextjs-vite` framework preset.

**Rationale**: The project uses Next.js 16 with features like `next/link`, `next/image`, and App Router. The `nextjs-vite` builder handles these correctly. The alternative (`@storybook/react-vite`) would require mocking Next.js APIs manually.

### 2. Storybook 9

**Decision**: Use Storybook 9 (latest stable).

**Rationale**: Storybook 9 is the current major version with native support for modern frameworks. It has first-class Next.js support and improved performance over Storybook 8.

### 3. Stories co-located with components

**Decision**: Place `*.stories.tsx` files in the same directory as their components.

**Rationale**: Co-location makes it easy to find stories alongside the components they document. The alternative (a separate `stories/` directory) creates distance between component and story.

### 4. Mock data in a shared file

**Decision**: Create `src/lib/mock-data.ts` with typed mock objects for `ImageSummary`, `ImageDetail`, `Detection`, etc.

**Rationale**: Multiple stories share the same data shapes (e.g., `ImageCard` and image detail stories both need `ImageSummary`). A shared mock file avoids duplication and keeps stories clean.

### 5. Dark mode via Storybook global type / toolbar

**Decision**: Use Storybook's `globalTypes` to add a theme toggle that adds/removes the `dark` class on the preview element, matching the app's approach.

**Rationale**: The app uses Tailwind's `dark:` variant with class strategy. Storybook's decorator system can toggle this class, enabling both light and dark story variants without changing component code.

### Component-to-story mapping

| Component | Props needed | Mock complexity |
|---|---|---|
| `UploadForm` | `onSuccess`, `onError` callbacks | Medium — multiple states (idle, selected, uploading) |
| `ImageCard` | `image: ImageSummary` | Low — single object prop |
| `DetectionDetail` | `detections: any` | Medium — nested plate/OCR data |
| `FullscreenPreview` | `src`, `alt`, `onClose` | Low — simple props |
| `SearchForm` | `onSearch` callback | Low — callback only |
| `Pagination` | `currentPage`, `totalPages`, `onPageChange` | Low — number props |
| `Navbar` | None | Low — no props, needs routing mock |
| `ThemeToggle` | None | Low — no props |
| `DisclaimerBanner` | None | Low — no props |

## Risks / Trade-offs

- **Next.js 16 compatibility** → Mitigation: `@storybook/nextjs-vite` has official support. Test early with `npx storybook@latest dev`.
- **Tailwind CSS 4 in Storybook** → Mitigation: Import the app's `globals.css` in `.storybook/preview.ts` so Tailwind processes all classes.
- **Components with `next/link` and `next/image`** → Mitigation: The Next.js framework preset handles these. May need to configure `next.config.ts` image domains if images fail.
- **`useTheme` hook in ThemeToggle** → Mitigation: The hook accesses `document.documentElement` which works in Storybook's browser context.
