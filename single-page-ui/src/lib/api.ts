const UPLOAD_TIMEOUT_MS = parseInt(process.env.NEXT_PUBLIC_UPLOAD_TIMEOUT || '120000', 10);

export { UPLOAD_TIMEOUT_MS };

export class RateLimitError extends Error {
  retryAfter: number;
  constructor(message: string, retryAfter: number) {
    super(message);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

let _apiBase: string | null = null;
let _initPromise: Promise<string> | null = null;

async function fetchApiBase(): Promise<string> {
  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      const data = await res.json();
      return data.apiBaseUrl ?? '';
    }
  } catch {}
  return '';
}

export function initConfig(): Promise<string> {
  if (_apiBase !== null) return Promise.resolve(_apiBase);
  if (!_initPromise) {
    _initPromise = fetchApiBase().then((base) => {
      _apiBase = base;
      return base;
    });
  }
  return _initPromise;
}

export async function getApiBase(): Promise<string> {
  if (_apiBase !== null) return _apiBase;
  return initConfig();
}

export let configReady: Promise<void> = initConfig().then(() => {});

let _maxUploadBytes: number | null = null;

export async function getMaxUploadBytes(): Promise<number> {
  if (_maxUploadBytes !== null) return _maxUploadBytes;
  try {
    const base = await getApiBase();
    const res = await fetch(`${base}/api/v1/config/`);
    if (res.ok) {
      const data = await res.json();
      _maxUploadBytes = data.max_upload_bytes as number;
      return _maxUploadBytes;
    }
  } catch {}
  _maxUploadBytes = 1048576;
  return _maxUploadBytes;
}

export async function uploadImage(file: File, maxBytes: number): Promise<any> {
  const formData = new FormData();
  formData.append('image', file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

  try {
    const base = await getApiBase();
    const res = await fetch(`${base}/api/v1/ocr/`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Upload failed' }));
      if (res.status === 429) {
        const retryAfter = parseInt(res.headers.get('Retry-After') || res.headers.get('X-RateLimit-Reset') || '60', 10);
        throw new RateLimitError(err.detail || err.error || 'Too many requests', retryAfter);
      }
      throw new Error(err.error || err.error_message || 'Upload failed');
    }

    return await res.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

export interface ImageSummary {
  id: number;
  filename: string;
  processing_status: string;
  upload_timestamp: string | null;
  processing_timestamp: string | null;
  original_image_url: string | null;
  processed_image_url: string | null;
  file_size: number | null;
}

export interface PaginatedResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ImageSummary[];
}

export async function getImages(params?: {
  query?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse> {
  const searchParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        searchParams.set(key, String(value));
      }
    });
  }

  const base = await getApiBase();
  const url = `${base}/api/v1/images/${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch images');
  return res.json();
}

export interface ImageDetail extends ImageSummary {
  error_message: string | null;
  detections: any;
  processing_logs: Array<{
    status: string;
    message: string;
    timestamp: string | null;
    duration_ms: number | null;
  }>;
  api_response: any;
}

export async function getImage(id: number): Promise<ImageDetail> {
  const base = await getApiBase();
  const res = await fetch(`${base}/api/v1/images/${id}/`);
  if (!res.ok) throw new Error('Image not found');
  return res.json();
}

export async function getDownloadUrl(id: number, type: 'original' | 'processed'): Promise<string> {
  const base = await getApiBase();
  return `${base}/api/v1/download/${id}/${type}/`;
}

export async function getImageUrl(path: string | null): Promise<string> {
  if (!path) return '';
  if (path.startsWith('http')) return path;
  const base = await getApiBase();
  return `${base}${path}`;
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export interface HealthStatus {
  status: string;
  database_healthy: boolean;
  timestamp: string;
}

export async function checkHealthLight(): Promise<HealthStatus> {
  const base = await getApiBase();
  const res = await fetch(`${base}/api/v1/health-light/`);
  return res.json();
}

export interface AvailabilityPoint {
  timestamp: string;
  value: number;
}

export async function getAvailability(days: number = 3): Promise<AvailabilityPoint[]> {
  const base = await getApiBase();
  const res = await fetch(`${base}/api/v1/availability/?days=${days}`);
  if (!res.ok) throw new Error('Failed to fetch availability');
  const data = await res.json();
  return data.data ?? [];
}
