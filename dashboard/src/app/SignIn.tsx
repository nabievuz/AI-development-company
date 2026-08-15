import { type FormEvent, useState } from 'react'
import { KeyRound, ShieldAlert } from 'lucide-react'
import { useSession } from '@/stores/session'
import { ApiError } from '@/lib/api'

export function SignIn({ error }: { error?: unknown }) {
  const setToken = useSession((state) => state.setToken)
  const [value, setValue] = useState('')

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    const trimmed = value.trim()
    if (trimmed) setToken(trimmed)
  }

  const rejected = error instanceof ApiError && error.isUnauthorized
  const disabled = error instanceof ApiError && (error.isDisabled || error.isUnconfigured)

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <KeyRound className="size-4 text-primary" aria-hidden="true" />
          <h1 className="text-sm font-semibold tracking-tight">DasLab Operator Cockpit</h1>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          The control plane is fail-closed. Present a bearer token bound to a principal in the
          WS-E SSOT.
        </p>

        {disabled ? (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>
              {error instanceof ApiError && error.isDisabled
                ? 'ws_h_control_plane is OFF — no data is served without the flag.'
                : 'RBAC is not configured — the control plane refuses to serve (fail-closed).'}
            </span>
          </div>
        ) : null}

        <form onSubmit={submit} className="mt-4 space-y-3">
          <div>
            <label htmlFor="cp-token" className="text-xs font-medium text-muted-foreground">
              Bearer token
            </label>
            <input
              id="cp-token"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="principal token"
              className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 font-mono text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          {rejected ? (
            <p className="text-xs text-deny">Token rejected by the control plane.</p>
          ) : null}
          <button
            type="submit"
            disabled={!value.trim()}
            className="w-full rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-40"
          >
            Enter cockpit
          </button>
        </form>

        <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground">
          Your token is held in this tab only (sessionStorage) and is never persisted to disk.
          Every read is audited against your principal.
        </p>
      </div>
    </main>
  )
}
