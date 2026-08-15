import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { configureApi } from './lib/api'
import { createQueryClient } from './lib/queryClient'
import { tabLeader } from './lib/tabLeader'
import { getToken, useSession } from './stores/session'
import './index.css'

const queryClient = createQueryClient()

configureApi(getToken, () => {
  useSession.getState().signOut()
})

let lastToken = useSession.getState().token
useSession.subscribe((state) => {
  if (state.token !== lastToken) {
    lastToken = state.token
    queryClient.clear()
  }
})

tabLeader.start()

const container = document.getElementById('root')
if (!container) throw new Error('root container missing')

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/app">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
