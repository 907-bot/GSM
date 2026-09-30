import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

interface Combination {
  concept_a: string
  concept_b: string
  confidence: number
  bridge_strength: number
  recommendation: string
  research_question?: string
  novelty_type: string
}

interface MissingLink {
  source: string
  target: string
  intermediate_types: string[]
  strength: number
}

const CONFIDENCE_COLOR = (c: number) => {
  if (c >= 0.8) return '#10b981'
  if (c >= 0.6) return '#f59e0b'
  return '#6366f1'
}

function CombinationCard({ combo }: { combo: Combination }) {
  const [expanded, setExpanded] = useState(false)
  const dragPayload = {
    type: 'missing-link',
    concepts: [combo.concept_a, combo.concept_b],
    label: `${combo.concept_a} + ${combo.concept_b}`,
    recommendation: combo.recommendation,
  }

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 16,
      padding: '20px 24px',
      transition: 'all 0.2s',
      cursor: 'pointer',
    }}
      draggable
      onDragStart={e => {
        e.dataTransfer.setData('application/x-gsm-missing-link', JSON.stringify(dragPayload))
        e.dataTransfer.setData('text/plain', dragPayload.label)
        e.dataTransfer.effectAllowed = 'copy'
      }}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Concept pair */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
        <div style={{
          padding: '6px 14px',
          background: 'rgba(99,102,241,0.2)',
          borderRadius: 20,
          border: '1px solid rgba(99,102,241,0.3)',
          color: '#a5b4fc',
          fontSize: 13,
          fontWeight: 600,
        }}>
          {combo.concept_a}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <div style={{ width: 40, height: 1, background: 'rgba(255,255,255,0.2)' }} />
          <span style={{ fontSize: 10, color: '#475569' }}>GAP</span>
          <div style={{ width: 40, height: 1, background: 'rgba(255,255,255,0.2)' }} />
        </div>

        <div style={{
          padding: '6px 14px',
          background: 'rgba(168,85,247,0.2)',
          borderRadius: 20,
          border: '1px solid rgba(168,85,247,0.3)',
          color: '#d8b4fe',
          fontSize: 13,
          fontWeight: 600,
        }}>
          {combo.concept_b}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <div style={{
            padding: '4px 10px',
            background: `${CONFIDENCE_COLOR(combo.confidence)}20`,
            borderRadius: 8,
            border: `1px solid ${CONFIDENCE_COLOR(combo.confidence)}40`,
            color: CONFIDENCE_COLOR(combo.confidence),
            fontSize: 12,
            fontWeight: 700,
          }}>
            {(combo.confidence * 100).toFixed(0)}% confidence
          </div>
          <span style={{ fontSize: 11, color: '#64748b' }}>
            {combo.bridge_strength} bridge connections
          </span>
        </div>
      </div>

      {/* Recommendation */}
      <p style={{ margin: '0 0 8px', fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
        {combo.recommendation}
      </p>

      {/* Research question (expanded) */}
      {expanded && combo.research_question && (
        <div style={{
          marginTop: 16,
          padding: '12px 16px',
          background: 'rgba(16,185,129,0.1)',
          borderRadius: 10,
          border: '1px solid rgba(16,185,129,0.2)',
        }}>
          <p style={{ margin: '0 0 6px', fontSize: 11, color: '#6ee7b7', fontWeight: 700 }}>💡 SUGGESTED RESEARCH QUESTION</p>
          <p style={{ margin: 0, fontSize: 13, color: '#e2e8f0', lineHeight: 1.6 }}>
            {combo.research_question}
          </p>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button
          onClick={e => { e.stopPropagation(); window.open(`/graph?concept=${encodeURIComponent(combo.concept_a)}`, '_self') }}
          style={{
            padding: '6px 14px',
            background: 'rgba(99,102,241,0.2)',
            border: '1px solid rgba(99,102,241,0.3)',
            borderRadius: 8,
            color: '#a5b4fc',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          🔍 Explore in Graph
        </button>
        <button
          onClick={e => { e.stopPropagation(); window.open(`/hypotheses?gap=${encodeURIComponent(`${combo.concept_a} + ${combo.concept_b}`)}`, '_self') }}
          style={{
            padding: '6px 14px',
            background: 'rgba(168,85,247,0.2)',
            border: '1px solid rgba(168,85,247,0.3)',
            borderRadius: 8,
            color: '#d8b4fe',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          🧠 Generate Hypothesis
        </button>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#475569', alignSelf: 'center' }}>
          drag to novelty score · {expanded ? '▲ less' : '▼ more'}
        </span>
      </div>
    </div>
  )
}

export function MissingLinksDashboard() {
  const [activeTab, setActiveTab] = useState<'combinations' | 'missing_links' | 'drug_repurposing' | 'three_hop'>('combinations')
  const [minConfidence, setMinConfidence] = useState(0.3)
  const [maxResults, setMaxResults] = useState(20)

  const combinationsQuery = useQuery({
    queryKey: ['novelty-combinations', minConfidence, maxResults],
    queryFn: () => api.noveltyCombinations(minConfidence, maxResults),
    refetchInterval: 60000,
  })

  const missingLinksQuery = useQuery({
    queryKey: ['missing-links'],
    queryFn: () => api.missingLinks(),
  })

  const drugQuery = useQuery({
    queryKey: ['drug-repurposing'],
    queryFn: () => api.drugRepurposing(),
    enabled: activeTab === 'drug_repurposing',
  })

  const threeHopQuery = useQuery({
    queryKey: ['three-hop'],
    queryFn: () => api.threeHopHypotheses(),
    enabled: activeTab === 'three_hop',
  })

  const TABS = [
    { key: 'combinations', label: '🎯 Unexplored Combinations', count: combinationsQuery.data?.total },
    { key: 'missing_links', label: '🔗 Missing Graph Links', count: missingLinksQuery.data?.total },
    { key: 'drug_repurposing', label: '💊 Drug Repurposing', count: drugQuery.data?.total },
    { key: 'three_hop', label: '🔀 3-Hop Hypotheses', count: threeHopQuery.data?.total },
  ]

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Missing Links Dashboard
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: 15 }}>
          Discover what nobody has tried yet — research gaps, unexplored combinations, and hidden connections in the knowledge graph.
        </p>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ color: '#94a3b8', fontSize: 13 }}>Min. Confidence:</label>
          <input
            type="range" min="0" max="0.9" step="0.1" value={minConfidence}
            onChange={e => setMinConfidence(parseFloat(e.target.value))}
            style={{ accentColor: '#6366f1', width: 120 }}
          />
          <span style={{ color: '#6366f1', fontSize: 13, fontWeight: 700, width: 32 }}>
            {(minConfidence * 100).toFixed(0)}%
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ color: '#94a3b8', fontSize: 13 }}>Results:</label>
          <select
            value={maxResults}
            onChange={e => setMaxResults(parseInt(e.target.value))}
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e2e8f0', padding: '4px 8px', fontSize: 13 }}
          >
            {[10, 20, 50].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <button
          onClick={() => { combinationsQuery.refetch(); missingLinksQuery.refetch() }}
          style={{ padding: '6px 16px', background: 'rgba(99,102,241,0.2)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, color: '#a5b4fc', fontSize: 13, cursor: 'pointer' }}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: 0 }}>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            style={{
              padding: '10px 18px',
              background: activeTab === tab.key ? 'rgba(99,102,241,0.2)' : 'none',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid #6366f1' : '2px solid transparent',
              color: activeTab === tab.key ? '#a5b4fc' : '#64748b',
              fontSize: 13,
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all 0.2s',
              fontWeight: activeTab === tab.key ? 600 : 400,
            }}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span style={{
                padding: '1px 7px',
                background: activeTab === tab.key ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.1)',
                borderRadius: 10,
                fontSize: 11,
              }}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'combinations' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {combinationsQuery.isLoading && <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>🔍 Scanning knowledge graph for unexplored combinations...</div>}
          {combinationsQuery.data?.combinations?.map((combo: Combination, i: number) => (
            <CombinationCard key={i} combo={combo} />
          ))}
          {!combinationsQuery.isLoading && !combinationsQuery.data?.combinations?.length && (
            <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
              <p style={{ fontSize: 40, margin: '0 0 16px' }}>🔬</p>
              <p style={{ fontSize: 16, margin: 0 }}>No combinations found. Index more papers to populate the knowledge graph.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'missing_links' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {missingLinksQuery.isLoading && <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>🔍 Finding missing graph links...</div>}
          {(missingLinksQuery.data?.missing_links || []).map((link: MissingLink, i: number) => (
            <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: '16px 20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: '#a5b4fc', fontWeight: 600 }}>{link.source}</span>
                <span style={{ color: '#475569' }}>——</span>
                <span style={{ color: '#94a3b8', fontSize: 12 }}>via [{link.intermediate_types?.join(', ')}]</span>
                <span style={{ color: '#475569' }}>——</span>
                <span style={{ color: '#d8b4fe', fontWeight: 600 }}>{link.target}</span>
                <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: 12 }}>strength: {link.strength}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'drug_repurposing' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {drugQuery.isLoading && <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>💊 Scanning drug-protein-disease chains...</div>}
          {(drugQuery.data?.candidates || []).map((c: any, i: number) => (
            <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: '16px 20px' }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 10 }}>
                <span style={{ padding: '4px 10px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 8, color: '#6ee7b7', fontSize: 12, fontWeight: 600 }}>💊 {c.drug}</span>
                <span style={{ color: '#475569' }}>→</span>
                <span style={{ padding: '4px 10px', background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 8, color: '#fcd34d', fontSize: 12, fontWeight: 600 }}>🧬 {c.protein}</span>
                <span style={{ color: '#475569' }}>→</span>
                <span style={{ padding: '4px 10px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#fca5a5', fontSize: 12, fontWeight: 600 }}>🦠 {c.disease}</span>
                <span style={{ marginLeft: 'auto', color: '#475569', fontSize: 11 }}>evidence: {c.evidence_strength}</span>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>{c.hypothesis}</p>
            </div>
          ))}
          {!drugQuery.isLoading && !drugQuery.data?.candidates?.length && (
            <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
              <p>No drug repurposing candidates found. Index biomedical papers to populate Drug/Protein/Disease nodes.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'three_hop' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {threeHopQuery.isLoading && <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>🔀 Finding 3-hop knowledge gaps...</div>}
          {(threeHopQuery.data?.hypotheses || []).map((h: any, i: number) => (
            <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: '16px 20px' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
                <span style={{ padding: '4px 10px', background: 'rgba(99,102,241,0.2)', borderRadius: 8, color: '#a5b4fc', fontSize: 12, fontWeight: 600 }}>{h.node_a}</span>
                <span style={{ color: '#475569' }}>→</span>
                <span style={{ padding: '4px 10px', background: 'rgba(255,255,255,0.1)', borderRadius: 8, color: '#94a3b8', fontSize: 12 }}>{h.bridge}</span>
                <span style={{ color: '#475569' }}>→</span>
                <span style={{ padding: '4px 10px', background: 'rgba(168,85,247,0.2)', borderRadius: 8, color: '#d8b4fe', fontSize: 12, fontWeight: 600 }}>{h.node_c}</span>
                <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: 11 }}>strength: {h.strength}</span>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>{h.hypothesis}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
