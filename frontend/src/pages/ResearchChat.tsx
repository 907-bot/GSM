import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: string[]
  timestamp: Date
}

const SUGGESTED_PROMPTS = [
  'What are the most unexplored research combinations in biology?',
  'Summarize recent advances in transformer architectures',
  'What contradictions exist in CRISPR research?',
  'Suggest experiments to validate the link between gut microbiome and depression',
  'What methods are rising in frequency in materials science?',
]

async function streamChat(messages: { role: string; content: string }[]): Promise<AsyncGenerator<string, void, unknown>> {
  const response = await fetch('/api/llm/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, use_graph_context: true, max_context_papers: 5 }),
  })

  if (!response.ok) throw new Error('Chat request failed')
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  async function* generate() {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          if (data === '[DONE]') return
          try {
            yield data
          } catch {}
        }
      }
    }
  }

  return generate()
}

export function ResearchChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hello! I'm your AI research assistant, connected to the scientific knowledge graph. I can help you explore research gaps, explain papers, compare methods, or answer questions grounded in indexed literature. What would you like to explore?",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (content?: string) => {
    const text = (content || input).trim()
    if (!text || isStreaming) return

    const userMsg: Message = { role: 'user', content: text, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsStreaming(true)

    const assistantMsg: Message = { role: 'assistant', content: '', timestamp: new Date() }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }))
      const stream = await streamChat(history)

      for await (const data of stream) {
        try {
          const parsed = JSON.parse(data)
          if (parsed.token) {
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: updated[updated.length - 1].content + parsed.token,
              }
              return updated
            })
          }
          if (parsed.citations) {
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                citations: parsed.citations,
              }
              return updated
            })
          }
        } catch {}
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: '⚠️ Failed to get a response. Please check that the API is running.',
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)', gap: 0 }}>
      {/* Header */}
      <div style={{
        padding: '20px 24px 16px',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(168,85,247,0.15) 100%)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18,
          }}>🧬</div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>AI Research Assistant</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#94a3b8' }}>
              Grounded in your knowledge graph · {messages.length - 1} turns
            </p>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }} />
            <span style={{ fontSize: 12, color: '#10b981' }}>Graph Connected</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        {messages.length === 1 && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <p style={{ color: '#64748b', fontSize: 14, marginBottom: 20 }}>Try asking:</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {SUGGESTED_PROMPTS.map(prompt => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  style={{
                    padding: '8px 14px',
                    background: 'rgba(99,102,241,0.15)',
                    border: '1px solid rgba(99,102,241,0.3)',
                    borderRadius: 20,
                    color: '#a5b4fc',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    textAlign: 'left',
                    maxWidth: 280,
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              gap: 12,
              alignItems: 'flex-start',
            }}
          >
            {/* Avatar */}
            <div style={{
              width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
              background: msg.role === 'user'
                ? 'linear-gradient(135deg, #6366f1, #a855f7)'
                : 'linear-gradient(135deg, #0ea5e9, #10b981)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14,
            }}>
              {msg.role === 'user' ? '👤' : '🧬'}
            </div>

            {/* Bubble */}
            <div style={{ maxWidth: '75%' }}>
              <div style={{
                padding: '12px 16px',
                borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                background: msg.role === 'user'
                  ? 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(168,85,247,0.3))'
                  : 'rgba(255,255,255,0.05)',
                border: `1px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.1)'}`,
                color: '#e2e8f0',
                fontSize: 14,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
              }}>
                {msg.content}
                {isStreaming && i === messages.length - 1 && msg.role === 'assistant' && (
                  <span style={{ display: 'inline-block', width: 2, height: 14, background: '#6366f1', marginLeft: 2, animation: 'blink 1s infinite' }} />
                )}
              </div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(16,185,129,0.1)', borderRadius: 8, border: '1px solid rgba(16,185,129,0.2)' }}>
                  <p style={{ margin: '0 0 4px', fontSize: 11, color: '#6ee7b7', fontWeight: 600 }}>📚 SOURCES FROM KNOWLEDGE BASE</p>
                  {msg.citations.map((c, ci) => (
                    <p key={ci} style={{ margin: '2px 0', fontSize: 11, color: '#94a3b8' }}>{c}</p>
                  ))}
                </div>
              )}

              <p style={{ margin: '4px 0 0', fontSize: 10, color: '#475569' }}>
                {msg.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '16px 24px 20px',
        background: 'rgba(15,23,42,0.8)',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        flexShrink: 0,
      }}>
        <div style={{
          display: 'flex',
          gap: 12,
          alignItems: 'flex-end',
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 16,
          padding: '12px 16px',
        }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about the scientific knowledge graph..."
            disabled={isStreaming}
            rows={1}
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: '#e2e8f0',
              fontSize: 14,
              resize: 'none',
              fontFamily: 'inherit',
              lineHeight: 1.5,
            }}
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || isStreaming}
            style={{
              width: 36, height: 36,
              borderRadius: '50%',
              background: (!input.trim() || isStreaming) ? 'rgba(255,255,255,0.1)' : 'linear-gradient(135deg, #6366f1, #a855f7)',
              border: 'none',
              cursor: (!input.trim() || isStreaming) ? 'not-allowed' : 'pointer',
              color: 'white',
              fontSize: 16,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.2s',
              flexShrink: 0,
            }}
          >
            {isStreaming ? '⏳' : '↑'}
          </button>
        </div>
        <p style={{ margin: '8px 0 0', textAlign: 'center', fontSize: 11, color: '#334155' }}>
          Responses grounded in {' '}
          <span style={{ color: '#6366f1' }}>your indexed papers</span>
          {' '}· Press Shift+Enter for new line
        </p>
      </div>

      <style>{`@keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }`}</style>
    </div>
  )
}
