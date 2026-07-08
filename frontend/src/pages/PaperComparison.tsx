import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

interface PaperInfo {
  id: string
  title: string
  source: string
}

interface ComparisonResult {
  paper_a: PaperInfo
  paper_b: PaperInfo
  shared_authors: string[]
  shared_concepts: string[]
  semantic_similarity: number
  similarity_verdict: string
  comparison_summary: string
}

export function PaperComparison() {
  const [paperIdA, setPaperIdA] = useState('')
  const [paperIdB, setPaperIdB] = useState('')
  const [triggerQuery, setTriggerQuery] = useState(false)

  const { data, isLoading, error, refetch } = useQuery<ComparisonResult>({
    queryKey: ['compare-papers', paperIdA, paperIdB],
    queryFn: async () => {
      const response = await fetch(`/api/papers/compare?paper_id_a=${encodeURIComponent(paperIdA)}&paper_id_b=${encodeURIComponent(paperIdB)}`)
      if (!response.ok) {
        throw new Error('Comparison failed. Make sure both paper IDs are correct.')
      }
      return response.json()
    },
    enabled: triggerQuery && !!paperIdA && !!paperIdB,
  })

  const handleCompare = (e: React.FormEvent) => {
    e.preventDefault()
    if (paperIdA && paperIdB) {
      setTriggerQuery(true)
      refetch()
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Paper Comparison View
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: 15 }}>
          Compare two papers side-by-side to discover shared authors, overlapping concepts, semantic similarities, or contradictions.
        </p>
      </div>

      <form onSubmit={handleCompare} style={{
        display: 'flex', gap: 16, marginBottom: 32, alignItems: 'flex-end',
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
        padding: 20, borderRadius: 12
      }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, color: '#94a3b8' }}>First Paper ID / UUID:</label>
          <input
            type="text"
            value={paperIdA}
            onChange={e => setPaperIdA(e.target.value)}
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            required
            style={{
              padding: '10px 14px', borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
              color: '#e2e8f0', fontSize: 14, outline: 'none'
            }}
          />
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, color: '#94a3b8' }}>Second Paper ID / UUID:</label>
          <input
            type="text"
            value={paperIdB}
            onChange={e => setPaperIdB(e.target.value)}
            placeholder="e.g. 770e8400-e29b-41d4-a716-446655440000"
            required
            style={{
              padding: '10px 14px', borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
              color: '#e2e8f0', fontSize: 14, outline: 'none'
            }}
          />
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 24px', background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            border: 'none', borderRadius: 8, color: '#ffffff', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', height: 42
          }}
        >
          Compare
        </button>
      </form>

      {isLoading && <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>Comparing papers using LLM semantic analyzer...</div>}

      {error && (
        <div style={{ padding: '16px 20px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, color: '#fca5a5', marginBottom: 24 }}>
          {(error as Error).message}
        </div>
      )}

      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          {/* Paper A & B Header Card */}
          <div style={{
            gridColumn: '1 / -1', display: 'flex', gap: 24,
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
            padding: 24, borderRadius: 16
          }}>
            <div style={{ flex: 1 }}>
              <span style={{ fontSize: 11, color: '#6366f1', fontWeight: 700 }}>PAPER A ({data.paper_a.source})</span>
              <h3 style={{ margin: '4px 0 0', fontSize: 16, color: '#f1f5f9' }}>{data.paper_a.title}</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 20px', borderLeft: '1px solid rgba(255,255,255,0.08)', borderRight: '1px solid rgba(255,255,255,0.08)' }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>Similarity</span>
              <span style={{ fontSize: 24, fontWeight: 800, color: '#10b981' }}>{(data.semantic_similarity * 100).toFixed(0)}%</span>
              <span style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{data.similarity_verdict}</span>
            </div>
            <div style={{ flex: 1 }}>
              <span style={{ fontSize: 11, color: '#a855f7', fontWeight: 700 }}>PAPER B ({data.paper_b.source})</span>
              <h3 style={{ margin: '4px 0 0', fontSize: 16, color: '#f1f5f9' }}>{data.paper_b.title}</h3>
            </div>
          </div>

          {/* AI Comparison Summary */}
          <div style={{
            gridColumn: '1 / -1', background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.15)',
            padding: 24, borderRadius: 16
          }}>
            <h4 style={{ margin: '0 0 10px', fontSize: 13, color: '#a5b4fc', fontWeight: 700, letterSpacing: '0.05em' }}>🧠 AI COMPARISON SUMMARY</h4>
            <p style={{ margin: 0, fontSize: 14, color: '#e2e8f0', lineHeight: 1.6 }}>{data.comparison_summary || 'No comparison text generated.'}</p>
          </div>

          {/* Overlapping concepts & Shared authors */}
          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
            padding: 24, borderRadius: 16
          }}>
            <h4 style={{ margin: '0 0 16px', fontSize: 14, color: '#f1f5f9' }}>🧬 Shared Concepts & Categories</h4>
            {data.shared_concepts.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {data.shared_concepts.map(concept => (
                  <span key={concept} style={{
                    padding: '4px 10px', background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.25)',
                    borderRadius: 12, color: '#a5b4fc', fontSize: 12
                  }}>
                    {concept}
                  </span>
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>No shared category tags found.</p>
            )}
          </div>

          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
            padding: 24, borderRadius: 16
          }}>
            <h4 style={{ margin: '0 0 16px', fontSize: 14, color: '#f1f5f9' }}>👥 Shared Authors</h4>
            {data.shared_authors.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {data.shared_authors.map(author => (
                  <span key={author} style={{
                    padding: '4px 10px', background: 'rgba(168,85,247,0.15)', border: '1px solid rgba(168,85,247,0.25)',
                    borderRadius: 12, color: '#d8b4fe', fontSize: 12
                  }}>
                    {author}
                  </span>
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>No common authors between these papers.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
