import { create } from 'zustand'
import type { ActionId, Identity, ModuleId } from '@/lib/types'

const STORAGE_KEY = 'daslab.cp.token'

function readStoredToken(): string {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function persistToken(token: string): void {
  try {
    if (token) window.sessionStorage.setItem(STORAGE_KEY, token)
    else window.sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    return
  }
}

interface SessionState {
  token: string
  identity: Identity | null
  setToken: (token: string) => void
  setIdentity: (identity: Identity | null) => void
  signOut: () => void
}

export const useSession = create<SessionState>((set) => ({
  token: readStoredToken(),
  identity: null,
  setToken: (token) => {
    persistToken(token)
    set({ token })
  },
  setIdentity: (identity) => set({ identity }),
  signOut: () => {
    persistToken('')
    set({ token: '', identity: null })
  },
}))

export function getToken(): string {
  return useSession.getState().token
}

export function useCan(): (module: ModuleId) => boolean {
  const identity = useSession((state) => state.identity)
  return (module: ModuleId) => Boolean(identity?.modules.includes(module))
}

export function useCanAct(): (action: ActionId) => boolean {
  const identity = useSession((state) => state.identity)
  return (action: ActionId) => Boolean(identity?.actions.includes(action))
}

export function useDenialReason(): (module: ModuleId) => string {
  const identity = useSession((state) => state.identity)
  return (module: ModuleId) =>
    identity?.denied.find((entry) => entry.module === module)?.reason ?? 'not permitted'
}
