/**
 * SSE-based Parser Stream Hook
 * Real-time updates через Server-Sent Events (EventSource)
 * 
 * ARCHITECTURE:
 * - Native EventSource API для SSE connection
 * - Automatic reconnection на disconnect
 * - Zustand store integration для global state
 * - Graceful cleanup on unmount/completion
 * 
 * USAGE:
 * const { isConnected, progress } = useParserStream(jobId);
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import type { ParserJobResult } from '@/api/services';
import { toast } from 'sonner';

// ============================================================================
// Types
// ============================================================================

/**
 * SSE Event types от backend
 */
type ParserEventType = 
  | 'connected'       // Initial connection established
  | 'progress'        // Progress update (reviews parsed so far)
  | 'complete'        // Job completed successfully
  | 'error'           // Job failed
  | 'heartbeat';      // Keep-alive ping

/**
 * Progress update payload
 */
interface ProgressData {
  current: number;      // Reviews processed so far
  total: number;        // Total reviews to process
  percentage: number;   // Completion percentage (0-100)
  stage: string;        // Current stage (parsing, analyzing, saving)
}

/**
 * SSE Message structure
 */
interface ParserStreamMessage {
  event: ParserEventType;
  data: {
    job_id: string;
    status: 'queued' | 'in_progress' | 'succeeded' | 'failed';
    progress?: ProgressData;
    result?: ParserJobResult;
    error?: string;
    timestamp?: string;
  };
}

/**
 * Hook options
 */
interface UseParserStreamOptions {
  /**
   * Enable automatic connection when jobId changes
   * @default true
   */
  autoConnect?: boolean;
  
  /**
   * Callback on successful completion
   */
  onComplete?: (result: ParserJobResult) => void;
  
  /**
   * Callback on error
   */
  onError?: (error: string) => void;
  
  /**
   * Callback on progress update
   */
  onProgress?: (progress: ProgressData) => void;
  
  /**
   * Enable debug logging
   * @default false
   */
  debug?: boolean;
  
  /**
   * Automatic reconnection attempts
   * @default 3
   */
  maxReconnectAttempts?: number;
  
  /**
   * Reconnection delay in ms
   * @default 2000
   */
  reconnectDelay?: number;
}

/**
 * Hook return value
 */
interface UseParserStreamReturn {
  /**
   * Is EventSource connected
   */
  isConnected: boolean;
  
  /**
   * Current progress data
   */
  progress: ProgressData | null;
  
  /**
   * Manual connect function
   */
  connect: () => void;
  
  /**
   * Manual disconnect function
   */
  disconnect: () => void;
  
  /**
   * Connection error
   */
  connectionError: string | null;
  
