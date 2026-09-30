import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Search,
  Sparkles,
  AlertTriangle,
  GitCompare,
  Lightbulb,
  BookOpen,
  ArrowRight,
  ExternalLink,
  Flame,
  Layers,
  Activity,
  CheckCircle2,
} from 'lucide-react'
import { api } from '../api'

const CURATED_DOMAINS = [
  { label: '⚛️ Quantum Error Correction', query: 'Quantum Error Correction in Surface Codes' },
  { label: '🤖 LLM Hallucinations & Reasoning', query: 'Large Language Model Hallucination and Faithfulness' },
  { label: '🧬 CRISPR Base Editing Specificity', query: 'CRISPR Cas9 Off-Target Mitigation and Base Editing' },
  { label: '⚡ Solid-State Battery Interfaces', query: 'Solid-State Lithium Battery Electrolyte Interfacial Stability' },
  { label: '🧠 Brain-Computer Interfaces', query: 'Brain-Computer Interfaces for Real-Time Speech Decoding' },
  { label: '🧪 Room-Temp Superconductors', query: 'Hydride Superconductivity and High-Pressure Transport' },
  { label: '🩺 Alzheimer Tau Biomarkers', query: 'Plasma Phosphorylated Tau Biomarkers for Early Alzheimer Diagnosis' },
]

