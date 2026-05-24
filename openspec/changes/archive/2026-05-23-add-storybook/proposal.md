## Why

The SPA has 9 components (`UploadForm`, `ImageCard`, `DetectionDetail`, `FullscreenPreview`, `SearchForm`, `Pagination`, `Navbar`, `ThemeToggle`, `DisclaimerBanner`) with no isolated component development or visual testing workflow. Adding Storybook provides a dedicated environment for developing, documenting, and visually testing each component in isolation — catching UI regressions early and serving as living documentation for the component library.

## What Changes

- Add Storybook 9 to the `single-page-ui/` Next.js project
- Configure Storybook for Next.js 16 + Tailwind CSS 4 compatibility
- Write stories for all 9 existing components
- Add a `storybook` npm script to `package.json`
- Add Storybook build caching config to `.gitignore`

## Capabilities

### New Capabilities

- `storybook-ui`: Component development environment using Storybook — stories, configuration, and tooling for isolated component development and visual documentation

### Modified Capabilities

_None — no existing spec-level behavior changes._

## Impact

- **Dependencies**: New dev dependencies (`@storybook/nextjs-vite`, `@storybook/react`, `storybook`, etc.) in `single-page-ui/package.json`
- **Configuration**: New `.storybook/` directory in `single-page-ui/` with `main.ts` and `preview.ts`
- **Stories**: New `*.stories.tsx` files alongside each component
- **Scripts**: New `storybook` and `build-storybook` npm scripts
- **Git**: `.gitignore` updates for Storybook build cache
- **No impact**: Django backend, existing Next.js pages/routes, or production builds
