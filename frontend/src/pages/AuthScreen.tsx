import React, { useState } from 'react'
import { Brain, Mail, Lock, User, ShieldAlert, ArrowRight, Sparkles, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../store/authStore'

export function AuthScreen() {
  const [isLogin, setIsLogin] = useState(true)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('researcher')
  const [validationError, setValidationError] = useState<string | null>(null)
  
  const { login, register, loading, error: authError } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    if (!email.trim() || !password.trim()) {
      setValidationError('Please fill in all required fields.')
      return
    }

    if (password.length < 8) {
      setValidationError('Password must be at least 8 characters long.')
      return
    }

    try {
      if (isLogin) {
        await login(email, password)
      } else {
        if (!name.trim()) {
          setValidationError('Please enter your name.')
          return
        }
        await register(name, email, password, role)
      }
    } catch (err) {
      // Handled by authStore
    }
  }

  const activeError = validationError || authError

  return (
    <div className="min-h-screen w-screen flex items-center justify-center bg-[#090d16] relative overflow-hidden font-sans">
      {/* Background blobs for premium depth */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-gradient-to-br from-blue-500/20 to-cyan-500/0 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/0 blur-[120px] pointer-events-none" />

      {/* Main card */}
      <div className="w-full max-w-md p-8 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-2xl shadow-[0_8px_32px_0_rgba(0,0,0,0.37)] relative z-10 mx-4">
        {/* Branding header */}
        <div className="text-center mb-8">
          <div className="inline-flex p-3 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 shadow-[0_0_20px_rgba(99,102,241,0.5)] mb-4 animate-pulse">
            <Brain className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-200 to-purple-400 tracking-tight">
            GSM-OS
          </h1>
          <p className="text-slate-400 mt-2 text-sm font-medium">
            Global Scientific Memory Operating System
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex bg-slate-900/50 p-1 rounded-lg border border-white/5 mb-6">
          <button
            onClick={() => { setIsLogin(true); setValidationError(null); }}
            className={`flex-1 py-2 text-sm font-semibold rounded-md transition-all duration-300 ${
              isLogin ? 'bg-white/10 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => { setIsLogin(false); setValidationError(null); }}
            className={`flex-1 py-2 text-sm font-semibold rounded-md transition-all duration-300 ${
              !isLogin ? 'bg-white/10 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Error panel */}
        {activeError && (
          <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="text-sm text-rose-200 font-medium">{activeError}</div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Isaac Newton"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-900/40 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all duration-200"
                />
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="email"
                placeholder="newton@gsm-os.org"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-900/40 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all duration-200"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900/40 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all duration-200"
              />
            </div>
          </div>

          {!isLogin && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">System Role</label>
              <div className="relative">
                <ShieldAlert className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full bg-slate-900/40 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-white text-sm focus:outline-none focus:border-blue-500 transition-all duration-200 appearance-none cursor-pointer"
                >
                  <option value="researcher" className="bg-[#090d16] text-white">Researcher (Default)</option>
                  <option value="admin" className="bg-[#090d16] text-white">Administrator</option>
                  <option value="viewer" className="bg-[#090d16] text-white">Viewer</option>
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 text-xs">▼</div>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-6 py-3 rounded-lg bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white font-semibold hover:shadow-[0_0_20px_rgba(99,102,241,0.4)] hover:brightness-110 active:scale-[0.98] transition-all duration-200 flex items-center justify-center gap-2 text-sm disabled:opacity-50 disabled:pointer-events-none"
          >
            {loading ? (
              <span className="w-5 h-5 rounded-full border-2 border-white/20 border-t-white animate-spin" />
            ) : (
              <>
                {isLogin ? 'Sign In' : 'Create Account'}
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        {/* Info footer */}
        <div className="mt-8 pt-6 border-t border-white/5 flex items-center justify-center gap-2 text-xs text-slate-500">
          <Sparkles className="h-3 w-3 text-indigo-400" />
          <span>Secured with AES-256 JWT Authorization</span>
        </div>
      </div>
    </div>
  )
}
