## ADDED Requirements

### Requirement: Storybook runs alongside the Next.js SPA
The project SHALL have a working Storybook development server that can be started independently of the Next.js dev server.

#### Scenario: Starting Storybook
- **WHEN** `npm run storybook` is executed in `single-page-ui/`
- **THEN** Storybook starts on port 6006 and all component stories load without errors

#### Scenario: Building Storybook statically
- **WHEN** `npm run build-storybook` is executed in `single-page-ui/`
- **THEN** a static Storybook build is produced in `storybook-static/`

### Requirement: All SPA components have stories
Every reusable component in `src/components/` and `src/app/disclaimer-banner.tsx` SHALL have a corresponding Storybook story file co-located in the same directory.

#### Scenario: Component coverage
- **WHEN** Storybook loads
- **THEN** stories exist for `UploadForm`, `ImageCard`, `DetectionDetail`, `FullscreenPreview`, `SearchForm`, `Pagination`, `Navbar`, `ThemeToggle`, and `DisclaimerBanner`

#### Scenario: Stories render with mock data
- **WHEN** any component story is selected in Storybook
- **THEN** the component renders with realistic mock data matching its TypeScript props interface

### Requirement: Dark mode stories work
Storybook SHALL support both light and dark theme previews matching the app's Tailwind dark mode behavior.

#### Scenario: Theme toggle in Storybook
- **WHEN** the Storybook theme toolbar item is toggled between light and dark
- **THEN** all stories re-render with the correct Tailwind `dark:` variant styles applied
