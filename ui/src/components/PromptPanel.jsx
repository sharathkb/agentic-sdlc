import { useState } from 'react'

const SCENARIOS = [
  {
    id: 'greenfield',
    label: 'Greenfield',
    badge: 'full build + tests',
    color: 'green',
    text:
      'Build a scalable URL shortener service with APIs, persistence, and analytics.\n\n' +
      'It should let clients submit a long URL and receive a short code, redirect short\n' +
      'codes to their target, and expose analytics on how often each short link is used.',
  },
  {
    id: 'brownfield',
    label: 'Brownfield',
    badge: 'halts at risk gate',
    color: 'blue',
    text:
      'Add per-client rate limiting to the existing URL shortener API so that abusive\n' +
      'clients are throttled. Requests above the configured limit should receive an\n' +
      'HTTP 429 response. Apply it across all endpoints as middleware.',
  },
  {
    id: 'ambiguous',
    label: 'Ambiguous',
    badge: 'halts at understanding gate',
    color: 'yellow',
    text: 'Make the app better and faster.',
  },
]

const PLACEHOLDER = `Describe what you want to build, e.g.:

Build a REST API for a task manager with user authentication,
SQLite persistence, and full CRUD operations.`

export default function PromptPanel({ onRun, onStop, running }) {
  const [requirement, setRequirement] = useState('')
  const [mock, setMock] = useState(false)

  const hasKey = Boolean(localStorage.getItem('anthropic_api_key'))
  const canRun = requirement.trim().length > 0

  const loadScenario = (scenario) => {
    setRequirement(scenario.text)
    setMock(true)
  }

  const handleRun = () => {
    if (!canRun || running) return
    onRun(requirement.trim(), mock)
  }

  const handleKeyDown = e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleRun()
  }

  return (
    <div className="prompt-panel">
      {/* Scenario presets */}
      <div className="scenario-row">
        <span className="scenario-label">Quick scenarios</span>
        {SCENARIOS.map(s => (
          <button
            key={s.id}
            className={`btn-scenario btn-scenario-${s.color}`}
            onClick={() => loadScenario(s)}
            disabled={running}
            title={s.badge}
          >
            {s.label}
            <span className="scenario-badge">{s.badge}</span>
          </button>
        ))}
      </div>

      <label>Requirement</label>
      <textarea
        className="prompt-textarea"
        value={requirement}
        onChange={e => setRequirement(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={PLACEHOLDER}
        disabled={running}
      />
      <div className="prompt-controls">
        {running ? (
          <button className="btn btn-danger-run" onClick={onStop}>
            ⏹ Stop
          </button>
        ) : (
          <button
            className="btn btn-primary"
            onClick={handleRun}
            disabled={!canRun}
            title="Ctrl+Enter"
          >
            ▶ Run
          </button>
        )}

        <label className="toggle-label">
          <input
            type="checkbox"
            checked={mock}
            onChange={e => setMock(e.target.checked)}
            disabled={running}
          />
          Mock mode
        </label>

        {!mock && (
          <span className={`key-indicator ${hasKey ? '' : 'key-missing'}`}>
            {hasKey ? '🔑 Key set' : '⚠ No API key — open Settings'}
          </span>
        )}
      </div>
    </div>
  )
}
