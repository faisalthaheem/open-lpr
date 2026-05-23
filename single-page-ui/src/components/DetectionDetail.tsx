'use client';

import { useState } from 'react';

interface Detection {
  plate?: {
    confidence: number;
    coordinates: { x1: number; y1: number; x2: number; y2: number };
  };
  ocr?: Array<{
    text: string;
    confidence: number;
    coordinates: { x1: number; y1: number; x2: number; y2: number };
  }>;
}

export default function DetectionDetail({ detections }: { detections: any }) {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  if (!detections || !detections.detections) {
    return <p className="text-gray-500 dark:text-gray-400 text-sm">No detection data available</p>;
  }

  const items: Detection[] = Array.isArray(detections.detections)
    ? detections.detections
    : Object.values(detections.detections);

  if (items.length === 0) {
    return <p className="text-gray-500 dark:text-gray-400 text-sm">No plates detected</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((det, idx) => {
        const isOpen = openIndex === idx;
        return (
          <div key={idx} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <button
              onClick={() => setOpenIndex(isOpen ? null : idx)}
              className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 dark:bg-[#1a1a1a] hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors"
            >
              <span className="font-medium text-sm">
                Plate {idx + 1}
                {det.ocr && det.ocr.length > 0 && (
                  <span className="ml-2 text-gray-500 dark:text-gray-400 font-normal">
                    ({det.ocr.length} OCR result{det.ocr.length > 1 ? 's' : ''})
                  </span>
                )}
              </span>
              <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {isOpen && (
              <div className="px-4 py-3 space-y-3 bg-white dark:bg-[#0f0f0f]">
                {det.plate && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 mb-1">Plate Bounding Box</h4>
                    <p className="text-sm font-mono">
                      ({det.plate.coordinates.x1}, {det.plate.coordinates.y1}) → ({det.plate.coordinates.x2}, {det.plate.coordinates.y2})
                      <span className="ml-2 text-gray-500">confidence: {(det.plate.confidence * 100).toFixed(1)}%</span>
                    </p>
                  </div>
                )}
                {det.ocr && det.ocr.map((ocrItem, ocrIdx) => (
                  <div key={ocrIdx}>
                    <h4 className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 mb-1">
                      OCR Result {ocrIdx + 1}
                    </h4>
                    <p className="text-lg font-medium">{ocrItem.text}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 font-mono mt-1">
                      ({ocrItem.coordinates.x1}, {ocrItem.coordinates.y1}) → ({ocrItem.coordinates.x2}, {ocrItem.coordinates.y2})
                      <span className="ml-2">confidence: {(ocrItem.confidence * 100).toFixed(1)}%</span>
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
