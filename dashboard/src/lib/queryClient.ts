import { QueryClient } from '@tanstack/react-query'
import { shouldRetry } from '@/hooks/useModuleQuery'

const COALESCE_MS = 300

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 15_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: true,
        refetchIntervalInBackground: false,
      },
    },
  })
}

export function createCoalescedInvalidator(client: QueryClient): () => void {
  let handle: number | null = null
  return () => {
    if (handle !== null) return
    handle = window.setTimeout(() => {
      handle = null
      void client.invalidateQueries()
    }, COALESCE_MS)
  }
}
