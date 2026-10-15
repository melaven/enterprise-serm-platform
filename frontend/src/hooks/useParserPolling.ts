/**
 * Hook для polling статуса парсера с exponential backoff и circuit breaker
 * 
 * SECURITY FIX: Предотвращает infinite polling при backend errors (500/503)
 * - Exponential backoff: 2s → 3s → 4.5s → ... → max 30s
 * - Circuit breaker: останавливается после 10 неудачных попыток
 * - Graceful cleanup: clearTimeout при unmount
 */

import { useState, useEffect, useRef } from 'react';

export interface ParserJobResult {
  reviews_found: number;
  reviews_new: number;
  reviews_saved: number;
  ai_enriched: number;
  ai_pending: number;
  duration_ms: number;
}

export interface ParserJobStatus {
  job_id: string;
  state: 'queued' | 'in_progress' | 'succeeded' | 'failed' | 'not_found';
  result: ParserJobResult | null;
  error: string | null;
}

interface PollingConfig {
  jobId: string;
  enabled?: boolean;
  maxRetries?: number;
  maxInterval?: number;
  backoffMultiplier?: number;
  onComplete?: (result: ParserJobResult) => void;
  onError?: (error: string) => void;
}

export function useParserPolling({
  jobId,
  enabled = true,
  maxRetries = 10,
  maxInterval = 30000, // 30s max
  backoffMultiplier = 1.5,
  onComplete,
  onError
}: PollingConfig) {
  const [state, setState] = useState<ParserJobStatus['state']>('in_progress');
  const [result, setResult] = useState<ParserJobResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  
  const intervalRef = useRef<number>(2000); // Start at 2s
  const timeoutIdRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled || !jobId || state === 'succeeded' || state === 'failed') {
      return;
    }

    const fetchStatus = async () => {
      // ✅ Check if still mounted before making request
      if (!isMountedRef.current) return;

      try {
        const response = await fetch(`/api/v1/parsers/status/${jobId}`);
        
        // ✅ Critical: Handle HTTP errors properly
        if (!response.ok) {
          if (response.status >= 500) {
            throw new Error(`Server error: ${response.status}`);
          }
          if (response.status === 404) {
            setState('not_found');
            const errorMsg = 'Parser job not found';
            setError(errorMsg);
            onError?.(errorMsg);
            return;
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const data: ParserJobStatus = await response.json();
        
        // ✅ Check if still mounted before updating state
        if (!isMountedRef.current) return;
        
        // ✅ Reset backoff on successful response
        setRetryCount(0);
        intervalRef.current = 2000;
        
        if (data.state === 'succeeded') {
          setState('succeeded');
          setResult(data.result);
          setError(null);
          if (data.result) {
            onComplete?.(data.result);
          }
          return;
        }
        
        if (data.state === 'failed') {
          setState('failed');
          setError(data.error || 'Unknown error');
          onError?.(data.error || 'Unknown error');
          return;
        }

        // ✅ Still in progress - schedule next poll
        if (isMountedRef.current) {
          timeoutIdRef.current = window.setTimeout(
            fetchStatus,
            intervalRef.current
          );
        }
        
      } catch (err) {
        console.error('Polling error:', err);
        
        // ✅ Check if still mounted before updating state
        if (!isMountedRef.current) return;
        
        // ✅ Circuit Breaker: stop after max retries
        if (retryCount >= maxRetries) {
          setState('failed');
          const errorMsg = `Failed after ${maxRetries} retries. Please refresh the page.`;
          setError(errorMsg);
          onError?.(errorMsg);
          return;
        }

        // ✅ Exponential backoff
        setRetryCount(prev => prev + 1);
        intervalRef.current = Math.min(
          intervalRef.current * backoffMultiplier,
          maxInterval
        );

        // Retry with new interval
        if (isMountedRef.current) {
          timeoutIdRef.current = window.setTimeout(
            fetchStatus,
            intervalRef.current
          );
        }
      }
    };

    // Start polling
    void fetchStatus();

    // ✅ Cleanup: clear timeout on unmount or when dependencies change
    return () => {
      if (timeoutIdRef.current !== null) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }
    };
  }, [jobId, enabled, state, retryCount, maxRetries, maxInterval, backoffMultiplier, onComplete, onError]);

  return { 
    state, 
    result, 
    error, 
    retryCount,
    isPolling: state === 'in_progress' || state === 'queued'
  };
}
