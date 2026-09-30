import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Sparkles,
  Download,
  Copy,
  Check,
  Printer,
  FileCode,
  FileText,
  Award,
  RefreshCw,
  Edit3,
  ChevronRight,
  ShieldCheck,
  Sliders,
  CheckCircle2,
} from 'lucide-react'
import { api } from '../api'

const VENUES = [
  { id: 'NeurIPS', label: 'NeurIPS (Neural Information Processing Systems)', tier: 'A*' },
  { id: 'ICML', label: 'ICML (International Conf. on Machine Learning)', tier: 'A*' },
  { id: 'Nature', label: 'Nature / Nature Machine Intelligence', tier: 'Top Journal' },
  { id: 'Science', label: 'Science / Science Robotics', tier: 'Top Journal' },
  { id: 'IEEE Transactions', label: 'IEEE Transactions (TPAMI)', tier: 'Top Journal' },
  { id: 'ACM', label: 'ACM Computing Surveys / SIGKDD', tier: 'A*' },
  { id: 'arXiv', label: 'arXiv Scientific Preprint', tier: 'Preprint' },
]

const PAPER_TYPES = [
  'Original Research Article',
  'Methodological Framework & Benchmark',
  'Position Paper & Research Agenda',
  'Systematic Review & Meta-Analysis',
]

const SECTION_TITLES: Record<string, string> = {
  abstract: 'Abstract',
  introduction: '1. Introduction',
  related_work: '2. Related Work',
  problem_formulation: '3. Problem Formulation & Research Gap',
  methodology: '4. Proposed Methodology',
  theoretical_analysis: '5. Theoretical Analysis',
  experimental_design: '6. Experimental Design',
  results_and_discussion: '7. Results and Discussion',
  limitations_and_future_work: '8. Limitations and Future Work',
  conclusion: '9. Conclusion',
}

