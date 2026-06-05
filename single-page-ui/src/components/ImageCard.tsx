'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ImageSummary, getImageUrl } from '@/lib/api';
import { formatRelativeTime } from '@/lib/relative-time';
import FullscreenPreview from './FullscreenPreview';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

function ResultSummary({ image }: { image: ImageSummary }) {
  if (image.processing_status !== 'completed') {
    const statusClass = statusColors[image.processing_status] || 'bg-gray-100 text-gray-800';
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusClass}`}>
        {image.processing_status}
      </span>
    );
  }

  if (image.plate_count === 0) {
    return <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">0 plates detected</span>;
  }

  if (image.plate_count === 1 && image.ocr_count === 1 && image.first_ocr_text) {
    return (
      <span className="text-xs text-green-700 dark:text-green-400 font-semibold">
        &ldquo;{image.first_ocr_text}&rdquo;
      </span>
    );
  }

  const plateLabel = image.plate_count === 1 ? '1 plate' : `${image.plate_count} plates`;
  const ocrLabel = image.ocr_count === 1 ? '1 OCR' : `${image.ocr_count} OCR`;
  return (
    <span className="text-xs text-green-700 dark:text-green-400 font-semibold">
      {plateLabel}, {ocrLabel}
    </span>
  );
}

export default function ImageCard({ image }: { image: ImageSummary }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [relativeTime, setRelativeTime] = useState<string>('');

  useEffect(() => {
    const path = image.processed_image_url || image.original_image_url;
    if (path) {
      getImageUrl(path).then(setImgSrc);
    }
  }, [image.processed_image_url, image.original_image_url]);

  useEffect(() => {
    if (!image.upload_timestamp) return;
    const update = () => setRelativeTime(formatRelativeTime(image.upload_timestamp!) + ' · PST');
    update();
    const interval = setInterval(update, 60000);
    return () => clearInterval(interval);
  }, [image.upload_timestamp]);

  return (
    <>
      <div className="bg-white dark:bg-[#1a1a1a] rounded-lg shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
        <div
          className="aspect-video bg-gray-200 dark:bg-[#2d2d2d] flex items-center justify-center cursor-zoom-in"
          onClick={() => imgSrc && setPreview(imgSrc)}
        >
          {imgSrc ? (
            <img src={imgSrc} alt={image.filename} className="w-full h-full object-cover" />
          ) : (
            <svg className="w-12 h-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          )}
        </div>
        <Link href={`/image/${image.id}`} className="block p-3 hover:bg-gray-50 dark:hover:bg-[#2d2d2d] transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">View Details</span>
            <ResultSummary image={image} />
          </div>
          <div className="mt-2">
            <span className="text-xs text-gray-500 dark:text-gray-400">{relativeTime}</span>
          </div>
        </Link>
      </div>
      {preview && (
        <FullscreenPreview src={preview} alt={image.filename} onClose={() => setPreview(null)} />
      )}
    </>
  );
}
