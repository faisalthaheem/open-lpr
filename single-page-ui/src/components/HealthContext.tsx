'use client';

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { checkHealthLight } from '@/lib/api';

interface HealthContextValue {
  isHealthy: boolean | null;
  status: string | null;
  lastChecked: Date | null;
  isLoading: boolean;
}

const HealthContext = createContext<HealthContextValue>({
  isHealthy: null,
  status: null,
  lastChecked: null,
  isLoading: true,
});

export function useHealth() {
  return useContext(HealthContext);
}

const POLL_INTERVAL = 30_000;

export function HealthProvider({ children }: { children: React.ReactNode }) {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const mounted = useRef(true);

  const check = useCallback(async () => {
    try {
      const result = await checkHealthLight();
      if (!mounted.current) return;
      setIsHealthy(result.database_healthy);
      setStatus(result.status);
      setLastChecked(new Date());
    } catch {
      if (!mounted.current) return;
      setIsHealthy(false);
      setStatus('unhealthy');
      setLastChecked(new Date());
    } finally {
      if (mounted.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    check();
    const interval = setInterval(check, POLL_INTERVAL);
    return () => {
      mounted.current = false;
      clearInterval(interval);
    };
  }, [check]);

  return (
    <HealthContext.Provider value={{ isHealthy, status, lastChecked, isLoading }}>
      {children}
    </HealthContext.Provider>
  );
}
