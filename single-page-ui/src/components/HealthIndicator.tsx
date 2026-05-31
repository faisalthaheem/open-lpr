'use client';

import { useHealth } from './HealthContext';

export default function HealthIndicator() {
  const { isHealthy, status, isLoading } = useHealth();

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-yellow-500" />
        </span>
        <span>Checking...</span>
      </div>
    );
  }

  if (isHealthy === false) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-red-400">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
        </span>
        <span>Service Down</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-xs text-green-400">
      <span className="relative flex h-2.5 w-2.5">
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
      </span>
      <span>Service Up</span>
    </div>
  );
}
