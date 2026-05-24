'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import UploadForm from '@/components/UploadForm';
import { getImages } from '@/lib/api';
import type { ImageSummary } from '@/lib/api';
import ImageCard from '@/components/ImageCard';

export default function HomePage() {
  const router = useRouter();
  const [recentImages, setRecentImages] = useState<ImageSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const loadRecent = async () => {
    try {
      const data = await getImages({ page_size: 9 });
      setRecentImages(data.results);
    } catch {
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
            {recentImages.map((img) => (
              <ImageCard key={img.id} image={img} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
