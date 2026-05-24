"use client";

import { useState, useEffect } from "react";

export default function DisclaimerBanner() {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    try {
      if (localStorage.getItem("lpr-disclaimer-dismissed") === "1") {
        setVisible(false);
      }
    } catch {}
  }, []);

  if (!visible) return null;

  return (
    <div className="bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="text-xs text-yellow-800 dark:text-yellow-300 space-y-1">
            <p className="font-semibold flex items-center gap-1">
              <svg
                className="w-3.5 h-3.5 shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              Demo System — No Liability Assumed
            </p>
            <p>
              This application is provided &quot;as is&quot; without warranties.
              Uploaded images will be <strong>retained</strong> and may be used
              for <strong>training purposes</strong>. We are not responsible for
              any consequences arising from the use of this system.
            </p>
          </div>
          <button
            onClick={() => {
              setVisible(false);
              try {
                localStorage.setItem("lpr-disclaimer-dismissed", "1");
              } catch {}
            }}
            className="shrink-0 text-yellow-600 dark:text-yellow-400 hover:text-yellow-800 dark:hover:text-yellow-200"
            aria-label="Dismiss"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
