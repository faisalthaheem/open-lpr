## 1. Backend CORS Setup

- [x] 1.1 Add `django-cors-headers` to `requirements.txt`
- [x] 1.2 Add `corsheaders` to `INSTALLED_APPS` and `MIDDLEWARE` (before `CommonMiddleware`) in `lpr_project/settings.py`
- [x] 1.3 Add `CORS_ALLOWED_ORIGINS` setting to `settings.py`, loaded via `config()` from `python-decouple`, defaulting to `http://localhost:3000`

## 2. Backend API Endpoints

- [x] 2.1 Create `GET /api/v1/images/` endpoint in `lpr_app/views/api_views.py` — accept `query`, `date_from`, `date_to`, `status`, `page`, `page_size` query params; return paginated JSON with `results`, `count`, `next`, `previous` fields
- [x] 2.2 Create `GET /api/v1/images/<id>/` endpoint in `lpr_app/views/api_views.py` — return full image detail including detections, OCR data, processing logs, and raw API response
- [x] 2.3 Add a `GET /api/v1/download/<id>/<type>/` endpoint that wraps the existing `FileService.download_image()` for SPA file downloads
- [x] 2.4 Register all new API URL patterns in `lpr_app/urls.py`

## 3. Next.js Project Scaffolding

- [x] 3.1 Initialize a Next.js project in `single-page-ui/` with TypeScript, Tailwind CSS, and App Router (`npx create-next-app@latest`)
- [x] 3.2 Configure `next.config.js` with `output: 'export'` for static export, `images.unoptimized: true`, and `NEXT_PUBLIC_API_BASE_URL` env variable
- [x] 3.3 Set up the root layout (`src/app/layout.tsx`) with HTML shell, metadata, global Tailwind styles, and theme provider
- [x] 3.4 Create Tailwind config with light/dark theme color variables matching the existing UI theme

## 4. Next.js Core Modules

- [x] 4.1 Create `src/lib/api.ts` — API client with configurable `NEXT_PUBLIC_API_BASE_URL`, fetch wrapper functions for `uploadImage()`, `getImages()`, `getImage(id)`, and `getDownloadUrl(id, type)`
- [x] 4.2 Create `src/hooks/useTheme.ts` — theme toggle hook with localStorage persistence and system `prefers-color-scheme` detection
- [x] 4.3 Create `src/components/Navbar.tsx` — navigation bar with links (Home, Images, Health Check) and theme toggle button
- [x] 4.4 Create `src/components/ThemeToggle.tsx` — light/dark toggle button component using `useTheme` hook

## 5. Next.js Pages and Components

- [x] 5.1 Create `src/app/page.tsx` — home page with upload form (drag-and-drop, client-side preview), loading indicator, and recent uploads grid
- [x] 5.2 Create `src/components/UploadForm.tsx` — reusable upload form component with file validation and progress feedback
- [x] 5.3 Create `src/app/images/page.tsx` — image list page with search form, filter controls, and paginated card grid
- [x] 5.4 Create `src/components/SearchForm.tsx` — search/filter form with query input, date range pickers, and status dropdown
- [x] 5.5 Create `src/components/ImageCard.tsx` — image card component displaying thumbnail, filename, status badge, and timestamp
- [x] 5.6 Create `src/components/Pagination.tsx` — pagination controls component with page number buttons and prev/next
- [x] 5.7 Create `src/app/image/[id]/page.tsx` — image detail page with original/processed comparison, detection summary, OCR results, download buttons, and processing logs
- [x] 5.8 Create `src/components/DetectionDetail.tsx` — accordion component for displaying plate detection and OCR results with coordinates and confidence scores

## 6. Docker Integration

- [x] 6.1 Create `single-page-ui/Dockerfile` — multi-stage build: stage 1 installs deps and builds (`next build`), stage 2 copies static export to `nginx:alpine`
- [x] 6.2 Create `single-page-ui/nginx.conf` with SPA static serving and API proxy pass configuration for `/api/`, `/health/`, `/metrics/`, and `/media/`
- [x] 6.3 Add a `spa` service to `docker-compose.yaml` (profile: `core`) building from `single-page-ui/`, exposing port 3000

## 7. Verification

- [x] 7.1 Start both backend and SPA locally (`python manage.py runserver` + `npm run dev`); upload an image via the SPA and confirm it appears in the image list
- [x] 7.2 Navigate to image detail in the SPA and confirm all detection/OCR data renders correctly
- [x] 7.3 Verify download buttons work for original and processed images
- [x] 7.4 Verify CORS works when SPA is served on a different port than the backend
