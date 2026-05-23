'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import UploadForm from '@/components/UploadForm';
import { getImages, getImageUrl } from '@/lib/api';
import type { ImageSummary } from '@/lib/api';
import Link from 'next/link';
import FullscreenPreview from '@/components/FullscreenPreview';

export default function HomePage() {
  const router = useRouter();
  const [recentImages, setRecentImages] = useState<ImageSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [preview, setPreview] = useState<{ src: string; alt: string } | null>(null);

  const loadRecent = async () => {
    try {
      const data = await getImages({ page_size: 9 });
      setRecentImages(data.results);
    } catch {
      // silently fail — recent uploads is supplementary
    } finally {
      setLoaded(true);
    }
  };

  if (!loaded) loadRecent();

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-light bg-gradient-to-r from-[#667eea] to-[#764ba2] bg-clip-text text-transparent">
          License Plate Recognition
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">Upload an image to detect and recognize license plates</p>
      </div>

      {error && (
        <div className="max-w-2xl mx-auto mb-4 p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg text-red-700 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="max-w-2xl mx-auto mb-12">
        <UploadForm
          onSuccess={(data) => {
            const id = data?.image_id || data?.id;
            if (id) router.push(`/image/${id}`);
          }}
          onError={setError}
        />
      </div>

      {recentImages.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Recent Uploads</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recentImages.map((img) => {
              const imgSrc = img.processed_image_url
                ? getImageUrl(img.processed_image_url)
                : img.original_image_url
                  ? getImageUrl(img.original_image_url)
                  : null;
              return (
                <div key={img.id} className="bg-white dark:bg-[#1a1a1a] rounded-lg shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
                  <div
                    className={`aspect-video bg-gray-200 dark:bg-[#2d2d2d] flex items-center justify-center ${imgSrc ? 'cursor-zoom-in' : ''}`}
                    onClick={() => imgSrc && setPreview({ src: imgSrc, alt: img.filename })}
                  >
                    {imgSrc ? (
                      <img src={imgSrc} alt={img.filename} className="w-full h-full object-cover" />
                    ) : (
                      <svg className="w-12 h-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    )}
                  </div>
                  <Link href={`/image/${img.id}`} className="block p-3 hover:bg-gray-50 dark:hover:bg-[#2d2d2d] transition-colors">
                    <p className="text-sm font-medium truncate">{img.filename}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {img.upload_timestamp ? new Date(img.upload_timestamp).toLocaleString() : ''}
                    </p>
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {preview && (
        <FullscreenPreview src={preview.src} alt={preview.alt} onClose={() => setPreview(null)} />
      )}
    </div>
  );
}
