import type { ImageSummary, ImageDetail } from './api';

export const mockImageSummaryCompleted: ImageSummary = {
  id: 1,
  filename: 'car-plate.jpg',
  processing_status: 'completed',
  upload_timestamp: '2026-05-23T10:30:00Z',
  processing_timestamp: '2026-05-23T10:30:02Z',
  original_image_url: '/media/uploads/2026/05/23/car-plate.jpg',
  processed_image_url: '/media/uploads/2026/05/23/processed_car-plate.jpg',
  file_size: 120000,
  plate_count: 1,
  ocr_count: 1,
  first_ocr_text: 'ABC 1234',
};

export const mockImageSummaryFailed: ImageSummary = {
  id: 2,
  filename: 'bad-image.jpg',
  processing_status: 'failed',
  upload_timestamp: '2026-05-23T10:25:00Z',
  processing_timestamp: null,
  original_image_url: '/media/uploads/2026/05/23/bad-image.jpg',
  processed_image_url: null,
  file_size: 85000,
  plate_count: 0,
  ocr_count: 0,
  first_ocr_text: null,
};

export const mockImageSummaryPending: ImageSummary = {
  id: 3,
  filename: 'pending.jpg',
  processing_status: 'pending',
  upload_timestamp: '2026-05-23T10:35:00Z',
  processing_timestamp: null,
  original_image_url: '/media/uploads/2026/05/23/pending.jpg',
  processed_image_url: null,
  file_size: 50000,
  plate_count: 0,
  ocr_count: 0,
  first_ocr_text: null,
};

export const mockDetection = {
  plate: {
    confidence: 0.98,
    coordinates: { x1: 176, y1: 202, x2: 378, y2: 259 },
  },
  ocr: [
    {
      text: 'ABC 1234',
      confidence: 0.95,
      coordinates: { x1: 180, y1: 188, x2: 300, y2: 198 },
    },
  ],
};

export const mockDetectionMultiplePlates = [
  {
    plate: {
      confidence: 0.97,
      coordinates: { x1: 100, y1: 150, x2: 300, y2: 200 },
    },
    ocr: [
      {
        text: 'XYZ 5678',
        confidence: 0.93,
        coordinates: { x1: 105, y1: 140, x2: 290, y2: 155 },
      },
    ],
  },
  {
    plate: {
      confidence: 0.89,
      coordinates: { x1: 400, y1: 300, x2: 600, y2: 350 },
    },
    ocr: [
      {
        text: 'DEF 9012',
        confidence: 0.91,
        coordinates: { x1: 405, y1: 290, x2: 590, y2: 305 },
      },
    ],
  },
];

export const mockImageDetail: ImageDetail = {
  ...mockImageSummaryCompleted,
  error_message: null,
  detections: [mockDetection],
  processing_logs: [
    {
      status: 'success',
      message: 'Processing completed successfully',
      timestamp: '2026-05-23T10:30:02Z',
      duration_ms: 2019,
    },
    {
      status: 'api_call',
      message: 'Starting Phase 1: License plate detection',
      timestamp: '2026-05-23T10:30:00Z',
      duration_ms: 1122,
    },
    {
      status: 'started',
      message: 'API OCR processing started',
      timestamp: '2026-05-23T10:30:00Z',
      duration_ms: 12,
    },
  ],
  api_response: {
    filename: 'car-plate.jpg',
    detections: [mockDetection],
  },
};