export function PaperPublisher() {
  const location = useLocation()
  const navigate = useNavigate()
  const stateData = (location.state as any) || {}

  // Configuration Form State
  const [topic, setTopic] = useState(stateData.topic || 'Quantum Machine Learning')
  const [gap, setGap] = useState(stateData.gap || 'Scalability and Coherence Limits in High-Dimensional States')
  const [venue, setVenue] = useState(stateData.venue || 'NeurIPS')
  const [paperType, setPaperType] = useState('Original Research Article')
  const [authorName, setAuthorName] = useState('Dr. Alex Mercer')
  const [authorAffiliation, setAuthorAffiliation] = useState('Global Scientific Memory Institute')
  const [authorEmail, setAuthorEmail] = useState('researcher@gsm-os.org')
  const [customNotes, setCustomNotes] = useState('')

  // Paper State
  const [paper, setPaper] = useState<any | null>(null)
  const [generating, setGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState<'article' | 'latex' | 'bibtex' | 'markdown' | 'review'>('article')

  // Edit/Regenerate State
  const [editingSection, setEditingSection] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(null)
  const [regeneratePrompt, setRegeneratePrompt] = useState('')

  // Review State
  const [review, setReview] = useState<any | null>(null)
  const [reviewing, setReviewing] = useState(false)

  // Copy Feedback
  const [copied, setCopied] = useState<string | null>(null)

  const handleGeneratePaper = async () => {
    setGenerating(true)
    setReview(null)

    try {
      const generated = await api.generatePublishedPaper({
        topic,
        gap,
        venue,
        paper_type: paperType,
        authors: [{ name: authorName, affiliation: authorAffiliation, email: authorEmail }],
        custom_notes: customNotes,
      })
      setPaper(generated)
    } catch (err: any) {
      console.error('Failed to generate paper', err)
      alert(err.message || 'Paper generation failed.')
    } finally {
      setGenerating(false)
    }
  }

  // Auto-generate on initial entry if topic and gap were supplied from Gap Finder
  useEffect(() => {
    if (stateData.topic && stateData.gap && !paper) {
      handleGeneratePaper()
    }
  }, [])

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleSaveEdit = (sectionKey: string) => {
    if (!paper) return
    setPaper({
      ...paper,
      sections: {
        ...paper.sections,
        [sectionKey]: editText,
      },
    })
    setEditingSection(null)
  }

  const handleRegenerateSectionSubmit = async (sectionKey: string) => {
    if (!paper) return
    setRegeneratingSection(sectionKey)

    try {
      const res = await api.regeneratePaperSection({
        section_name: sectionKey,
        topic: paper.topic,
        current_content: paper.sections[sectionKey] || '',
        prompt: regeneratePrompt || 'Increase theoretical depth and enhance formal academic phrasing.',
      })
      setPaper({
        ...paper,
        sections: {
          ...paper.sections,
          [sectionKey]: res.content,
        },
      })
      setRegeneratePrompt('')
    } catch (err: any) {
      alert(err.message || 'Failed to regenerate section.')
    } finally {
      setRegeneratingSection(null)
    }
  }

  const handleSimulateReview = async () => {
    if (!paper) return
    setReviewing(true)

    try {
      const res = await api.simulatePaperReview({
        title: paper.title,
        abstract: paper.sections.abstract || '',
        sections: paper.sections,
        venue: paper.venue,
      })
      setReview(res)
      setActiveTab('review')
    } catch (err: any) {
      alert(err.message || 'Review simulation failed.')
    } finally {
      setReviewing(false)
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in print:p-0 print:m-0 print:max-w-none">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 print:hidden">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 border border-blue-500/30 text-blue-300 text-xs font-semibold uppercase tracking-wider mb-2">
            <Award className="w-3.5 h-3.5" />
            <span>Autonomous Publication Studio</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white">
            Research Paper <span className="gradient-text">Publisher</span>
          </h1>
          <p className="text-slate-300 text-sm mt-1">
            Transform any scientific gap or hypothesis into a submission-ready, publication-grade academic manuscript with full LaTeX, BibTeX, and peer review simulation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/gaps')}
            className="px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-xs font-semibold transition-all flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Gap Finder</span>
          </button>

          {paper && (
            <button
              type="button"
              onClick={handleSimulateReview}
              disabled={reviewing}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold shadow-lg shadow-emerald-500/20 active:scale-[0.98] transition-all flex items-center gap-2"
            >
              {reviewing ? (
                <span className="w-3.5 h-3.5 rounded-full border-2 border-white/20 border-t-white animate-spin" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
              <span>Simulate Peer Review</span>
            </button>
          )}
        </div>
      </div>

      {/* Configuration Accordion / Drawer */}
      <div className="p-6 rounded-3xl bg-gradient-to-b from-slate-900/90 to-slate-900/60 border border-white/10 backdrop-blur-xl shadow-xl space-y-6 print:hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold text-white uppercase tracking-wider">Paper Specification</h3>
          </div>
          <span className="text-xs text-slate-400">Target Venue & Rigor Controls</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Topic */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Research Subject / Topic</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Quantum Machine Learning"
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Research Gap */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Core Research Gap / Problem</label>
            <input
              type="text"
              value={gap}
              onChange={(e) => setGap(e.target.value)}
              placeholder="e.g. Scalability and decoherence limits in multi-qubit states"
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Target Venue */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Target Submission Venue</label>
            <select
              value={venue}
              onChange={(e) => setVenue(e.target.value)}
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            >
              {VENUES.map((v) => (
                <option key={v.id} value={v.id} className="bg-slate-900 text-white">
                  {v.label} [{v.tier}]
                </option>
              ))}
            </select>
          </div>

          {/* Author Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Primary Author Name</label>
            <input
              type="text"
              value={authorName}
              onChange={(e) => setAuthorName(e.target.value)}
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Affiliation */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Institution / Affiliation</label>
            <input
              type="text"
              value={authorAffiliation}
              onChange={(e) => setAuthorAffiliation(e.target.value)}
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Paper Type */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Article Taxonomy</label>
            <select
              value={paperType}
              onChange={(e) => setPaperType(e.target.value)}
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            >
              {PAPER_TYPES.map((pt) => (
                <option key={pt} value={pt} className="bg-slate-900 text-white">
                  {pt}
                </option>
              ))}
            </select>
          </div>

          {/* Author Email */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Author Email</label>
            <input
              type="email"
              value={authorEmail}
              onChange={(e) => setAuthorEmail(e.target.value)}
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Custom Focus / Notes */}
          <div className="space-y-1.5 md:col-span-2">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Custom Focus or Methodological Directives (Optional)</label>
            <input
              type="text"
              value={customNotes}
              onChange={(e) => setCustomNotes(e.target.value)}
              placeholder="e.g. Emphasize multi-scale Riemannian projection, polynomial error decay bounds, and ablation across 3 noise regimes"
              className="w-full bg-slate-950/70 border border-white/10 rounded-xl py-2.5 px-3.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Generate / Re-generate Action Button */}
        <div className="pt-2 flex items-center justify-between border-t border-white/5">
          <div className="text-xs text-slate-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Generates 10 full academic sections, mathematical formulations, and BibTeX database.</span>
          </div>

          <button
            type="button"
            onClick={handleGeneratePaper}
            disabled={generating}
            className="px-8 py-3.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-bold text-sm shadow-xl shadow-indigo-500/25 active:scale-[0.98] transition-all flex items-center gap-2.5 disabled:opacity-50"
          >
            {generating ? (
              <>
                <span className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" />
                <span>Compiling Full Research Paper...</span>
              </>
            ) : (
              <>
                <BookOpen className="w-4 h-4" />
                <span>{paper ? 'Regenerate Complete Paper' : 'Generate Full Research Paper'}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Generated Paper Workspace */}
      {paper && (
        <div className="space-y-6">
          {/* Top Bar: Paper Title, Stats, and Export Actions */}
          <div className="p-6 rounded-3xl bg-slate-900/80 border border-white/10 backdrop-blur-xl shadow-xl flex flex-wrap items-center justify-between gap-6 print:hidden">
            <div className="space-y-1 max-w-2xl">
              <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider">
                Target Venue: {paper.venue} • {paper.paper_type}
              </span>
              <h2 className="text-xl font-extrabold text-white leading-snug">{paper.title}</h2>
              <div className="flex items-center gap-4 text-xs text-slate-400 pt-1">
                <span>{paper.stats?.word_count} words</span>
                <span>•</span>
                <span>{paper.stats?.sections_count} sections</span>
                <span>•</span>
                <span>{paper.stats?.citations_count} citations</span>
              </div>
            </div>

            {/* Export Toolbar */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => api.exportPaperFile('latex', paper.latex, 'research_paper')}
                className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow flex items-center gap-1.5 transition-all"
                title="Download compilation-ready LaTeX source"
              >
                <Download className="w-3.5 h-3.5" />
                <span>LaTeX (.tex)</span>
              </button>

              <button
                type="button"
                onClick={() => api.exportPaperFile('bibtex', paper.bibtex, 'references')}
                className="px-3.5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow flex items-center gap-1.5 transition-all"
                title="Download BibTeX citation database"
              >
                <Download className="w-3.5 h-3.5" />
                <span>BibTeX (.bib)</span>
              </button>

              <button
                type="button"
                onClick={() => api.exportPaperFile('markdown', paper.markdown, 'paper')}
                className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold border border-white/10 flex items-center gap-1.5 transition-all"
                title="Download academic Markdown"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Markdown (.md)</span>
              </button>

              <button
                type="button"
                onClick={() => window.print()}
                className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold border border-white/10 flex items-center gap-1.5 transition-all"
                title="Print or Save as PDF"
              >
                <Printer className="w-3.5 h-3.5 text-slate-300" />
                <span>Print / PDF</span>
              </button>
            </div>
          </div>

          {/* View Switcher Tabs */}
          <div className="flex bg-slate-900/60 p-1.5 rounded-2xl border border-white/10 w-fit print:hidden">
            <button
              onClick={() => setActiveTab('article')}
              className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'article' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Formatted Article</span>
            </button>

            <button
              onClick={() => setActiveTab('latex')}
              className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'latex' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              <FileCode className="w-4 h-4" />
              <span>LaTeX Source (.tex)</span>
            </button>

            <button
              onClick={() => setActiveTab('bibtex')}
              className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'bibtex' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>BibTeX Citations (.bib)</span>
            </button>

            <button
              onClick={() => setActiveTab('markdown')}
              className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'markdown' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Markdown</span>
            </button>

            {review && (
              <button
                onClick={() => setActiveTab('review')}
                className={`px-5 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2 ${
                  activeTab === 'review' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/30' : 'text-slate-400 hover:text-white'
                }`}
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Peer Review Report</span>
              </button>
            )}
          </div>

          {/* TAB 1: Formatted Article View */}
          {activeTab === 'article' && (
            <div className="rounded-3xl bg-slate-900/90 border border-white/10 p-10 md:p-14 shadow-2xl space-y-10 font-sans print:border-none print:shadow-none print:p-0">
              {/* Paper Title & Authors Block */}
              <div className="text-center space-y-4 pb-8 border-b border-white/10">
                <div className="inline-block px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-semibold mb-2">
                  Prepared for {paper.venue} ({paper.venue_info?.style || 'Peer Review'})
                </div>
                <h1 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-tight max-w-4xl mx-auto">
                  {paper.title}
                </h1>

                <div className="pt-2 text-slate-300 text-sm space-y-1">
                  <p className="font-bold text-white text-base">
                    {paper.authors?.map((a: any) => a.name).join(', ')}
                  </p>
                  <p className="text-slate-400 text-xs">{paper.authors?.[0]?.affiliation}</p>
                  <p className="text-slate-500 text-xs font-mono">{paper.authors?.[0]?.email}</p>
                </div>
              </div>

              {/* Abstract Callout */}
              <div className="p-7 rounded-2xl bg-indigo-950/30 border border-indigo-500/20 space-y-3 relative group">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-extrabold text-indigo-300 uppercase tracking-widest">Abstract</h3>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingSection('abstract')
                      setEditText(paper.sections.abstract || '')
                    }}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs flex items-center gap-1"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Edit</span>
                  </button>
                </div>

                {editingSection === 'abstract' ? (
                  <div className="space-y-3">
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      rows={5}
                      className="w-full p-3 rounded-xl bg-slate-950 border border-indigo-500/40 text-white text-sm focus:outline-none"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setEditingSection(null)}
                        className="px-3 py-1.5 rounded-lg bg-white/5 text-slate-400 text-xs"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSaveEdit('abstract')}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-slate-200 text-sm leading-relaxed italic">{paper.sections.abstract}</p>
                )}

                <div className="pt-2 text-xs text-slate-400">
                  <strong className="text-slate-300">Keywords:</strong> {paper.keywords?.join(', ')}
                </div>
              </div>

              {/* Academic Sections */}
              <div className="space-y-12">
                {Object.entries(SECTION_TITLES).map(([secKey, secTitle]) => {
                  if (secKey === 'abstract') return null
                  const content = paper.sections[secKey] || ''

                  return (
                    <section key={secKey} className="space-y-4 relative group">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <h2 className="text-xl font-bold text-white tracking-tight">{secTitle}</h2>

                        {/* Section Actions */}
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity print:hidden">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingSection(secKey)
                              setEditText(content)
                            }}
                            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs flex items-center gap-1"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                            <span>Edit</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              const prompt = window.prompt(
                                `How would you like to improve the "${secTitle}" section?`,
                                'Expand theoretical proofs and add more empirical citations.'
                              )
                              if (prompt) {
                                setRegeneratePrompt(prompt)
                                handleRegenerateSectionSubmit(secKey)
                              }
                            }}
                            disabled={regeneratingSection === secKey}
                            className="p-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 text-xs flex items-center gap-1"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${regeneratingSection === secKey ? 'animate-spin' : ''}`} />
                            <span>Regenerate</span>
                          </button>
                        </div>
                      </div>

                      {editingSection === secKey ? (
                        <div className="space-y-3">
                          <textarea
                            value={editText}
                            onChange={(e) => setEditText(e.target.value)}
                            rows={8}
                            className="w-full p-4 rounded-xl bg-slate-950 border border-indigo-500/40 text-white text-sm focus:outline-none font-mono"
                          />
                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => setEditingSection(null)}
                              className="px-3 py-1.5 rounded-lg bg-white/5 text-slate-400 text-xs"
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSaveEdit(secKey)}
                              className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold"
                            >
                              Save Changes
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap space-y-3">
                          {content}
                        </div>
                      )}
                    </section>
                  )
                })}
              </div>

              {/* References */}
              <div className="pt-8 border-t border-white/10 space-y-4">
                <h2 className="text-xl font-bold text-white tracking-tight">10. References</h2>
                <pre className="p-5 rounded-2xl bg-slate-950/70 border border-white/10 text-xs text-slate-400 font-mono overflow-x-auto">
                  {paper.bibtex}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 2: LaTeX View */}
          {activeTab === 'latex' && (
            <div className="rounded-3xl bg-slate-950 border border-white/10 p-6 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 text-indigo-400 font-bold">
                  <FileCode className="w-4 h-4" />
                  <span>Compilation-Ready LaTeX Document (.tex)</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCopy(paper.latex, 'latex')}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs flex items-center gap-1.5 transition-colors"
                  >
                    {copied === 'latex' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied === 'latex' ? 'Copied!' : 'Copy LaTeX'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => api.exportPaperFile('latex', paper.latex, 'paper')}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download .tex</span>
                  </button>
                </div>
              </div>

              <textarea
                readOnly
                value={paper.latex}
                rows={28}
                className="w-full bg-transparent text-slate-300 font-mono text-xs focus:outline-none resize-none leading-relaxed"
              />
            </div>
          )}

          {/* TAB 3: BibTeX View */}
          {activeTab === 'bibtex' && (
            <div className="rounded-3xl bg-slate-950 border border-white/10 p-6 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 text-purple-400 font-bold">
                  <BookOpen className="w-4 h-4" />
                  <span>Academic BibTeX Citation Database (.bib)</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCopy(paper.bibtex, 'bibtex')}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs flex items-center gap-1.5"
                  >
                    {copied === 'bibtex' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied === 'bibtex' ? 'Copied!' : 'Copy BibTeX'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => api.exportPaperFile('bibtex', paper.bibtex, 'references')}
                    className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download .bib</span>
                  </button>
                </div>
              </div>

              <textarea
                readOnly
                value={paper.bibtex}
                rows={20}
                className="w-full bg-transparent text-slate-300 font-mono text-xs focus:outline-none resize-none leading-relaxed"
              />
            </div>
          )}

          {/* TAB 4: Markdown View */}
          {activeTab === 'markdown' && (
            <div className="rounded-3xl bg-slate-950 border border-white/10 p-6 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 text-slate-300 font-bold">
                  <FileText className="w-4 h-4" />
                  <span>Publication Markdown with Frontmatter</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCopy(paper.markdown, 'markdown')}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs flex items-center gap-1.5"
                  >
                    {copied === 'markdown' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied === 'markdown' ? 'Copied!' : 'Copy Markdown'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => api.exportPaperFile('markdown', paper.markdown, 'paper')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download .md</span>
                  </button>
                </div>
              </div>

              <textarea
                readOnly
                value={paper.markdown}
                rows={28}
                className="w-full bg-transparent text-slate-300 font-mono text-xs focus:outline-none resize-none leading-relaxed"
              />
            </div>
          )}

          {/* TAB 5: Peer Review Report */}
          {activeTab === 'review' && review && (
            <div className="rounded-3xl bg-slate-900/90 border border-emerald-500/30 p-8 space-y-8 shadow-2xl">
              {/* Review Scorecards */}
              <div className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-white/10">
                <div>
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                    {review.reviewer_role}
                  </span>
                  <h3 className="text-2xl font-black text-white mt-1">Official Peer Review Evaluation</h3>
                  <p className="text-xs text-slate-400">Calibrated against {review.venue} acceptance standards</p>
                </div>

                <div className="flex items-center gap-6">
                  <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-center">
                    <span className="text-[10px] uppercase font-bold text-emerald-300 block">Recommendation</span>
                    <span className="text-base font-extrabold text-white">{review.recommendation}</span>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-blue-500/10 border border-blue-500/30 text-center">
                    <span className="text-[10px] uppercase font-bold text-blue-300 block">Acceptance Prob.</span>
                    <span className="text-xl font-black text-white">{Math.round(review.acceptance_probability * 100)}%</span>
                  </div>
                </div>
              </div>

              {/* 4 Score Metric Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-center space-y-1">
                  <span className="text-[11px] text-slate-400 font-semibold">Novelty</span>
                  <p className="text-2xl font-black text-indigo-400">{review.scores.novelty} / 10</p>
                </div>
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-center space-y-1">
                  <span className="text-[11px] text-slate-400 font-semibold">Theoretical Rigor</span>
                  <p className="text-2xl font-black text-cyan-400">{review.scores.theoretical_soundness} / 10</p>
                </div>
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-center space-y-1">
                  <span className="text-[11px] text-slate-400 font-semibold">Empirical Soundness</span>
                  <p className="text-2xl font-black text-emerald-400">{review.scores.empirical_rigor} / 10</p>
                </div>
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-center space-y-1">
                  <span className="text-[11px] text-slate-400 font-semibold">Presentation & Clarity</span>
                  <p className="text-2xl font-black text-amber-400">{review.scores.clarity_and_presentation} / 10</p>
                </div>
              </div>

              {/* Review Text */}
              <div className="p-6 rounded-2xl bg-slate-950/60 border border-white/10 space-y-4">
                <h4 className="text-sm font-bold text-white uppercase tracking-wider">Detailed Review Comments</h4>
                <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {review.review_summary}
                </div>
              </div>

              {/* Pre-submission Checklist */}
              {review.action_checklist && (
                <div className="p-6 rounded-2xl bg-amber-500/5 border border-amber-500/20 space-y-3">
                  <h4 className="text-xs font-extrabold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Author Action Checklist Prior to Submission</span>
                  </h4>
                  <ul className="space-y-2">
                    {review.action_checklist.map((item: string, idx: number) => (
                      <li key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                        <ChevronRight className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
