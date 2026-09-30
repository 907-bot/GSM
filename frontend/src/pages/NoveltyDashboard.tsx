import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

interface NoveltyScoreResult {
  concepts: string[]
  novelty_score: number
  combo_paper_count: number
  individual_counts: Record<string, number>
  explanation: string
  verdict: string
}

export function NoveltyDashboard() {
  const [conceptsStr, setConceptsStr] = useState('')
  const [trigger, setTrigger] = useState(false)

  const concepts = conceptsStr.split(',').map(c => c.trim()).filter(c => c.length > 0)

  const { data, isLoading, error, refetch } = useQuery<NoveltyScoreResult>({
    queryKey: ['novelty-score', concepts],
    queryFn: () => api.scoreNovelty(concepts),
    enabled: trigger && concepts.length > 0,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (concepts.length > 0) {
      setTrigger(true)
      refetch()
    }
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const raw = e.dataTransfer.getData('application/x-gsm-missing-link')
    const text = e.dataTransfer.getData('text/plain')
    try {
      const payload = raw ? JSON.parse(raw) : null
      const droppedConcepts = payload?.concepts?.length ? payload.concepts : text.split('+')
      const next = droppedConcepts.map((c: string) => c.trim()).filter(Boolean)
      if (next.length > 0) {
        setConceptsStr(next.join(', '))
        setTrigger(true)
        setTimeout(() => refetch(), 0)
      }
    } catch {
      if (text.trim()) setConceptsStr(text.split('+').map(c => c.trim()).join(', '))
    }
  }

  return (
    <div
      onDragOver={e => e.preventDefault()}
      onDrop={handleDrop}
      style={{ padding: '24px 32px', maxWidth: 1000, margin: '0 auto' }}
    >
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Novelty Score Dashboard
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: 15 }}>
          Test any custom concept combination to calculate its novelty against the knowledge graph.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
        padding: 24, borderRadius: 16, display: 'flex', flexDirection: 'column', gap: 16,
        marginBottom: 32
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, color: '#94a3b8' }}>Concepts (comma separated):</label>
          <input
            type="text"
            value={conceptsStr}
            onChange={e => setConceptsStr(e.target.value)}
            placeholder="e.g. CRISPR, Parkinson's disease, nanoparticles"
            required
            style={{
              padding: '12px 16px', borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
              color: '#e2e8f0', fontSize: 14, outline: 'none'
            }}
          />
          <span style={{ fontSize: 11, color: '#64748b' }}>Provide 2 to 5 scientific keywords or node names.</span>
          <span style={{ fontSize: 11, color: '#64748b' }}>You can also drag a missing link card here from the Missing Links dashboard.</span>
        </div>

        <button
          type="submit"
          style={{
            padding: '12px 24px', background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            border: 'none', borderRadius: 8, color: '#ffffff', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', alignSelf: 'flex-start'
          }}
        >
          Check Novelty
        </button>
      </form>

      {isLoading && <div style={{ color: '#94a3b8', textAlign: 'center', padding: 40 }}>Calculating overlap densities...</div>}

      {error && (
        <div style={{ padding: '16px 20px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, color: '#fca5a5', marginBottom: 24 }}>
          {(error as Error).message}
        </div>
      )}

      {data && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div style={{
            display: 'flex', gap: 32, alignItems: 'center',
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
            padding: 32, borderRadius: 20
          }}>
            <div style={{
              width: 120, height: 120, borderRadius: '50%',
              background: 'rgba(99,102,241,0.1)', border: '4px solid #6366f1',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0
            }}>
              <span style={{ fontSize: 28, fontWeight: 800, color: '#6366f1' }}>
                {(data.novelty_score * 100).toFixed(0)}%
              </span>
              <span style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>Novelty</span>
            </div>

            <div>
              <span style={{
                padding: '4px 10px', background: 'rgba(99,102,241,0.2)',
                borderRadius: 8, color: '#a5b4fc', fontSize: 12, fontWeight: 700
              }}>
                {data.verdict}
              </span>
              <p style={{ margin: '12px 0 0', fontSize: 15, color: '#e2e8f0', lineHeight: 1.6 }}>
                {data.explanation}
              </p>
            </div>
          </div>

          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
            padding: 24, borderRadius: 16
          }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, color: '#f1f5f9' }}>Individual Concept Frequencies</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {Object.entries(data.individual_counts).map(([concept, count]) => (
                <div key={concept} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#94a3b8' }}>
                  <span>{concept}</span>
                  <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{count} papers</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
