import { useEffect, useMemo, useState } from 'react'
import { Activity, Bell, Database, Save, Settings as SettingsIcon, Shield, Zap } from 'lucide-react'
import { api } from '../api'

type Preferences = {
  sources: Record<string, boolean>
  notifications: Record<string, boolean>
  processing: Record<string, boolean>
  cacheTtlSeconds: number
  defaultPaperLimit: number
  discoveryDomain: string
  localOnly: boolean
  retentionDays: number
}

const DEFAULT_PREFS: Preferences = {
  sources: {
    huggingface: true,
    arxiv: true,
    pubmed: true,
    openalex: true,
    biorxiv: true,
    medrxiv: true,
    core: false,
  },
  notifications: {
    newPapers: true,
    contradictions: true,
    bottlenecks: true,
    hypotheses: true,
    dailyDigest: true,
  },
  processing: {
    autoIndex: true,
    replayOnNewData: true,
    crossDomainAnalysis: true,
    parallelFetch: true,
  },
  cacheTtlSeconds: 300,
  defaultPaperLimit: 30,
  discoveryDomain: '',
  localOnly: false,
  retentionDays: 90,
}

function loadPrefs(): Preferences {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem('gsm_settings') || '{}') }
  } catch {
    return DEFAULT_PREFS
  }
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="sr-only peer" />
      <div className="w-9 h-5 bg-slate-700 rounded-full peer peer-checked:bg-blue-500 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
    </label>
  )
}

export function Settings() {
  const [prefs, setPrefs] = useState<Preferences>(loadPrefs)
  const [saved, setSaved] = useState(false)
  const [health, setHealth] = useState<any>(null)
  const [models, setModels] = useState<any>(null)

  useEffect(() => {
    Promise.allSettled([api.health(), api.graphHealth(), api.memoryStats()])
      .then(([healthRes, graphRes, memoryRes]) => {
        setHealth({
          health: healthRes.status === 'fulfilled' ? healthRes.value : null,
          graph: graphRes.status === 'fulfilled' ? graphRes.value : null,
          memory: memoryRes.status === 'fulfilled' ? memoryRes.value : null,
        })
      })
    fetch('/api/llm/models').then(r => r.json()).then(setModels).catch(() => setModels(null))
  }, [])

  const enabledSources = useMemo(
    () => Object.values(prefs.sources).filter(Boolean).length,
    [prefs.sources]
  )

  const updateGroup = (group: 'sources' | 'notifications' | 'processing', key: string, value: boolean) => {
    setPrefs(prev => ({ ...prev, [group]: { ...prev[group], [key]: value } }))
  }

  const save = () => {
    localStorage.setItem('gsm_settings', JSON.stringify(prefs))
    setSaved(true)
    setTimeout(() => setSaved(false), 1800)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Settings</h1>
          <p className="text-slate-400 mt-1">Configure sources, fetching behavior, alerts, and local research preferences</p>
        </div>
        <button onClick={save} className="glass-card px-4 py-2 flex items-center gap-2 text-sm text-blue-300 hover:text-white transition-colors">
          <Save className="h-4 w-4" />
          {saved ? 'Saved' : 'Save'}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Database className="h-5 w-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Research Sources</h2>
          </div>
          <div className="space-y-3">
            {Object.entries(prefs.sources).map(([key, enabled]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm text-slate-300 capitalize">{key.replace(/([a-z])([A-Z])/g, '$1 $2')}</span>
                <Toggle checked={enabled} onChange={value => updateGroup('sources', key, value)} />
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-5 w-5 text-yellow-400" />
            <h2 className="text-lg font-semibold text-white">Fetch Performance</h2>
          </div>
          <div className="space-y-4">
            <label className="block text-sm text-slate-300">
              Default paper limit
              <input type="number" min={5} max={100} value={prefs.defaultPaperLimit} onChange={e => setPrefs(prev => ({ ...prev, defaultPaperLimit: Number(e.target.value) }))} className="mt-1 w-full px-3 py-2 rounded bg-slate-800 text-slate-300 border border-slate-700 focus:outline-none focus:border-blue-500" />
            </label>
            <label className="block text-sm text-slate-300">
              Cache TTL seconds
              <input type="number" min={30} max={3600} value={prefs.cacheTtlSeconds} onChange={e => setPrefs(prev => ({ ...prev, cacheTtlSeconds: Number(e.target.value) }))} className="mt-1 w-full px-3 py-2 rounded bg-slate-800 text-slate-300 border border-slate-700 focus:outline-none focus:border-blue-500" />
            </label>
            <label className="block text-sm text-slate-300">
              Preferred discovery niche
              <input type="text" value={prefs.discoveryDomain} onChange={e => setPrefs(prev => ({ ...prev, discoveryDomain: e.target.value }))} placeholder="e.g. graph neural networks" className="mt-1 w-full px-3 py-2 rounded bg-slate-800 text-slate-300 border border-slate-700 focus:outline-none focus:border-blue-500" />
            </label>
          </div>
        </div>

        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">Processing</h2>
          </div>
          <div className="space-y-3">
            {Object.entries(prefs.processing).map(([key, enabled]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm text-slate-300">{key.replace(/([A-Z])/g, ' $1')}</span>
                <Toggle checked={enabled} onChange={value => updateGroup('processing', key, value)} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Bell className="h-5 w-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Notifications</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(prefs.notifications).map(([key, enabled]) => (
              <div key={key} className="flex items-center justify-between gap-4">
                <span className="text-sm text-slate-300">{key.replace(/([A-Z])/g, ' $1')}</span>
                <Toggle checked={enabled} onChange={value => updateGroup('notifications', key, value)} />
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="h-5 w-5 text-rose-400" />
            <h2 className="text-lg font-semibold text-white">Security & Privacy</h2>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300">Local processing only</span>
              <Toggle checked={prefs.localOnly} onChange={value => setPrefs(prev => ({ ...prev, localOnly: value }))} />
            </div>
            <label className="block text-sm text-slate-300">
              Data retention days
              <input type="number" min={1} max={3650} value={prefs.retentionDays} onChange={e => setPrefs(prev => ({ ...prev, retentionDays: Number(e.target.value) }))} className="mt-1 w-32 px-3 py-2 rounded bg-slate-800 text-slate-300 border border-slate-700 focus:outline-none focus:border-blue-500" />
            </label>
          </div>
        </div>
      </div>

      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <SettingsIcon className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">System Information</h2>
        </div>
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div><span className="text-slate-500">Enabled sources: </span><span className="text-slate-300">{enabledSources}</span></div>
          <div><span className="text-slate-500">API: </span><span className="text-slate-300">{health?.health?.status || 'checking'}</span></div>
          <div><span className="text-slate-500">Graph health: </span><span className="text-slate-300">{health?.graph ? `${(health.graph.health_score * 100).toFixed(0)}%` : 'checking'}</span></div>
          <div><span className="text-slate-500">LLM: </span><span className="text-slate-300">{models?.current_provider || 'checking'}</span></div>
          <div><span className="text-slate-500">Concepts: </span><span className="text-slate-300">{health?.memory?.semantic?.concepts ?? 0}</span></div>
          <div><span className="text-slate-500">Papers: </span><span className="text-slate-300">{health?.memory?.semantic?.papers ?? 0}</span></div>
          <div><span className="text-slate-500">Cache target: </span><span className="text-slate-300">{prefs.cacheTtlSeconds}s</span></div>
          <div><span className="text-slate-500">Default limit: </span><span className="text-slate-300">{prefs.defaultPaperLimit}</span></div>
        </div>
      </div>
    </div>
  )
}
