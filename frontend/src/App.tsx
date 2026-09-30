import { useEffect } from 'react'
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
import { ResearchChat } from './pages/ResearchChat'
import { MissingLinksDashboard } from './pages/MissingLinksDashboard'
import { PaperComparison } from './pages/PaperComparison'
import { ResearchRoadmap } from './pages/ResearchRoadmap'
import { Timeline } from './pages/Timeline'
import { NoveltyDashboard } from './pages/NoveltyDashboard'
import { GapFinder } from './pages/GapFinder'
import { PaperPublisher } from './pages/PaperPublisher'
import { useAuthStore } from './store/authStore'
import { AuthScreen } from './pages/AuthScreen'

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
  const { token, checkMe, clearAuth } = useAuthStore()

  useEffect(() => {
    checkMe()

    const handleUnauthorized = () => {
      clearAuth()
    }

    window.addEventListener('gsm_auth_unauthorized', handleUnauthorized)
    return () => window.removeEventListener('gsm_auth_unauthorized', handleUnauthorized)
  }, [checkMe, clearAuth])

  if (!token) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthScreen />
      </QueryClientProvider>
    )
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/gaps" element={<GapFinder />} />
            <Route path="/publish" element={<PaperPublisher />} />
            <Route path="/discovery" element={<DiscoveryFeed />} />
            <Route path="/bottlenecks" element={<BottleneckDashboard />} />
            <Route path="/hypotheses" element={<HypothesisDashboard />} />
            <Route path="/graph" element={<GraphExplorer />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/papers" element={<PapersBrowser />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/chat" element={<ResearchChat />} />
            <Route path="/missing-links" element={<MissingLinksDashboard />} />
            <Route path="/papers/compare" element={<PaperComparison />} />
            <Route path="/roadmap" element={<ResearchRoadmap />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/novelty" element={<NoveltyDashboard />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App

