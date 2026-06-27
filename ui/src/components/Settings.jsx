import { useState } from 'react'

const MODELS = [
  { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6 — faster & cheaper (recommended)' },
  { id: 'claude-opus-4-8',   label: 'Claude Opus 4.8 — smartest, slower & pricier' },
]

export default function Settings({ onClose }) {
  const [apiKey, setApiKey] = useState(localStorage.getItem('anthropic_api_key') || '')
  const [model, setModel]   = useState(localStorage.getItem('anthropic_model') || 'claude-sonnet-4-6')
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved]     = useState(false)

  const hasSavedKey = Boolean(localStorage.getItem('anthropic_api_key'))

  const handleSave = () => {
    if (apiKey.trim()) {
      localStorage.setItem('anthropic_api_key', apiKey.trim())
    } else {
      localStorage.removeItem('anthropic_api_key')
    }
    localStorage.setItem('anthropic_model', model)
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const handleClear = () => {
    setApiKey('')
    localStorage.removeItem('anthropic_api_key')
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>

        <div className="modal-header">
          <h2>⚙ Settings</h2>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">

          {/* API Key */}
          <div className="field">
            <label>Anthropic API Key</label>
            <p className="field-hint">
              Stored only in your browser (<code>localStorage</code>). Sent directly to the
              backend per request — never persisted on disk. Get one at{' '}
              <strong>console.anthropic.com</strong>.
            </p>
            <div className="input-row">
              <input
                type={showKey ? 'text' : 'password'}
                className="input-key"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="sk-ant-api03-..."
                spellCheck={false}
              />
              <button className="btn-sm" onClick={() => setShowKey(v => !v)}>
                {showKey ? 'Hide' : 'Show'}
              </button>
              <button className="btn-sm btn-sm-danger" onClick={handleClear}>Clear</button>
            </div>
            {hasSavedKey && !saved && (
              <span className="badge-saved">✓ Key is saved</span>
            )}
          </div>

          {/* Model */}
          <div className="field">
            <label>Code-generation model</label>
            <select
              className="select"
              value={model}
              onChange={e => setModel(e.target.value)}
            >
              {MODELS.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            <p className="field-hint">
              Architecture &amp; decomposition steps always use Opus regardless of this setting.
            </p>
          </div>

          {/* No-key fallback info */}
          <div className="field">
            <label>Running without a key?</label>
            <p className="field-hint">
              Leave the key empty and enable <strong>Mock mode</strong> on the main screen
              to run fully offline with deterministic fixtures (URL shortener scenario only).
              No API costs, no internet required.
            </p>
          </div>

        </div>

        <div className="modal-footer">
          {saved && <span className="badge-success">✓ Saved!</span>}
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave}>Save</button>
        </div>

      </div>
    </div>
  )
}