  /**
   * Reconnection attempts count
   */
  reconnectAttempts: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * SSE-based Parser Stream Hook
 * 
 * @example
 * ```tsx
 * function ParserJobsTable() {
 *   const { parserJobId } = useParser();
 *   
 *   const { isConnected, progress } = useParserStream(parserJobId, {
 *     onComplete: (result) => {
 *       toast.success(`Parsed ${result.reviews_saved} reviews!`);
 *       refetch();
 *     },
 *     onError: (error) => {
 *       toast.error(`Parser failed: ${error}`);
 *     }
 *   });
 *   
 *   return (
 *     <div>
 *       {isConnected && progress && (
 *         <ProgressBar value={progress.percentage} />
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useParserStream(
  jobId: string | null,
  options: UseParserStreamOptions = {}
): UseParserStreamReturn {
  const {
    autoConnect = true,
    onComplete,
    onError,
    onProgress,
    debug = false,
    maxReconnectAttempts = 3,
    reconnectDelay = 2000,
  } = options;
  
  // ============================================================================
  // State
  // ============================================================================
  
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  
  // Zustand store access
  const updateParserState = useAppStore(state => ({
    setStatus: (status: 'queued' | 'in_progress' | 'succeeded' | 'failed') => {
      state.parserStatus = status;
    },
    setResult: (result: ParserJobResult) => {
      state.parserResult = result;
    },
    setError: (error: string) => {
      state.parserError = error;
    },
  }));
  
  // ============================================================================
  // Refs
  // ============================================================================
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  
  // ============================================================================
  // Logging Utility
  // ============================================================================
  
  const log = useCallback((...args: unknown[]) => {
    if (debug) {
      console.log('[ParserStream]', ...args);
    }
  }, [debug]);
  
  // ============================================================================
  // Disconnect Function
  // ============================================================================
  
  const disconnect = useCallback(() => {
    log('Disconnecting...');
    
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    // Close EventSource
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    setIsConnected(false);
    setProgress(null);
    setConnectionError(null);
    setReconnectAttempts(0);
  }, [log]);
  
  // ============================================================================
  // Connect Function
  // ============================================================================
  
  const connect = useCallback(() => {
    if (!jobId) {
      log('No jobId provided, skipping connection');
      return;
    }
    
    if (eventSourceRef.current) {
      log('Already connected, skipping');
      return;
    }
    
    log(`Connecting to SSE stream for job: ${jobId}`);
    
    // Construct SSE endpoint URL
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const sseUrl = `${baseUrl}/api/v1/parser/stream/${jobId}`;
    
    try {
      // Create EventSource connection
      const eventSource = new EventSource(sseUrl, {
        withCredentials: true, // Include auth cookies/headers
      });
      
      eventSourceRef.current = eventSource;
      
      // ========================================================================
      // Event Handlers
      // ========================================================================
      
      /**
       * Connection opened
       */
      eventSource.onopen = () => {
        if (!isMountedRef.current) return;
        
        log('SSE connection opened');
        setIsConnected(true);
        setConnectionError(null);
        setReconnectAttempts(0);
        
        // Update Zustand store
        updateParserState.setStatus('in_progress');
      };
      
      /**
       * Generic message handler (default event type)
       */
      eventSource.onmessage = (event: MessageEvent) => {
        if (!isMountedRef.current) return;
        
        try {
          const message: ParserStreamMessage = JSON.parse(event.data);
          log('Received message:', message);
          
          // Update Zustand store with latest status
          if (message.data.status) {
            updateParserState.setStatus(message.data.status);
          }
          
          // Handle different event types
          switch (message.event) {
            case 'connected':
              log('Connection confirmed by server');
              break;
            
            case 'progress':
              if (message.data.progress) {
                setProgress(message.data.progress);
                onProgress?.(message.data.progress);
                log(`Progress: ${message.data.progress.percentage}%`);
              }
              break;
            
            case 'complete':
              log('Job completed successfully');
              
              if (message.data.result) {
                updateParserState.setResult(message.data.result);
                onComplete?.(message.data.result);
                
                toast.success('Parser completed!', {
                  description: `Parsed ${message.data.result.reviews_saved} reviews`,
                });
              }
              
              // Auto-disconnect on completion
              disconnect();
              break;
            
            case 'error':
              log('Job failed:', message.data.error);
              
              const errorMsg = message.data.error || 'Unknown error';
              updateParserState.setError(errorMsg);
              onError?.(errorMsg);
              
              toast.error('Parser failed', {
                description: errorMsg,
              });
              
              // Auto-disconnect on error
              disconnect();
              break;
            
            case 'heartbeat':
              // Keep-alive ping, no action needed
              log('Heartbeat received');
              break;
            
            default:
              log('Unknown event type:', message.event);
          }
        } catch (err) {
          console.error('[ParserStream] Failed to parse message:', err);
        }
      };
      
      /**
       * Connection error handler
       */
      eventSource.onerror = (error) => {
        if (!isMountedRef.current) return;
        
        log('SSE connection error:', error);
        
        // Close current connection
        eventSource.close();
        eventSourceRef.current = null;
        setIsConnected(false);
        
        // Attempt reconnection if under max attempts
        if (reconnectAttempts < maxReconnectAttempts) {
          const nextAttempt = reconnectAttempts + 1;
          setReconnectAttempts(nextAttempt);
          
          const delay = reconnectDelay * nextAttempt; // Exponential backoff
          
          log(`Reconnecting in ${delay}ms (attempt ${nextAttempt}/${maxReconnectAttempts})`);
          
          setConnectionError(`Connection lost. Reconnecting... (${nextAttempt}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current && jobId) {
              connect();
            }
          }, delay);
        } else {
          // Max reconnect attempts exceeded
          const errorMsg = 'Connection failed after multiple attempts';
          setConnectionError(errorMsg);
          
          toast.error('Connection lost', {
            description: errorMsg,
          });
          
          log('Max reconnect attempts exceeded');
        }
      };
      
      /**
       * Named event listeners (alternative to onmessage)
       * Backend can send events like: event: progress\ndata: {...}
       */
      eventSource.addEventListener('progress', (event: MessageEvent) => {
        eventSource.onmessage?.(event);
      });
      
      eventSource.addEventListener('complete', (event: MessageEvent) => {
        eventSource.onmessage?.(event);
      });
      
      eventSource.addEventListener('error_event', (event: MessageEvent) => {
        eventSource.onmessage?.(event);
      });
      
    } catch (err) {
      console.error('[ParserStream] Failed to create EventSource:', err);
      setConnectionError('Failed to establish connection');
      
      toast.error('Connection failed', {
        description: 'Unable to connect to parser stream',
      });
    }
  }, [
    jobId,
    log,
    updateParserState,
    onComplete,
    onError,
    onProgress,
    reconnectAttempts,
    maxReconnectAttempts,
    reconnectDelay,
    disconnect,
  ]);
  
  // ============================================================================
  // Effects
  // ============================================================================
  
  /**
   * Auto-connect on jobId change
   */
  useEffect(() => {
    if (autoConnect && jobId) {
      connect();
    }
    
    return () => {
      // Cleanup on unmount or jobId change
      disconnect();
    };
  }, [jobId, autoConnect, connect, disconnect]);
  
  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    isMountedRef.current = true;
    
    return () => {
      isMountedRef.current = false;
      disconnect();
    };
  }, [disconnect]);
  
  // ============================================================================
  // Return
  // ============================================================================
  
  return {
    isConnected,
    progress,
    connect,
    disconnect,
    connectionError,
    reconnectAttempts,
  };
}

// ============================================================================
// Utility Hook: useParserStreamStatus
// ============================================================================

/**
 * Simplified hook for components that only need connection status
 */
export function useParserStreamStatus(jobId: string | null) {
  const { isConnected, progress } = useParserStream(jobId, {
    debug: false,
  });
  
  return {
    isConnected,
    progress,
    isActive: isConnected && progress !== null,
  };
}
