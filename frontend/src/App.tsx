import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { DiscoveryFeed } from './pages/DiscoveryFeed'
import { BottleneckDashboard } from './pages/BottleneckDashboard'
import { HypothesisDashboard } from './pages/HypothesisDashboard'
import { GraphExplorer } from './pages/GraphExplorer'
import { SearchPage } from './pages/Search'
import { PapersBrowser } from './pages/PapersBrowser'
import { Settings } from './pages/Settings'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 2,
      staleTime: 30000,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/discovery" element={<DiscoveryFeed />} />
            <Route path="/bottlenecks" element={<BottleneckDashboard />} />
            <Route path="/hypotheses" element={<HypothesisDashboard />} />
            <Route path="/graph" element={<GraphExplorer />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/papers" element={<PapersBrowser />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
