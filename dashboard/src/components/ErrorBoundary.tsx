import { Component, type ErrorInfo, type ReactNode } from 'react'
import { RotateCcw, ShieldAlert } from 'lucide-react'

interface Props {
  children: ReactNode
  moduleName: string
  fallback?: (error: Error, reset: () => void) => ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    if (typeof console !== 'undefined') {
      console.error(`[${this.props.moduleName}] module crashed`, error, info.componentStack)
    }
  }

  private readonly reset = (): void => {
    this.setState({ error: null })
  }

  override render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children
    if (this.props.fallback) return this.props.fallback(error, this.reset)
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-deny/30 bg-deny/5 px-4 py-8 text-center">
        <ShieldAlert className="size-5 text-deny" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-deny">
            The {this.props.moduleName} module failed
          </p>
          <p className="mt-1 max-w-prose text-xs text-muted-foreground">
            This module is isolated — the rest of the cockpit is unaffected.
          </p>
          <p className="mt-2 max-w-prose break-words font-mono text-[11px] text-muted-foreground">
            {error.message}
          </p>
        </div>
        <button
          type="button"
          onClick={this.reset}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-accent"
        >
          <RotateCcw className="size-3" aria-hidden="true" />
          Retry module
        </button>
      </div>
    )
  }
}
