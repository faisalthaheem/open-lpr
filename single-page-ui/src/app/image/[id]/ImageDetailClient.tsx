'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { getImage, getImageUrl, getDownloadUrl } from '@/lib/api';
import type { ImageDetail } from '@/lib/api';
import DetectionDetail from '@/components/DetectionDetail';
import FullscreenPreview from '@/components/FullscreenPreview';

export default function ImageDetailClient() {
  const params = useParams();
  const id = Number(params.id);
  const [image, setImage] = useState<ImageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ src: string; alt: string } | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string>('');
  const [processedUrl, setProcessedUrl] = useState<string>('');
  const [downloadOriginalUrl, setDownloadOriginalUrl] = useState<string>('');
  const [downloadProcessedUrl, setDownloadProcessedUrl] = useState<string>('');

  useEffect(() => {
    if (!id) return;
    getImage(id)
      .then((img) => {
        setImage(img);
        if (img.original_image_url) getImageUrl(img.original_image_url).then(setOriginalUrl);
        if (img.processed_image_url) getImageUrl(img.processed_image_url).then(setProcessedUrl);
        getDownloadUrl(img.id, 'original').then(setDownloadOriginalUrl);
        getDownloadUrl(img.id, 'processed').then(setDownloadProcessedUrl);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <svg className="animate-spin w-8 h-8 text-purple-500" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (error || !image) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-red-600 dark:text-red-400 text-lg">{error || 'Image not found'}</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{image.filename}</h1>
        <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500 dark:text-gray-400">
          <span>ID: {image.id}</span>
          <span>Uploaded: {image.upload_timestamp ? new Date(image.upload_timestamp).toLocaleString() : 'N/A'}</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[image.processing_status] || ''}`}>
            {image.processing_status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-lg font-medium mb-2">Original</h2>
          <div className="bg-gray-100 dark:bg-[#1a1a1a] rounded-lg overflow-hidden">
            {originalUrl ? (
              <img
                src={originalUrl}
                alt="Original"
                className="w-full h-auto cursor-zoom-in"
                onClick={() => setPreview({ src: originalUrl, alt: 'Original' })}
              />
            ) : (
              <div className="p-12 text-center text-gray-400">No image</div>
            )}
          </div>
          <a
            href={downloadOriginalUrl}
            className="inline-block mt-2 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors"
          >
            Download Original
          </a>
        </div>
        <div>
          <h2 className="text-lg font-medium mb-2">Processed</h2>
          <div className="bg-gray-100 dark:bg-[#1a1a1a] rounded-lg overflow-hidden">
            {processedUrl ? (
              <img
                src={processedUrl}
                alt="Processed"
                className="w-full h-auto cursor-zoom-in"
                onClick={() => setPreview({ src: processedUrl, alt: 'Processed' })}
              />
            ) : (
              <div className="p-12 text-center text-gray-400">No processed image</div>
            )}
          </div>
          {image.processed_image_url && (
            <a
              href={downloadProcessedUrl}
              className="inline-block mt-2 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors"
            >
              Download Processed
            </a>
          )}
        </div>
      </div>

      {image.error_message && (
        <div className="mb-6 p-4 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg text-red-700 dark:text-red-400">
          <h3 className="font-semibold mb-1">Error</h3>
          <p className="text-sm">{image.error_message}</p>
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-lg font-medium mb-3">Detection Results</h2>
        <DetectionDetail detections={image.detections} />
      </div>

      {image.processing_logs && image.processing_logs.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-medium mb-3">Processing Logs</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 px-3">Status</th>
                  <th className="text-left py-2 px-3">Message</th>
                  <th className="text-left py-2 px-3">Time</th>
                  <th className="text-left py-2 px-3">Duration</th>
                </tr>
              </thead>
              <tbody>
                {image.processing_logs.map((log, idx) => (
                  <tr key={idx} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 px-3">{log.status}</td>
                    <td className="py-2 px-3">{log.message}</td>
                    <td className="py-2 px-3 text-gray-500 dark:text-gray-400">{log.timestamp ? new Date(log.timestamp).toLocaleString() : ''}</td>
                    <td className="py-2 px-3 text-gray-500 dark:text-gray-400">{log.duration_ms ? `${log.duration_ms}ms` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {image.api_response && (
        <div>
          <h2 className="text-lg font-medium mb-3">Raw API Response</h2>
          <pre className="bg-gray-100 dark:bg-[#1a1a1a] p-4 rounded-lg overflow-x-auto text-xs font-mono">
            {JSON.stringify(image.api_response, null, 2)}
          </pre>
        </div>
      )}

      {preview && (
        <FullscreenPreview src={preview.src} alt={preview.alt} onClose={() => setPreview(null)} />
      )}
    </div>
  );
}
