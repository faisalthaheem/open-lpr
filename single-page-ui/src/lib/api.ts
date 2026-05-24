const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';
const UPLOAD_TIMEOUT_MS = parseInt(process.env.NEXT_PUBLIC_UPLOAD_TIMEOUT || '120000', 10);

export { UPLOAD_TIMEOUT_MS };

let _maxUploadBytes: number | null = null;

export async function getMaxUploadBytes(): Promise<number> {
  if (_maxUploadBytes !== null) return _maxUploadBytes;
  try {
    const res = await fetch(`${API_BASE}/api/v1/config/`);
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
    const res = await fetch(`${API_BASE}/api/v1/ocr/`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Upload failed' }));
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

  const url = `${API_BASE}/api/v1/images/${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
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
  const res = await fetch(`${API_BASE}/api/v1/images/${id}/`);
  if (!res.ok) throw new Error('Image not found');
  return res.json();
}

export function getDownloadUrl(id: number, type: 'original' | 'processed'): string {
  return `${API_BASE}/api/v1/download/${id}/${type}/`;
}

export function getImageUrl(path: string | null): string {
  if (!path) return '';
  if (path.startsWith('http')) return path;
  return `${API_BASE}${path}`;
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
