'use client';

import { useState, useEffect, ReactNode } from 'react';
import { initConfig } from '@/lib/api';

const INIT_TIMEOUT_MS = 10000;

export default function AppInitializer({ children }: { children: ReactNode }) {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setState('error');
      setErrorMsg('Initialization timed out. The backend may be unavailable.');
    }, INIT_TIMEOUT_MS);

    initConfig()
      .then(() => {
        clearTimeout(timer);
        setState('ready');
      })
      .catch(() => {
        clearTimeout(timer);
        setErrorMsg('Failed to connect to the backend. Please check your configuration.');
        setState('error');
      });

    return () => clearTimeout(timer);
  }, []);

  if (state === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <svg className="animate-spin w-12 h-12 text-purple-500 mb-4" viewBox="0 0 100 100" fill="none">
          <circle className="opacity-20" cx="50" cy="50" r="40" stroke="currentColor" strokeWidth="8" />
          <path className="text-purple-500" fill="currentColor" d="M50 10a40 40 0 0140 40h-8a32 32 0 00-32-32V10z" />
        </svg>
        <p className="text-gray-600 dark:text-gray-400 text-sm">Initializing...</p>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <svg className="w-16 h-16 text-red-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <p className="text-red-600 dark:text-red-400 font-medium mb-2">Initialization Failed</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{errorMsg}</p>
        <button
          onClick={() => {
            setState('loading');
            setErrorMsg('');
            initConfig()
              .then(() => setState('ready'))
              .catch(() => {
                setErrorMsg('Failed to connect to the backend. Please check your configuration.');
                setState('error');
              });
          }}
          className="px-6 py-2 bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
        >
          Retry
        </button>
      </div>
    );
  }

  return <>{children}</>;
}