export function GapFinder() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''

  const [query, setQuery] = useState(initialQuery || 'Quantum Machine Learning')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'all' | 'bottlenecks' | 'contradictions' | 'missing' | 'hypotheses'>('all')

  const handleSearch = async (targetQuery?: string) => {
    const q = (targetQuery !== undefined ? targetQuery : query).trim()
    if (!q) return

    setLoading(true)
    setError(null)

    try {
      const data = await api.analyzeGaps(q, 15)
      setResults(data)
    } catch (err: any) {
      console.error('Gap analysis failed', err)
      setError(err.message || 'Failed to analyze subject gaps. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    handleSearch(query)
  }, [])

  const handlePublishFromGap = (gapTitle: string, hypothesisText?: string, venue = 'NeurIPS') => {
    navigate('/publish', {
      state: {
        topic: results?.subject || query,
        gap: gapTitle,
        hypothesis: hypothesisText || '',
        evidence: results?.papers || [],
        venue: venue,
      },
    })
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Hero Header */}
      <div className="relative rounded-3xl p-8 bg-gradient-to-r from-blue-900/30 via-indigo-900/20 to-purple-900/30 border border-white/10 backdrop-blur-xl shadow-2xl overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold tracking-wide uppercase">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Autonomous Scientific Discovery</span>
          </div>

          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            Subject <span className="gradient-text">Gap Finder</span>
          </h1>

          <p className="text-slate-300 text-base max-w-3xl leading-relaxed">
            Enter any scientific subject or discipline that you love. GSM-OS retrieves open literature from
            arXiv, OpenAlex, and PubMed, analyzes mathematical and empirical invariants, and pinpoints
            exact <strong className="text-white">bottlenecks</strong>, <strong className="text-white">contradictions</strong>, and <strong className="text-white">unexplored hypotheses</strong> ready to be authored into a publication-grade paper.
          </p>

          {/* Search Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSearch()
            }}
            className="pt-2 flex flex-col sm:flex-row gap-3 max-w-4xl"
          >
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter any subject (e.g. Quantum Error Correction, Neuroplasticity, Generative AI Alignment)..."
                className="w-full bg-slate-900/70 border border-white/20 rounded-xl py-3.5 pl-12 pr-4 text-white placeholder-slate-400 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 transition-all shadow-inner"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="px-7 py-3.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-semibold text-sm shadow-lg shadow-indigo-500/25 active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-2 shrink-0"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" />
                  <span>Discovering Gaps...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Find Gaps</span>
                </>
              )}
            </button>
          </form>

          {/* Curated Domain Chips */}
          <div className="pt-2 space-y-1.5">
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">
              Trending Research Frontiers:
            </span>
            <div className="flex flex-wrap gap-2">
              {CURATED_DOMAINS.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => {
                    setQuery(item.query)
                    handleSearch(item.query)
                  }}
                  className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-indigo-400/40 text-slate-300 hover:text-white text-xs transition-all duration-200"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="py-16 text-center space-y-4">
          <div className="inline-flex p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 animate-pulse">
            <Activity className="w-8 h-8 animate-spin" />
          </div>
          <h3 className="text-xl font-bold text-white">Synthesizing Literature & Identifying Gaps...</h3>
          <p className="text-slate-400 text-sm max-w-md mx-auto">
            Fetching scholarly preprints, extracting mathematical invariants, and formulating publication angles for <span className="text-indigo-300">"{query}"</span>.
          </p>
        </div>
      )}

      {/* Results View */}
      {!loading && results && (
        <div className="space-y-8">
          {/* Metadata Banner */}
          <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
            <div>
              <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Analysis Scope</span>
              <h2 className="text-2xl font-bold text-white capitalize">{results.subject}</h2>
              <div className="flex flex-wrap gap-2 mt-2">
                {results.key_concepts?.map((c: string) => (
                  <span key={c} className="px-2.5 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/30 text-blue-300 text-xs font-medium">
                    #{c}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-6">
              <div className="text-right">
                <span className="text-xs text-slate-400">Papers Ingested</span>
                <p className="text-2xl font-black text-indigo-400">{results.papers_analyzed_count}</p>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400">Bottlenecks</span>
                <p className="text-2xl font-black text-amber-400">{results.bottlenecks?.length || 0}</p>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400">Hypotheses</span>
                <p className="text-2xl font-black text-emerald-400">{results.hypotheses?.length || 0}</p>
              </div>
            </div>
          </div>

          {/* Paper Publishing Proposal Banners */}
          {results.paper_angles && results.paper_angles.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Flame className="w-5 h-5 text-amber-400" />
                  <h3 className="text-lg font-bold text-white">Recommended Paper Angles (Ready to Publish)</h3>
                </div>
                <span className="text-xs text-slate-400">Click any angle to generate complete paper</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {results.paper_angles.map((pa: any, i: number) => (
                  <div
                    key={i}
                    className="p-5 rounded-2xl bg-gradient-to-b from-indigo-950/40 to-slate-900/60 border border-indigo-500/30 hover:border-indigo-400/60 transition-all duration-300 flex flex-col justify-between group shadow-lg hover:shadow-indigo-500/10"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[11px] font-semibold">
                          {pa.paper_type}
                        </span>
                        <span className="text-[11px] text-indigo-300 font-medium">
                          {pa.target_venue}
                        </span>
                      </div>

                      <h4 className="text-base font-bold text-white group-hover:text-indigo-300 transition-colors leading-snug">
                        {pa.title}
                      </h4>

                      <p className="text-xs text-slate-300 leading-relaxed">
                        {pa.contribution_summary}
                      </p>
                    </div>

                    <div className="pt-5 mt-4 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handlePublishFromGap(pa.title, pa.hypothesis, pa.target_venue)}
                        className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md group-hover:brightness-110 active:scale-[0.98] transition-all"
                      >
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>Publish This Paper</span>
                        <ArrowRight className="w-3.5 h-3.5 ml-auto" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section Filter Tabs */}
          <div className="flex bg-slate-900/60 p-1.5 rounded-xl border border-white/10 w-fit">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'all' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              All Gaps Matrix
            </button>
            <button
              onClick={() => setActiveTab('bottlenecks')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'bottlenecks' ? 'bg-amber-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Bottlenecks ({results.bottlenecks?.length || 0})
            </button>
            <button
              onClick={() => setActiveTab('contradictions')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'contradictions' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Controversies ({results.contradictions?.length || 0})
            </button>
            <button
              onClick={() => setActiveTab('missing')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'missing' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Missing Links ({results.missing_links?.length || 0})
            </button>
            <button
              onClick={() => setActiveTab('hypotheses')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'hypotheses' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Hypotheses ({results.hypotheses?.length || 0})
            </button>
          </div>

          {/* 1. Bottlenecks Section */}
          {(activeTab === 'all' || activeTab === 'bottlenecks') && results.bottlenecks && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h3 className="text-xl font-bold text-white">Scientific Bottlenecks & Roadblocks</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {results.bottlenecks.map((b: any) => (
                  <div
                    key={b.id}
                    className="p-6 rounded-2xl bg-white/5 border border-amber-500/20 hover:border-amber-400/50 backdrop-blur-sm transition-all duration-200 flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[11px] font-bold uppercase">
                          {b.severity} Severity
                        </span>
                        <span className="text-xs font-bold text-slate-400">
                          {Math.round(b.confidence * 100)}% confidence
                        </span>
                      </div>

                      <h4 className="text-base font-bold text-white">{b.title}</h4>
                      <p className="text-xs text-slate-300 leading-relaxed">{b.description}</p>

                      <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/15">
                        <span className="text-[11px] font-semibold text-amber-300 block mb-1">
                          💡 Breakthrough Formulation:
                        </span>
                        <p className="text-xs text-slate-300">{b.suggested_solution}</p>
                      </div>

                      {b.evidence_papers && b.evidence_papers.length > 0 && (
                        <div className="text-[11px] text-slate-400">
                          <span className="font-semibold text-slate-300">Evidence Base: </span>
                          {b.evidence_papers.join('; ')}
                        </div>
                      )}
                    </div>

                    <div className="pt-4 mt-4 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handlePublishFromGap(b.title, b.suggested_solution)}
                        className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-600 to-indigo-600 hover:from-amber-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md active:scale-[0.98] transition-all"
                      >
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>Publish Paper on this Bottleneck</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2. Contradictions Section */}
          {(activeTab === 'all' || activeTab === 'contradictions') && results.contradictions && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <GitCompare className="w-5 h-5 text-rose-400" />
                <h3 className="text-xl font-bold text-white">Literature Contradictions & Method Debates</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {results.contradictions.map((c: any) => (
                  <div
                    key={c.id}
                    className="p-6 rounded-2xl bg-white/5 border border-rose-500/20 hover:border-rose-400/40 backdrop-blur-sm transition-all duration-200 flex flex-col justify-between"
                  >
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[11px] font-bold">
                          {c.type}
                        </span>
                        <span className="text-xs text-slate-400 font-semibold">{Math.round(c.confidence * 100)}% detection</span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="p-3.5 rounded-xl bg-blue-500/5 border border-blue-500/20">
                          <span className="text-[10px] font-bold text-blue-400 block uppercase mb-1">Perspective A</span>
                          <p className="text-xs text-slate-200">{c.claim_a}</p>
                          <span className="text-[10px] text-slate-400 block mt-2">Source: {c.source_a}</span>
                        </div>

                        <div className="p-3.5 rounded-xl bg-rose-500/5 border border-rose-500/20">
                          <span className="text-[10px] font-bold text-rose-400 block uppercase mb-1">Perspective B</span>
                          <p className="text-xs text-slate-200">{c.claim_b}</p>
                          <span className="text-[10px] text-slate-400 block mt-2">Source: {c.source_b}</span>
                        </div>
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed">
                        <strong className="text-white">Core Friction:</strong> {c.conflict_summary}
                      </p>

                      <div className="p-3.5 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
                        <span className="text-[11px] font-semibold text-emerald-400 block mb-1">
                          🎯 Proposed Resolution Paradigm:
                        </span>
                        <p className="text-xs text-slate-300">{c.resolution_hypothesis}</p>
                      </div>
                    </div>

                    <div className="pt-4 mt-4 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handlePublishFromGap(`Resolving ${c.type} in ${results.subject}`, c.resolution_hypothesis)}
                        className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-rose-600 to-indigo-600 hover:from-rose-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md active:scale-[0.98] transition-all"
                      >
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>Publish Paper Resolving this Conflict</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 3. Missing Links & Unexplored Bridges */}
          {(activeTab === 'all' || activeTab === 'missing') && results.missing_links && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-cyan-400" />
                <h3 className="text-xl font-bold text-white">Unexplored Concept Bridges & Missing Links</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {results.missing_links.map((m: any) => (
                  <div
                    key={m.id}
                    className="p-6 rounded-2xl bg-white/5 border border-cyan-500/20 hover:border-cyan-400/40 backdrop-blur-sm transition-all duration-200 flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="px-2.5 py-1 rounded-lg bg-blue-500/20 text-blue-300 text-xs font-bold">
                            {m.concept_a}
                          </span>
                          <span className="text-slate-400 font-bold">⟷</span>
                          <span className="px-2.5 py-1 rounded-lg bg-purple-500/20 text-purple-300 text-xs font-bold">
                            {m.concept_b}
                          </span>
                        </div>
                        <span className="text-xs font-bold text-cyan-300">
                          {Math.round(m.novelty_score * 100)}% Novelty
                        </span>
                      </div>

                      <h4 className="text-base font-bold text-white">{m.suggested_title}</h4>
                      <p className="text-xs text-slate-300 leading-relaxed">{m.bridge_rationale}</p>
                      <p className="text-[11px] text-cyan-400 font-semibold">{m.potential_impact}</p>
                    </div>

                    <div className="pt-4 mt-4 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handlePublishFromGap(m.suggested_title, m.bridge_rationale)}
                        className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md active:scale-[0.98] transition-all"
                      >
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>Publish Cross-Domain Paper</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. Actionable Hypotheses */}
          {(activeTab === 'all' || activeTab === 'hypotheses') && results.hypotheses && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-emerald-400" />
                <h3 className="text-xl font-bold text-white">Generated Testable Hypotheses</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {results.hypotheses.map((h: any) => (
                  <div
                    key={h.id}
                    className="p-6 rounded-2xl bg-white/5 border border-emerald-500/20 hover:border-emerald-400/40 backdrop-blur-sm transition-all duration-200 flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[11px] font-bold">
                          Empirically Testable
                        </span>
                        <span className="text-xs text-emerald-400 font-bold">{Math.round(h.confidence * 100)}% Confidence</span>
                      </div>

                      <p className="text-sm text-slate-100 font-medium leading-relaxed">{h.hypothesis_text}</p>

                      <div className="space-y-1.5 pt-2">
                        <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                          Experimental Validation Protocol:
                        </span>
                        {h.suggested_experiments?.map((exp: string, idx: number) => (
                          <div key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                            <span>{exp}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="pt-4 mt-4 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handlePublishFromGap(`Empirical Validation of Invariant Manifolds in ${results.subject}`, h.hypothesis_text)}
                        className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md active:scale-[0.98] transition-all"
                      >
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>Publish Paper Validating this Hypothesis</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Ingested Literature Drawer */}
          {results.papers && results.papers.length > 0 && (
            <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider">
                    Literature Analyzed for {results.subject} ({results.papers.length} Papers Ingested)
                  </h4>
                </div>
                <span className="text-xs text-slate-400">Indexed in local SQLite memory</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {results.papers.map((p: any) => (
                  <div key={p.id} className="p-3.5 rounded-xl bg-slate-900/50 border border-white/5 space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <h5 className="text-xs font-bold text-slate-200 line-clamp-1">{p.title}</h5>
                      {p.url && (
                        <a
                          href={p.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-slate-400 hover:text-indigo-300 shrink-0"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2">{p.abstract_preview}</p>
                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                      <span>{p.authors?.join(', ') || 'Unknown Authors'}</span>
                      <span className="uppercase text-indigo-400">{p.source || 'arxiv'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
