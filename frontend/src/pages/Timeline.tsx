import { useQuery } from '@tanstack/react-query'

interface PaperEvent {
  id: string
  title: string
  published_at: string
  source: string
  categories: string[]
  quality_score?: number
}

export function Timeline() {
  const { data, isLoading } = useQuery<{ papers: PaperEvent[] }>({
    queryKey: ['timeline-papers'],
    queryFn: async () => {
      const response = await fetch('/api/papers?page=1&page_size=100&sort_by=published_at&sort_order=desc')
      return response.json()
    },
  })

  const papers = data?.papers || []

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Discovery Timeline
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: 15 }}>
          Chronological view of scientific literature ingestion and discovery updates within the living scientific brain.
        </p>
      </div>

      {isLoading && <div style={{ color: '#94a3b8', textAlign: 'center', padding: 40 }}>Loading chronological timeline...</div>}

      {!isLoading && papers.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
          <p style={{ fontSize: 40, margin: '0 0 16px' }}>📅</p>
          <p style={{ fontSize: 16, margin: 0 }}>No indexed papers found. Once papers are indexed, they will appear chronologically here.</p>
        </div>
      )}

      <div style={{ position: 'relative', paddingLeft: 32, borderLeft: '2px solid rgba(255,255,255,0.08)' }}>
        {papers.map((paper) => (
          <div key={paper.id} style={{ position: 'relative', marginBottom: 40 }}>
            {/* Timeline Dot */}
            <div style={{
              position: 'absolute', left: -43, top: 4, width: 20, height: 20,
              borderRadius: '50%', background: '#0f172a', border: '3px solid #6366f1',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10
            }} />

            {/* Content Card */}
            <div style={{
              background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
              padding: 20, borderRadius: 14, transition: 'all 0.2s'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <span style={{ fontSize: 13, color: '#6366f1', fontWeight: 700 }}>
                  📅 {paper.published_at || 'Unknown Date'}
                </span>
                <span style={{
                  padding: '2px 8px', background: 'rgba(255,255,255,0.06)', borderRadius: 6,
                  fontSize: 11, color: '#94a3b8'
                }}>
                  {paper.source}
                </span>
              </div>

              <h3 style={{ margin: '0 0 12px', fontSize: 16, color: '#e2e8f0', fontWeight: 600 }}>
                {paper.title}
              </h3>

              {paper.categories && paper.categories.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {paper.categories.map(cat => (
                    <span key={cat} style={{
                      padding: '2px 8px', background: 'rgba(99,102,241,0.1)',
                      borderRadius: 10, color: '#a5b4fc', fontSize: 11
                    }}>
                      {cat}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
