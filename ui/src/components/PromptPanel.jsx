import { useState } from 'react'

const PLACEHOLDER = `Describe what you want to build, e.g.:

Build a REST API for a task manager with user authentication,
SQLite persistence, and full CRUD operations.`

export default function PromptPanel({ onRun, onStop, running }) {
  const [requirement, setRequirement] = useState('')
  const [mock, setMock] = useState(false)

  const hasKey = Boolean(localStorage.getItem('anthropic_api_key'))
  const canRun = requirement.trim().length > 0

  const handleRun = () => {
    if (!canRun || running) return
    onRun(requirement.trim(), mock)
  }

  const handleKeyDown = e => {
    // Ctrl+Enter or Cmd+Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleRun()
    }
  }

  return (
    <div className="prompt-panel">
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
