import React, { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GripVertical, Plus, X } from 'lucide-react'
import { api } from '../api'

interface PaperInfo {
  id: string
  title: string
  source: string
  authors?: string[]
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

function normalizePaper(paper: any): PaperInfo {
  const payload = paper.payload || paper
  return {
    id: paper.id || payload.id || payload.source_id,
    title: payload.title || 'Untitled paper',
    source: payload.source || 'Memory',
    authors: payload.authors || [],
  }
}

export function PaperComparison() {
  const [selected, setSelected] = useState<PaperInfo[]>([])
  const [query, setQuery] = useState('')

  const papersQuery = useQuery({
    queryKey: ['comparison-papers'],
    queryFn: async () => {
      const { data } = await api.listPapers(1, 100)
      return (data || []).map(normalizePaper).filter((paper: PaperInfo) => paper.id)
    },
  })

  const pairKeys = useMemo(() => {
    const pairs: Array<[PaperInfo, PaperInfo]> = []
    for (let i = 0; i < selected.length; i += 1) {
      for (let j = i + 1; j < selected.length; j += 1) {
        pairs.push([selected[i], selected[j]])
      }
    }
    return pairs
  }, [selected])

  const comparisonQuery = useQuery<ComparisonResult[]>({
    queryKey: ['compare-paper-set', selected.map(p => p.id).join('|')],
    queryFn: async () => Promise.all(pairKeys.map(([a, b]) => api.comparePapers(a.id, b.id))),
    enabled: selected.length >= 2,
  })

  const filteredPapers = useMemo(() => {
    const q = query.trim().toLowerCase()
    const available = (papersQuery.data || []).filter((paper: PaperInfo) => !selected.some(p => p.id === paper.id))
    if (!q) return available.slice(0, 20)
    return available.filter((paper: PaperInfo) => {
      return paper.title.toLowerCase().includes(q)
        || paper.source.toLowerCase().includes(q)
        || (paper.authors || []).join(' ').toLowerCase().includes(q)
    }).slice(0, 20)
  }, [papersQuery.data, query, selected])

  const addPaper = (paper: PaperInfo) => {
    setSelected(prev => prev.some(p => p.id === paper.id) ? prev : [...prev, paper].slice(0, 6))
  }

  const removePaper = (id: string) => {
    setSelected(prev => prev.filter(p => p.id !== id))
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const raw = e.dataTransfer.getData('application/x-gsm-paper')
    if (!raw) return
    try {
      addPaper(JSON.parse(raw))
    } catch {
      // ignore malformed drag data
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Paper Comparison View
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: 15 }}>
          Select papers by name or drag them into the comparison tray to compare two or more studies.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 380px) 1fr', gap: 24 }}>
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)', padding: 20, borderRadius: 12 }}>
          <label style={{ fontSize: 13, color: '#94a3b8' }}>Find papers by title, author, or source</label>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search stored papers"
            style={{ width: '100%', marginTop: 8, marginBottom: 16, padding: '10px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', fontSize: 14, outline: 'none' }}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 520, overflowY: 'auto' }}>
            {papersQuery.isLoading && <p style={{ color: '#64748b', fontSize: 13 }}>Loading papers...</p>}
            {filteredPapers.map((paper: PaperInfo) => (
              <div
                key={paper.id}
                draggable
                onDragStart={e => {
                  e.dataTransfer.setData('application/x-gsm-paper', JSON.stringify(paper))
                  e.dataTransfer.setData('text/plain', paper.title)
                  e.dataTransfer.effectAllowed = 'copy'
                }}
                style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, padding: 12, background: 'rgba(255,255,255,0.03)', cursor: 'grab' }}
              >
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <GripVertical size={16} color="#64748b" style={{ flexShrink: 0, marginTop: 2 }} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ color: '#f1f5f9', fontSize: 13, fontWeight: 700, lineHeight: 1.35 }}>{paper.title}</div>
                    <div style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>{paper.source}{paper.authors?.length ? ` · ${paper.authors.slice(0, 2).join(', ')}` : ''}</div>
                  </div>
                  <button type="button" onClick={() => addPaper(paper)} style={{ border: '1px solid rgba(99,102,241,0.35)', background: 'rgba(99,102,241,0.16)', color: '#a5b4fc', borderRadius: 8, padding: 6, cursor: 'pointer' }}>
                    <Plus size={14} />
                  </button>
                </div>
              </div>
            ))}
            {!papersQuery.isLoading && filteredPapers.length === 0 && (
              <p style={{ color: '#64748b', fontSize: 13 }}>No matching stored papers. Fetch papers from Discovery Feed first.</p>
            )}
          </div>
        </div>

        <div>
          <div
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop}
            style={{ minHeight: 130, marginBottom: 24, border: '1px dashed rgba(99,102,241,0.45)', borderRadius: 12, padding: 16, background: 'rgba(99,102,241,0.05)' }}
          >
            <div style={{ fontSize: 13, color: '#a5b4fc', fontWeight: 700, marginBottom: 12 }}>Comparison tray</div>
            {selected.length === 0 ? (
              <p style={{ margin: 0, color: '#64748b', fontSize: 14 }}>Drop papers here or add them from the list.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {selected.map((paper, index) => (
                  <div key={paper.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <span style={{ color: '#94a3b8', fontSize: 12, width: 22 }}>{index + 1}</span>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ color: '#f8fafc', fontSize: 14, fontWeight: 700 }}>{paper.title}</div>
                      <div style={{ color: '#64748b', fontSize: 11 }}>{paper.source}{paper.authors?.length ? ` · ${paper.authors.slice(0, 3).join(', ')}` : ''}</div>
                    </div>
                    <button type="button" onClick={() => removePaper(paper.id)} style={{ border: 'none', background: 'rgba(239,68,68,0.15)', color: '#fca5a5', borderRadius: 8, padding: 6, cursor: 'pointer' }}>
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {comparisonQuery.isLoading && <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>Comparing selected papers...</div>}
          {comparisonQuery.error && (
            <div style={{ padding: '16px 20px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, color: '#fca5a5', marginBottom: 24 }}>
              {(comparisonQuery.error as Error).message}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {(comparisonQuery.data || []).map((data, i) => (
              <div key={`${data.paper_a.id}-${data.paper_b.id}-${i}`} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', padding: 20, borderRadius: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, alignItems: 'center', marginBottom: 16 }}>
                  <h3 style={{ margin: 0, fontSize: 15, color: '#f1f5f9' }}>{data.paper_a.title}</h3>
                  <div style={{ textAlign: 'center', minWidth: 90 }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: '#10b981' }}>{(data.semantic_similarity * 100).toFixed(0)}%</div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>{data.similarity_verdict}</div>
                  </div>
                  <h3 style={{ margin: 0, fontSize: 15, color: '#f1f5f9' }}>{data.paper_b.title}</h3>
                </div>
                <p style={{ margin: '0 0 14px', fontSize: 14, color: '#e2e8f0', lineHeight: 1.6 }}>{data.comparison_summary || 'No comparison text generated.'}</p>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', color: '#94a3b8', fontSize: 12 }}>
                  <span>Shared concepts: {data.shared_concepts.length ? data.shared_concepts.join(', ') : 'none found'}</span>
                  <span>Shared authors: {data.shared_authors.length ? data.shared_authors.join(', ') : 'none found'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
