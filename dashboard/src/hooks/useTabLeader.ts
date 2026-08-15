import { useEffect, useState } from 'react'
import { tabLeader } from '@/lib/tabLeader'

export function useTabLeader(): boolean {
  const [leader, setLeader] = useState(() => tabLeader.isLeader())
  useEffect(() => tabLeader.subscribe(setLeader), [])
  return leader
}
