import { useState, useRef } from 'react'
import Settings from './components/Settings'
import PromptPanel from './components/PromptPanel'
import LogStream from './components/LogStream'
import ArtifactViewer from './components/ArtifactViewer'

export default function App() {
  const [showSettings, setShowSettings] = useState(false)
  const [logs, setLogs] = useState([])
  const [running, setRunning] = useState(false)
  const [runStatus, setRunStatus] = useState(null)
  const [artifactRefresh, setArtifactRefresh] = useState(0)
  const abortRef = useRef(null)

  const handleRun = async (requirement, mock) => {
    setLogs([])
    setRunStatus(null)
    setRunning(true)

    const apiKey = localStorage.getItem('anthropic_api_key') || ''
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'x-api-key': apiKey } : {}),
        },
        body: JSON.stringify({ requirement, mock, api_key: apiKey || undefined }),
        signal: controller.signal,
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line in buffer
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'log') {
              setLogs(prev => [...prev, data])
            } else if (['done', 'halted', 'error'].includes(data.type)) {
              setRunStatus(data)
              setRunning(false)
              if (data.type === 'done') setArtifactRefresh(n => n + 1)
            }
          } catch { /* skip malformed SSE line */ }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setRunStatus({ type: 'error', msg: err.message })
      }
      setRunning(false)
    }
  }

  const handleStop = () => {
    abortRef.current?.abort()
    setRunning(false)
    setRunStatus({ type: 'error', msg: 'Run cancelled.' })
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <span className="app-icon">🤖</span>
          <span>Agentic SDLC</span>
        </div>
        <button className="btn-settings" onClick={() => setShowSettings(true)}>
          ⚙ Settings
        </button>
      </header>

      <div className="app-body">
        <div className="left-panel">
          <PromptPanel onRun={handleRun} onStop={handleStop} running={running} />
          <LogStream logs={logs} status={runStatus} running={running} />
        </div>
        <div className="right-panel">
          <ArtifactViewer refreshKey={artifactRefresh} />
        </div>
      </div>

      {showSettings && <Settings onClose={() => setShowSettings(false)} />}
    </div>
  )
}
