import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { api } from '../api'

interface RoadmapResult {
  topic: string
  timeframe_years: number
  timeframe_weeks: number
  roadmap: string
  gaps_included: boolean
  sources?: any[]
}

export function ResearchRoadmap() {
  const [topic, setTopic] = useState('')
  const [timeframeWeeks, setTimeframeWeeks] = useState(1)
  const [includeGaps, setIncludeGaps] = useState(true)
  const [trigger, setTrigger] = useState(false)

  const { data, isLoading, error, refetch } = useQuery<RoadmapResult>({
    queryKey: ['roadmap', topic, timeframeWeeks, includeGaps],
    queryFn: () => api.generateRoadmap(topic, timeframeWeeks, includeGaps),
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
            <label style={{ fontSize: 13, color: '#94a3b8' }}>Timeline:</label>
            <select
              value={timeframeWeeks}
              onChange={e => setTimeframeWeeks(parseInt(e.target.value))}
              style={{
                padding: '10px 14px', borderRadius: 8,
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                color: '#e2e8f0', fontSize: 14, outline: 'none', width: 180
              }}
            >
              {[
                [1, '1 week'],
                [2, '2 weeks'],
                [4, '1 month'],
                [12, '3 months'],
                [26, '6 months'],
                [52, '1 year'],
                [156, '3 years'],
                [260, '5 years'],
              ].map(([weeks, label]) => <option key={weeks} value={weeks}>{label}</option>)}
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
            padding: 32, borderRadius: 20, whiteSpace: 'pre-wrap', lineHeight: 1.7,
            color: '#e2e8f0', fontSize: 15
          }}>
            {data.roadmap}
          </div>
          {!!data.sources?.length && (
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)', padding: 24, borderRadius: 16 }}>
              <h3 style={{ margin: '0 0 14px', fontSize: 15, color: '#f1f5f9' }}>Research Sources</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.sources.map((source, i) => (
                  <a key={i} href={source.url || (source.doi ? `https://doi.org/${source.doi}` : '#')} target="_blank" rel="noreferrer" style={{ display: 'flex', gap: 10, alignItems: 'center', color: '#a5b4fc', textDecoration: 'none', fontSize: 13 }}>
                    <ExternalLink size={14} />
                    <span>{source.title || 'Untitled source'} <span style={{ color: '#64748b' }}>({source.source})</span></span>
                  </a>
                ))}
              </div>
            </div>
          )}
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
