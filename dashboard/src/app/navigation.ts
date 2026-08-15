import {
  Activity,
  BadgeCheck,
  Banknote,
  Blocks,
  Brain,
  ClipboardList,
  Flag,
  GaugeCircle,
  Inbox,
  KeyRound,
  LayoutDashboard,
  ListTree,
  ScrollText,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import type { ComponentType } from 'react'
import type { ModuleId } from '@/lib/types'

export interface NavItem {
  module: ModuleId
  path: string
  label: string
  group: string
  icon: ComponentType<{ className?: string }>
}

export const NAV_GROUPS = ['Command', 'Engineering', 'Operations', 'Governance'] as const

export const NAV_ITEMS: NavItem[] = [
  { module: 'overview', path: '/', label: 'Overview', group: 'Command', icon: LayoutDashboard },
  { module: 'org.directory', path: '/org', label: 'Org Directory', group: 'Command', icon: ListTree },
  { module: 'product.board', path: '/board', label: 'Board & Risk', group: 'Command', icon: ClipboardList },
  { module: 'engineering.waves', path: '/waves', label: 'Wave Timeline', group: 'Engineering', icon: Activity },
  { module: 'engineering.runs', path: '/runs', label: 'Run Feed', group: 'Engineering', icon: ScrollText },
  { module: 'engineering.agents', path: '/agents', label: 'Agent Usage', group: 'Engineering', icon: Blocks },
  { module: 'engineering.tools', path: '/tools', label: 'Tool Usage', group: 'Engineering', icon: Wrench },
  { module: 'engineering.quality', path: '/quality', label: 'Quality Health', group: 'Engineering', icon: BadgeCheck },
  { module: 'operations.metrics', path: '/metrics', label: 'Metrics T1–T7', group: 'Operations', icon: GaugeCircle },
  { module: 'operations.memory', path: '/memory', label: 'Memory Health', group: 'Operations', icon: Brain },
  { module: 'operations.cost', path: '/cost', label: 'Budget Burn', group: 'Operations', icon: Banknote },
  { module: 'governance.interrupts', path: '/interrupts', label: 'Action Console', group: 'Governance', icon: Inbox },
  { module: 'governance.gates', path: '/gates', label: 'GATE-6 Decisions', group: 'Governance', icon: ShieldCheck },
  { module: 'governance.rbac', path: '/access', label: 'Access Control', group: 'Governance', icon: KeyRound },
  { module: 'governance.flags', path: '/flags', label: 'Feature Flags', group: 'Governance', icon: Flag },
  { module: 'governance.audit', path: '/audit', label: 'Audit Trail', group: 'Governance', icon: ScrollText },
]

export function navFor(modules: ModuleId[]): NavItem[] {
  const allowed = new Set(modules)
  return NAV_ITEMS.filter((item) => allowed.has(item.module))
}

export function moduleForPath(path: string): ModuleId | null {
  return NAV_ITEMS.find((item) => item.path === path)?.module ?? null
}
