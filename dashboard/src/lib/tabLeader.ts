const LEASE_KEY = 'daslab.cp.poll-leader'
const CHANNEL = 'daslab.cp.leader'
const LEASE_MS = 6_000
const RENEW_MS = 2_000

interface Lease {
  id: string
  expires: number
}

function now(): number {
  return Date.now()
}

function readLease(): Lease | null {
  try {
    const raw = window.localStorage.getItem(LEASE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Lease
    return typeof parsed?.id === 'string' && typeof parsed?.expires === 'number' ? parsed : null
  } catch {
    return null
  }
}

function writeLease(lease: Lease): void {
  try {
    window.localStorage.setItem(LEASE_KEY, JSON.stringify(lease))
  } catch {
    return
  }
}

export class TabLeader {
  private readonly id = `${now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  private readonly listeners = new Set<(leader: boolean) => void>()
  private channel: BroadcastChannel | null = null
  private timer: number | null = null
  private leader = false

  start(): void {
    if (this.timer !== null) return
    if (typeof BroadcastChannel !== 'undefined') {
      this.channel = new BroadcastChannel(CHANNEL)
      this.channel.onmessage = () => this.evaluate()
    }
    document.addEventListener('visibilitychange', this.evaluate)
    this.evaluate()
    this.timer = window.setInterval(this.evaluate, RENEW_MS)
  }

  stop(): void {
    if (this.timer !== null) {
      window.clearInterval(this.timer)
      this.timer = null
    }
    document.removeEventListener('visibilitychange', this.evaluate)
    this.channel?.close()
    this.channel = null
    if (this.leader) {
      this.leader = false
      try {
        window.localStorage.removeItem(LEASE_KEY)
      } catch {
        return
      }
    }
  }

  isLeader(): boolean {
    return this.leader
  }

  subscribe(listener: (leader: boolean) => void): () => void {
    this.listeners.add(listener)
    listener(this.leader)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private readonly evaluate = (): void => {
    const hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden'
    const lease = readLease()
    const expired = !lease || lease.expires < now()
    const mine = lease?.id === this.id

    let next = this.leader
    if (hidden) {
      if (mine) {
        try {
          window.localStorage.removeItem(LEASE_KEY)
        } catch {
          next = false
        }
      }
      next = false
    } else if (mine || expired) {
      writeLease({ id: this.id, expires: now() + LEASE_MS })
      next = true
    } else {
      next = false
    }

    if (next !== this.leader) {
      this.leader = next
      this.listeners.forEach((listener) => listener(next))
      this.channel?.postMessage({ id: this.id, leader: next })
    }
  }
}

export const tabLeader = new TabLeader()
