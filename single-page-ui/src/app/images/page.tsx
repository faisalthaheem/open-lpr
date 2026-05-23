'use client';

import { useState, useEffect, useCallback } from 'react';
import { getImages } from '@/lib/api';
import type { ImageSummary } from '@/lib/api';
import SearchForm from '@/components/SearchForm';
import ImageCard from '@/components/ImageCard';
import Pagination from '@/components/Pagination';

export default function ImagesPage() {
  const [images, setImages] = useState<ImageSummary[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [searchParams, setSearchParams] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchImages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getImages({ ...searchParams, page, page_size: pageSize });
      setImages(data.results);
      setCount(data.count);
    } catch {
      setError('Failed to load images');
    } finally {
      setLoading(false);
    }
  }, [searchParams, page, pageSize]);

  useEffect(() => { fetchImages(); }, [fetchImages]);

  const handleSearch = (params: Record<string, string>) => {
    setSearchParams(params);
    setPage(1);
  };

  const totalPages = Math.ceil(count / pageSize);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold mb-6">Image History</h1>

      <SearchForm onSearch={handleSearch} />

      {error && (
        <div className="p-3 mb-4 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg text-red-700 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <svg className="animate-spin w-8 h-8 text-purple-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      ) : images.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          No images found
        </div>
      ) : (
        <>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{count} image{count !== 1 ? 's' : ''} found</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {images.map((img) => (
              <ImageCard key={img.id} image={img} />
            ))}
          </div>
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
