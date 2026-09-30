import { useState, useEffect, useCallback, useRef } from 'react'
import { Network, Search, RotateCw, AlertTriangle, Loader2 } from 'lucide-react'
import * as d3 from 'd3-force'
import { api } from '../api'
import { useEventStore } from '../store/eventStore'

const MAJOR_GROUPS: Record<string, { color: string; label: string; subcategories: string[] }> = {
  drugs: {
    color: '#ef4444',
    label: 'Drugs',
    subcategories: ['small_molecule', 'antibody', 'vaccine', 'gene_therapy', 'immunotherapy', 'nanomedicine'],
  },
  medicine: {
    color: '#3b82f6',
    label: 'Medicine',
    subcategories: ['oncology', 'cardiology', 'neurology', 'clinical_trial', 'diagnostics', 'epidemiology'],
  },
  tech: {
    color: '#a855f7',
    label: 'Tech',
    subcategories: ['ai_ml', 'robotics', 'quantum', 'semiconductor', 'blockchain', 'cybersecurity'],
  },
  physics: {
    color: '#f59e0b',
    label: 'Physics',
    subcategories: ['particle', 'condensed_matter', 'astrophysics', 'optics', 'plasma', 'quantum_physics'],
  },
  others: {
    color: '#6b7280',
    label: 'Others',
    subcategories: ['chemistry', 'materials', 'biology', 'environment', 'math', 'education'],
  },
}

const SUBCAT_LABELS: Record<string, string> = {
  small_molecule: 'Small Molecule', antibody: 'Antibody', vaccine: 'Vaccine',
  gene_therapy: 'Gene Therapy', immunotherapy: 'Immunotherapy', nanomedicine: 'Nanomedicine',
  oncology: 'Oncology', cardiology: 'Cardiology', neurology: 'Neurology',
  clinical_trial: 'Clinical Trial', diagnostics: 'Diagnostics', epidemiology: 'Epidemiology',
  ai_ml: 'AI/ML', robotics: 'Robotics', quantum: 'Quantum Computing',
  semiconductor: 'Semiconductor', blockchain: 'Blockchain', cybersecurity: 'Cybersecurity',
  particle: 'Particle Physics', condensed_matter: 'Condensed Matter', astrophysics: 'Astrophysics',
  optics: 'Optics', plasma: 'Plasma Physics', quantum_physics: 'Quantum Physics',
  chemistry: 'Chemistry', materials: 'Materials Sci.', biology: 'Biology',
  environment: 'Environment', math: 'Mathematics', education: 'Education',
}

const MAJOR_CATEGORIES = ['drugs', 'medicine', 'tech', 'physics', 'others']

type GraphNode = {
  id: string
  group: string
  subcategory?: string
  val: number
  isMajor?: boolean
  x?: number
  y?: number
}

type GraphLink = {
  source: string
  target: string
  label?: string
}

type GraphData = {
  nodes: GraphNode[]
  links: GraphLink[]
}

