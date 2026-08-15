import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { ApiError, queryKeys } from '@/lib/api'
import { useTabLeader } from '@/hooks/useTabLeader'

const NON_RETRYABLE = new Set([400, 401, 403, 404, 422, 503])

export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && NON_RETRYABLE.has(error.status)) return false
  return failureCount < 2
}

interface ModuleQueryOptions {
  enabled?: boolean
  refetchInterval?: number | false
  staleTime?: number
}

export function useModuleQuery<T>(
  id: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: ModuleQueryOptions = {},
): UseQueryResult<T, unknown> {
  const isLeader = useTabLeader()
  const interval = options.refetchInterval ?? false
  return useQuery<T, unknown>({
    queryKey: queryKeys.module(id),
    queryFn: ({ signal }) => fetcher(signal),
    enabled: options.enabled ?? true,
    staleTime: options.staleTime ?? 15_000,
    refetchInterval: interval === false ? false : isLeader ? interval : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: shouldRetry,
  })
}

export const LIVE_INTERVAL = 10_000
export const SLOW_INTERVAL = 60_000
