## 1. Setup

- [x] 1.1 Initialize Storybook in `single-page-ui/` with `npx storybook@latest init` and the Next.js framework
- [x] 1.2 Configure `.storybook/main.ts` — set framework to `@storybook/nextjs-vite`, configure story locations (`../src/**/*.stories.tsx`)
- [x] 1.3 Configure `.storybook/preview.ts` — import `../src/app/globals.css` for Tailwind, add dark mode global type with toolbar toggle
- [x] 1.4 Add `storybook` and `build-storybook` scripts to `package.json`
- [x] 1.5 Update `.gitignore` with `storybook-static/`

## 2. Mock Data

- [x] 2.1 Create `src/lib/mock-data.ts` with typed mock objects for `ImageSummary`, `ImageDetail`, and `Detection` data

## 3. Stories — Simple Components

- [x] 3.1 Write `ThemeToggle.stories.tsx` (default, no props)
- [x] 3.2 Write `DisclaimerBanner.stories.tsx` (default, dismissed state)
- [x] 3.3 Write `Pagination.stories.tsx` (first page, middle page, last page)
- [x] 3.4 Write `SearchForm.stories.tsx` (default empty, with values)
- [x] 3.5 Write `Navbar.stories.tsx` (default, with mobile menu)

## 4. Stories — Medium Complexity Components

- [x] 4.1 Write `ImageCard.stories.tsx` (completed image, failed image, different statuses)
- [x] 4.2 Write `FullscreenPreview.stories.tsx` (with sample image, closed state)
- [x] 4.3 Write `DetectionDetail.stories.tsx` (single plate, multiple plates, no detections)
- [x] 4.4 Write `UploadForm.stories.tsx` (idle, file selected, uploading state)

## 5. Verification

- [x] 5.1 Run `npm run storybook` and verify all stories load without console errors
- [x] 5.2 Toggle dark mode in Storybook toolbar and verify all stories switch themes correctly
- [x] 5.3 Run `npm run build-storybook` and verify static build succeeds