export function GraphExplorer() {
  const [searchQuery, setSearchQuery] = useState('')
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [health, setHealth] = useState<any>(null)
  const [clusters, setClusters] = useState<any[]>([])
  const [links, setLinks] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loadingPapers, setLoadingPapers] = useState(false)

  const simRef = useRef<d3.Simulation<any, any> | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const events = useEventStore((s) => s.events['graph'] || [])

  // Build graph from real papers in memory
  const buildGraphFromPapers = useCallback(async (topic = '') => {
    setLoadingPapers(true)
    try {
      let papers: any[] = []
      if (topic.trim()) {
        const fetched = await api.fetchLatestPapers(topic.trim(), 50)
        papers = fetched.papers || []
      } else {
        const memory = await api.listPapers(1, 200)
        papers = memory.data || []
        if (!papers.length) {
          const fetched = await api.fetchLatestPapers('', 50)
          papers = fetched.papers || []
        }
      }
      if (!papers?.length) return

      // Map paper categories to major groups and subcategories
      const catMap: Record<string, { major: string; sub: string }> = {}
      for (const [major, info] of Object.entries(MAJOR_GROUPS)) {
        for (const sub of info.subcategories) {
          catMap[sub] = { major, sub }
          catMap[sub.replace(/_/g, ' ')] = { major, sub }
          catMap[SUBCAT_LABELS[sub]?.toLowerCase() || ''] = { major, sub }
        }
      }

      // Classify papers
      const majorCounts: Record<string, number> = {}
      const subPapers: Record<string, string[]> = {}
      for (const p of papers) {
        const payload = p.payload || p
        const cats = (payload.categories || []).map((c: string) => String(c).toLowerCase()).filter(Boolean)
        let assigned = false
        for (const cat of cats) {
          const mapped = catMap[cat] || Object.entries(catMap).find(([key]) => cat.includes(key) || key.includes(cat))?.[1]
          if (mapped) {
            majorCounts[mapped.major] = (majorCounts[mapped.major] || 0) + 1
            if (!subPapers[mapped.sub]) subPapers[mapped.sub] = []
            subPapers[mapped.sub].push(payload.title || '')
            assigned = true
            break
          }
        }
        if (!assigned) {
          majorCounts['others'] = (majorCounts['others'] || 0) + 1
          const otherSub = cats[0] || payload.source || 'general'
          if (!subPapers[otherSub]) subPapers[otherSub] = []
          subPapers[otherSub].push(payload.title || '')
        }
      }

      // Build nodes only from real paper/category evidence.
      const nodes: GraphNode[] = []
      const links: GraphLink[] = []
      for (const major of MAJOR_CATEGORIES.filter(m => majorCounts[m] > 0)) {
        const info = MAJOR_GROUPS[major]
        const count = majorCounts[major] || 0

        const majorId = `group:${major}`
        nodes.push({
          id: majorId,
          group: major,
          val: Math.max(10, count * 2),
          isMajor: true,
        })

        const realSubcategories = Object.keys(subPapers).filter(sub => info.subcategories.includes(sub) || major === 'others')
        for (const sub of realSubcategories) {
          const subId = `sub:${major}:${sub}`
          const paperTitles = subPapers[sub] || []
          nodes.push({
            id: subId,
            group: major,
            subcategory: sub,
            val: Math.max(4, paperTitles.length * 1.5),
          })

          links.push({ source: majorId, target: subId, label: 'belongs_to' })
        }

        for (const otherMajor of MAJOR_CATEGORIES) {
          if (otherMajor > major && majorCounts[otherMajor] > 0) {
            links.push({
              source: majorId,
              target: `group:${otherMajor}`,
              label: 'cross_domain',
            })
          }
        }
      }

      setGraphData({ nodes, links })
    } catch {
      // fallback below
    } finally {
      setLoadingPapers(false)
    }
  }, [])

  // d3-force render (same as before but with major nodes bigger)
  const redrawGraph = useCallback((data: GraphData) => {
    if (!data || !svgRef.current) return
    const svg = svgRef.current
    const width = svg.clientWidth || 800
    const height = 500

    if (simRef.current) simRef.current.stop()

    let linksG = svg.querySelector('.links-group') as SVGGElement
    let nodesG = svg.querySelector('.nodes-group') as SVGGElement

    if (!linksG) {
      linksG = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      linksG.setAttribute('class', 'links-group')
      svg.appendChild(linksG)
    }
    if (!nodesG) {
      nodesG = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      nodesG.setAttribute('class', 'nodes-group')
      svg.appendChild(nodesG)
    }

    linksG.innerHTML = ''
    data.links.forEach((link) => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
      const isCrossDomain = link.label === 'cross_domain' || link.label === 'belongs_to'
      line.setAttribute('stroke', isCrossDomain ? 'rgba(148,163,184,0.15)' : 'rgba(148,163,184,0.3)')
      line.setAttribute('stroke-width', isCrossDomain ? '0.5' : '1')
      line.setAttribute('stroke-dasharray', link.label === 'belongs_to' ? '3,3' : 'none')
      line.setAttribute('data-source', String(link.source))
      line.setAttribute('data-target', String(link.target))
      linksG.appendChild(line)
    })

    nodesG.innerHTML = ''
    const nodeElements: Map<string, { g: SVGGElement; circle: SVGCircleElement; text: SVGTextElement }> = new Map()

    data.nodes.forEach((node) => {
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      g.setAttribute('class', 'cursor-pointer')
      g.addEventListener('click', () => {
        const wasHighlighted = g.getAttribute('data-highlighted') === 'true'
        const isHighlighted = !wasHighlighted
        g.setAttribute('data-highlighted', String(isHighlighted))
        circle.setAttribute('fill-opacity', isHighlighted ? '1' : '0.7')
        text.setAttribute('fill', isHighlighted ? '#e2e8f0' : '#94a3b8')
      })

      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      const groupInfo = MAJOR_GROUPS[node.group]
      const color = groupInfo?.color || '#6b7280'
      const r = node.isMajor ? Math.max(14, node.val || 14) : Math.max(5, node.val || 5)
      circle.setAttribute('r', '0')
      setTimeout(() => circle.setAttribute('r', String(r)), 10)
      circle.setAttribute('fill', color)
      circle.setAttribute('fill-opacity', node.isMajor ? '0.9' : '0.6')
      circle.setAttribute('stroke', '#fff')
      circle.setAttribute('stroke-width', node.isMajor ? '2' : '0.5')
      g.appendChild(circle)

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('dy', String(r + 14))
      text.setAttribute('text-anchor', 'middle')
      text.setAttribute('fill', node.isMajor ? '#e2e8f0' : '#94a3b8')
      text.setAttribute('font-size', node.isMajor ? '12' : '9')
      text.setAttribute('font-weight', node.isMajor ? 'bold' : 'normal')
      const label = node.isMajor
        ? (MAJOR_GROUPS[node.group]?.label || node.group)
        : (SUBCAT_LABELS[node.subcategory || ''] || node.id.split(':').pop() || node.id)
      text.textContent = label
      g.appendChild(text)

      nodesG.appendChild(g)
      nodeElements.set(node.id, { g, circle, text })
    })

    const simNodes = data.nodes.map((n) => ({ ...n }))
    const simLinks = data.links.map((l) => ({ source: l.source, target: l.target }))

    const sim: any = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink(simLinks).id((d: any) => d.id).distance((d: any) => {
        const s = simNodes.find((n: any) => n.id === d.source?.id || n.id === d.source)
        const t = simNodes.find((n: any) => n.id === d.target?.id || n.id === d.target)
        if (s?.isMajor || t?.isMajor) return 180
        return 80
      }))
      .force('charge', d3.forceManyBody().strength((d: any) => d.isMajor ? -400 : -150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => (d.isMajor ? 30 : 15)))
      .alphaDecay(0.02)

    const lineElements = linksG.querySelectorAll('line')

    sim.on('tick', () => {
      lineElements.forEach((line, i) => {
        const l = simLinks[i]
        if (!l) return
        const s = l.source as any
        const t = l.target as any
        if (s.x != null && s.y != null && t.x != null && t.y != null) {
          line.setAttribute('x1', s.x)
          line.setAttribute('y1', s.y)
          line.setAttribute('x2', t.x)
          line.setAttribute('y2', t.y)
        }
      })
      simNodes.forEach((d: any) => {
        const el = nodeElements.get(d.id)
        if (el && d.x != null && d.y != null) {
          el.g.setAttribute('transform', `translate(${d.x},${d.y})`)
        }
      })
    })

    simRef.current = sim
    return () => { sim.stop() }
  }, [])

  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) return
    redrawGraph(graphData)
  }, [graphData?.nodes.length, graphData?.links.length, redrawGraph])

  useEffect(() => {
    const onResize = () => {
      if (graphData && simRef.current) {
        const svg = svgRef.current
        if (svg) {
          const width = svg.clientWidth || 800
          simRef.current.force('center', d3.forceCenter(width / 2, 250))
          simRef.current.alpha(0.3).restart()
        }
      }
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [graphData])

  // Load real data on mount
  useEffect(() => {
    async function load() {
      try {
        const [gh, ec, ml] = await Promise.all([
          api.graphHealth(),
          api.emergingClusters(),
          api.missingLinks(),
        ])
        setHealth(gh)
        setClusters(ec?.clusters ?? [])
        setLinks(ml?.missing_links ?? [])
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Build graph from real papers after initial load
  useEffect(() => {
    if (!loading) {
      buildGraphFromPapers()
    }
  }, [loading, buildGraphFromPapers])

  // Listen for graph events
  useEffect(() => {
    if (events.length === 0) return
    const lastEvent = events[events.length - 1]

    if (lastEvent.type === 'graph.relationship.created') {
      const { source, target, type: relType } = lastEvent.data || {}
      if (!source || !target) return
      setGraphData((prev) => {
        if (!prev) return prev
        const newNodes = [...prev.nodes]
        const newEdges = [...prev.links]
        if (!newNodes.some((n) => n.id === source)) {
          newNodes.push({ id: source, group: 'others', val: 5 })
        }
        if (!newNodes.some((n) => n.id === target)) {
          newNodes.push({ id: target, group: 'others', val: 5 })
        }
        if (!newEdges.some((e) => `${e.source}-${e.target}` === `${source}-${target}`)) {
          newEdges.push({ source, target, label: relType || 'related' })
        }
        return { nodes: newNodes, links: newEdges }
      })
    }

    if (lastEvent.type === 'graph.concept.created') {
      const concept = lastEvent.data?.concept
      if (!concept) return
      setGraphData((prev) => {
        if (!prev) return prev
        if (prev.nodes.some((n) => n.id === concept)) return prev
        return {
          ...prev,
          nodes: [...prev.nodes, { id: concept, group: lastEvent.data?.domain || 'others', val: 5 }],
        }
      })
    }
  }, [events.length])

  async function handleVisualize(concept: string) {
    if (!concept.trim()) return
    setLoading(true)
    try {
      await buildGraphFromPapers(concept)
      const data = await api.visualizeGraph(concept, 2)
      if (data?.nodes?.length > 0) {
        const nodes: GraphNode[] = data.nodes.map((n: any) => ({
          id: n.id || n,
          group: n.group || 'others',
          val: n.val || n.paper_count || 6,
        }))
        const edges: GraphLink[] = (data.edges || data.links || []).map((e: any) => ({
          source: e.source?.id || e.source,
          target: e.target?.id || e.target,
          label: e.label || e.type || 'related',
        }))
        setGraphData({ nodes, links: edges })
      } else {
        setGraphData({ nodes: [{ id: concept, group: 'others', val: 10 }], links: [] })
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Graph Explorer</h1>
          <p className="text-slate-400 mt-1">Knowledge graph organized by major domains with sub-categories</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => buildGraphFromPapers()} disabled={loadingPapers}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-blue-400 hover:text-blue-300 border border-blue-500/30 transition-colors disabled:opacity-50">
            {loadingPapers ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCw className="h-3 w-3" />}
            Rebuild from Papers
          </button>
        </div>
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Visualize a concept (e.g. CRISPR, GNN, Quantum)"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleVisualize(searchQuery)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg glass-card text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
          />
        </div>
        <button onClick={() => handleVisualize(searchQuery)} disabled={loading}
          className="px-4 py-2.5 rounded-lg bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-50">
          Visualize
        </button>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="col-span-3 glass-card p-4">
          {loading ? (
            <div className="graph-container bg-slate-950/50 rounded-lg border border-white/5 flex items-center justify-center">
              <div className="text-center animate-pulse">
                <Network className="h-16 w-16 text-blue-400/30 mx-auto mb-4" />
                <p className="text-slate-400 text-sm">Loading graph data…</p>
              </div>
            </div>
          ) : error ? (
            <div className="graph-container bg-slate-950/50 rounded-lg border border-rose-500/20 flex items-center justify-center">
              <div className="text-center">
                <AlertTriangle className="h-12 w-12 text-rose-400/50 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">{error}</p>
              </div>
            </div>
          ) : graphData?.nodes?.length ? (
            <div className="graph-container bg-slate-950/50 rounded-lg border border-white/5 overflow-hidden relative">
              <svg ref={svgRef} width="100%" height="500" className="force-graph-svg" />

              {/* Legend */}
              <div className="absolute top-3 left-3 glass-card p-3 text-xs space-y-1.5">
                {Object.entries(MAJOR_GROUPS).map(([key, info]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: info.color }} />
                    <span className="text-slate-300 font-medium">{info.label}</span>
                  </div>
                ))}
                <div className="border-t border-white/10 pt-1.5 mt-1.5">
                  <div className="flex items-center gap-2 text-slate-500">
                    <span className="w-2.5 h-0.5 border-t border-dashed border-slate-500" />
                    belongs_to
                  </div>
                  <div className="flex items-center gap-2 text-slate-500">
                    <span className="w-2.5 h-0.5 bg-slate-500" />
                    cross_domain
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="graph-container bg-slate-950/50 rounded-lg border border-white/5 flex items-center justify-center">
              <div className="text-center">
                <Network className="h-16 w-16 text-blue-400/30 mx-auto mb-4" />
                <p className="text-slate-400 text-sm">Fetch papers first to build the knowledge graph</p>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="glass-card p-4">
            <h3 className="text-sm font-medium text-white mb-3">Graph Stats</h3>
            {health ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Nodes</span><span className="text-white font-medium">{graphData?.nodes?.length ?? health.statistics?.concepts ?? 0}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Edges</span><span className="text-white font-medium">{graphData?.links?.length ?? health.statistics?.relationships ?? 0}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Density</span><span className="text-white font-medium">{(health.density * 100).toFixed(2)}%</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Health</span><span className="text-emerald-400 font-medium">{(health.health_score * 100).toFixed(0)}%</span></div>
              </div>
            ) : (
              <div className="h-20 animate-pulse bg-slate-700/50 rounded" />
            )}
          </div>

          <div className="glass-card p-4">
            <h3 className="text-sm font-medium text-white mb-3">Emerging Clusters</h3>
            {clusters.length > 0 ? (
              <div className="space-y-2">
                {clusters.slice(0, 5).map((c: any, i: number) => (
                  <button key={i} onClick={() => handleVisualize(c.concept)}
                    className="w-full text-left px-2 py-1.5 rounded text-sm text-slate-300 hover:bg-white/5 transition-colors">
                    <div className="font-medium truncate">{c.concept}</div>
                    <div className="text-xs text-slate-500">{c.paper_count} papers · {(c.emergence_score ?? 0).toFixed(1)} score</div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No clusters detected yet</p>
            )}
          </div>

          <div className="glass-card p-4">
            <h3 className="text-sm font-medium text-white mb-3">Missing Links</h3>
            {links.length > 0 ? (
              <div className="space-y-1">
                {links.slice(0, 4).map((l: any, i: number) => (
                  <div key={i} className="text-xs text-slate-400">
                    <span className="text-blue-300">{l.source}</span> ↔ <span className="text-purple-300">{l.target}</span>
                    <div className="text-slate-500">{(l.confidence * 100).toFixed(0)}% confidence</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No missing links found</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
