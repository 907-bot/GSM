import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

interface RoadmapResult {
  topic: string
  timeframe_years: number
  roadmap: string
  gaps_included: boolean
}

export function ResearchRoadmap() {
  const [topic, setTopic] = useState('')
  const [timeframe, setTimeframe] = useState(3)
  const [includeGaps, setIncludeGaps] = useState(true)
  const [trigger, setTrigger] = useState(false)

  const { data, isLoading, error, refetch } = useQuery<RoadmapResult>({
    queryKey: ['roadmap', topic, timeframe, includeGaps],
    queryFn: async () => {
      const response = await fetch('/api/roadmap/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, timeframe_years: timeframe, include_gaps: includeGaps }),
      })
      if (!response.ok) {
        throw new Error('Failed to generate roadmap. Please check API.')
      }
      return response.json()
    },
    enabled: trigger && !!topic,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (topic) {
      setTrigger(true)
      refetch()
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Research Roadmap Generator
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: 15 }}>
          Generate an AI roadmap targeting a research field. Automatically integrates unexplored graph gaps.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
        padding: 24, borderRadius: 16, display: 'flex', flexDirection: 'column', gap: 20,
        marginBottom: 32
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, color: '#94a3b8' }}>Research Topic / Goal:</label>
          <input
            type="text"
            value={topic}
            onChange={e => setTopic(e.target.value)}
            placeholder="e.g. CRISPR therapeutics for Parkinson's disease"
            required
            style={{
              padding: '12px 16px', borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
              color: '#e2e8f0', fontSize: 14, outline: 'none'
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 13, color: '#94a3b8' }}>Timeframe (Years):</label>
            <select
              value={timeframe}
              onChange={e => setTimeframe(parseInt(e.target.value))}
              style={{
                padding: '10px 14px', borderRadius: 8,
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                color: '#e2e8f0', fontSize: 14, outline: 'none', width: 140
              }}
            >
              {[1, 2, 3, 5, 7, 10].map(y => <option key={y} value={y}>{y} {y === 1 ? 'Year' : 'Years'}</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 24 }}>
            <input
              type="checkbox"
              id="includeGaps"
              checked={includeGaps}
              onChange={e => setIncludeGaps(e.target.checked)}
              style={{ width: 18, height: 18, accentColor: '#6366f1' }}
            />
            <label htmlFor="includeGaps" style={{ fontSize: 13, color: '#94a3b8', cursor: 'pointer' }}>
              Auto-inject identified knowledge graph gaps
            </label>
          </div>
        </div>

        <button
          type="submit"
          style={{
            padding: '12px 24px', background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            border: 'none', borderRadius: 8, color: '#ffffff', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', alignSelf: 'flex-start', transition: 'opacity 0.2s'
          }}
        >
          {isLoading ? 'Generating Roadmap...' : 'Generate Roadmap'}
        </button>
      </form>

      {isLoading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <div style={{ display: 'inline-block', width: 32, height: 32, border: '3px solid rgba(99,102,241,0.3)', borderTopColor: '#6366f1', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <p style={{ marginTop: 16, color: '#94a3b8', fontSize: 14 }}>Analyzing database & formulating timeline milestones...</p>
        </div>
      )}

      {error && (
        <div style={{ padding: '16px 20px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, color: '#fca5a5', marginBottom: 24 }}>
          {(error as Error).message}
        </div>
      )}

      {data && (
        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          padding: 32, borderRadius: 20, whiteSpace: 'pre-wrap', lineHeight: 1.7,
          color: '#e2e8f0', fontSize: 15
        }}>
          {data.roadmap}
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
