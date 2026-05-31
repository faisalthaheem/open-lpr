'use client';

import { useState, useRef, useEffect } from 'react';
import { uploadImage, getMaxUploadBytes, UPLOAD_TIMEOUT_MS, formatBytes } from '@/lib/api';

interface UploadFormProps {
  onSuccess: (data: any) => void;
  onError: (error: string) => void;
  disabled?: boolean;
}

type UploadState = 'idle' | 'selected' | 'uploading' | 'timed_out';

export default function UploadForm({ onSuccess, onError, disabled = false }: UploadFormProps) {
  const [dragover, setDragover] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number>(0);
  const [state, setState] = useState<UploadState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [maxUploadBytes, setMaxUploadBytes] = useState<number>(1048576);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getMaxUploadBytes().then(setMaxUploadBytes);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      onError('Please select an image file');
      return;
    }
    if (file.size > maxUploadBytes) {
      onError(`File too large (${formatBytes(file.size)}). Maximum size is ${formatBytes(maxUploadBytes)}.`);
      return;
    }
    setFileName(file.name);
    setFileSize(file.size);
    setState('selected');
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleSubmit = async () => {
    const file = inputRef.current?.files?.[0];
    if (!file) {
      onError('Please select an image');
      return;
    }
    if (file.size > maxUploadBytes) {
      onError(`File too large (${formatBytes(file.size)}). Maximum size is ${formatBytes(maxUploadBytes)}.`);
      return;
    }

    setState('uploading');
    setElapsed(0);
    const start = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 500);

    try {
      const result = await uploadImage(file, maxUploadBytes);
      if (timerRef.current) clearInterval(timerRef.current);
      onSuccess(result);
    } catch (err: any) {
      if (timerRef.current) clearInterval(timerRef.current);
      if (err.name === 'AbortError') {
        setState('timed_out');
        onError(`Upload timed out after ${UPLOAD_TIMEOUT_MS / 1000}s. The server may be busy — try again.`);
      } else {
        setState('selected');
        onError(err.message || 'Upload failed');
      }
    }
  };

  const reset = () => {
    setPreview(null);
    setFileName(null);
    setFileSize(0);
    setState('idle');
    setElapsed(0);
    if (inputRef.current) inputRef.current.value = '';
  };

  const progressPct = Math.min(100, (elapsed / (UPLOAD_TIMEOUT_MS / 1000)) * 100);
  const progressColor = progressPct > 75 ? 'bg-red-500' : progressPct > 50 ? 'bg-yellow-500' : 'bg-gradient-to-r from-[#667eea] to-[#764ba2]';

  return (
    <div className="space-y-4">
      {disabled && state === 'idle' && (
        <p className="text-center text-sm text-red-500 dark:text-red-400">
          Uploads are disabled — backend service is unavailable
        </p>
      )}

      {state === 'idle' || state === 'selected' ? (
        <div
          className={`border-3 border-dashed rounded-xl p-12 text-center transition-all duration-300 ${
            disabled
              ? 'border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-[#111] opacity-50 cursor-not-allowed'
              : dragover
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 cursor-pointer'
                : 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-[#1a1a1a] hover:border-purple-500 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] cursor-pointer'
          }`}
          onDragOver={(e) => { if (disabled) return; e.preventDefault(); setDragover(true); }}
          onDragLeave={() => setDragover(false)}
          onDrop={(e) => { if (disabled) return; e.preventDefault(); setDragover(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
          onClick={() => { if (disabled) return; inputRef.current?.click(); }}
        >
          <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p className="text-gray-600 dark:text-gray-400">
            {fileName ? fileName : 'Drag and drop an image here, or click to browse'}
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Max file size: {formatBytes(maxUploadBytes)}
          </p>
        </div>
      ) : null}

      {preview && state === 'selected' && (
        <>
          <div className="flex justify-center">
            <img src={preview} alt="Preview" className="max-h-64 rounded-lg shadow-md" />
          </div>
          <div className="flex items-center justify-center space-x-3 text-sm text-gray-500 dark:text-gray-400">
            <span>{fileName}</span>
            <span>·</span>
            <span>{formatBytes(fileSize)}</span>
          </div>
          <div className="flex justify-center space-x-3">
            <button
              onClick={handleSubmit}
              disabled={disabled}
              className={`px-6 py-2 rounded-lg font-medium transition-opacity ${
                disabled
                  ? 'bg-gray-400 dark:bg-gray-600 text-gray-200 cursor-not-allowed opacity-50'
                  : 'bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white hover:opacity-90'
              }`}
            >
              Upload & Detect
            </button>
            <button
              onClick={reset}
              className="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors"
            >
              Clear
            </button>
          </div>
        </>
      )}

      {state === 'uploading' && (
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="relative">
              <svg className="w-20 h-20 animate-spin" viewBox="0 0 100 100" fill="none">
                <circle className="opacity-20" cx="50" cy="50" r="40" stroke="currentColor" strokeWidth="8" />
                <path className="text-purple-500" fill="currentColor" d="M50 10a40 40 0 0140 40h-8a32 32 0 00-32-32V10z" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-sm font-mono text-gray-500 dark:text-gray-400">{elapsed}s</span>
              </div>
            </div>
          </div>
          <div>
            <p className="text-gray-700 dark:text-gray-300 font-medium">Processing image...</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {fileName} · timeout in {Math.max(0, Math.floor(UPLOAD_TIMEOUT_MS / 1000) - elapsed)}s
            </p>
          </div>
          <div className="max-w-xs mx-auto">
            <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${progressColor}`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {state === 'timed_out' && (
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <svg className="w-16 h-16 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div>
            <p className="text-red-600 dark:text-red-400 font-medium">Request timed out</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">The server may be busy or still processing.</p>
          </div>
          <div className="flex justify-center space-x-3">
            <button
              onClick={handleSubmit}
              className="px-6 py-2 bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
            >
              Retry
            </button>
            <button
              onClick={reset}
              className="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
