import { Settings as SettingsIcon, Bell, Database, Activity, Shield } from 'lucide-react'

const sections = [
  {
    title: 'Research Sources',
    icon: Database,
    settings: [
      { name: 'arXiv', enabled: true },
      { name: 'PubMed', enabled: true },
      { name: 'Semantic Scholar', enabled: true },
      { name: 'OpenAlex', enabled: true },
      { name: 'Nature', enabled: false },
      { name: 'Science', enabled: false },
      { name: 'Cell', enabled: false },
    ],
  },
  {
    title: 'Notifications',
    icon: Bell,
    settings: [
      { name: 'New Papers in Domain', enabled: true },
      { name: 'Contradictions Detected', enabled: true },
      { name: 'Bottlenecks Found', enabled: true },
      { name: 'Hypotheses Generated', enabled: true },
      { name: 'Daily Discovery Digest', enabled: true },
      { name: 'Weekly Graph Summary', enabled: false },
    ],
  },
  {
    title: 'Processing',
    icon: Activity,
    settings: [
      { name: 'Auto-index Papers', enabled: true },
      { name: 'Run Replay on New Data', enabled: true },
      { name: 'Daily Dream Cycle', enabled: true },
      { name: 'Cross-domain Analysis', enabled: true },
      { name: 'GPU Acceleration', enabled: false },
      { name: 'Parallel Processing', enabled: true },
    ],
  },
  {
    title: 'Security & Privacy',
    icon: Shield,
    settings: [
      { name: 'Encrypt Research Data', enabled: true },
      { name: 'Anonymous Analytics', enabled: true },
      { name: 'Local Processing Only', enabled: false },
      { name: 'Data Retention (days)', value: '90', isValue: true },
    ],
  },
]

export function Settings() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Settings</h1>
          <p className="text-slate-400 mt-1">Configure GSM-OS system preferences</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {sections.map((section) => (
          <div key={section.title} className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <section.icon className="h-5 w-5 text-blue-400" />
              <h2 className="text-lg font-semibold text-white">{section.title}</h2>
            </div>
            <div className="space-y-3">
              {section.settings.map((setting) => (
                <div key={setting.name} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">{setting.name}</span>
                  {'enabled' in setting ? (
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        defaultChecked={setting.enabled}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-slate-700 rounded-full peer peer-checked:bg-blue-500 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
                    </label>
                  ) : (
                    <input
                      type="text"
                      defaultValue={setting.value}
                      className="w-20 px-2 py-1 rounded text-sm bg-slate-800 text-slate-300 border border-slate-700 focus:outline-none focus:border-blue-500 text-center"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* System Info */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <SettingsIcon className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">System Information</h2>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Version', value: '0.1.0' },
            { label: 'Environment', value: 'Development' },
            { label: 'Python Version', value: '3.11' },
            { label: 'Database', value: 'Qdrant + Neo4j' },
            { label: 'Task Queue', value: 'Celery + Redis' },
            { label: 'LLM Backend', value: 'GPT-4 + Claude' },
          ].map((info) => (
            <div key={info.label} className="text-sm">
              <span className="text-slate-500">{info.label}: </span>
              <span className="text-slate-300">{info.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
