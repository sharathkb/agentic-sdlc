import { useState } from 'react'

const PROVIDERS = [
  {
    id: 'anthropic',
    label: 'Anthropic (Claude)',
    hint: 'Get a key at console.anthropic.com — pay-as-you-go from $5',
    placeholder: 'sk-ant-api03-...',
    keyStorageKey: 'anthropic_api_key',
    needsKey: true,
    models: [
      { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6 (recommended)' },
      { id: 'claude-opus-4-8',   label: 'Claude Opus 4.8 (smartest, slower)' },
      { id: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (fastest, cheapest)' },
    ],
  },
  {
    id: 'groq',
    label: 'Groq (free tier)',
    hint: 'Free tier at console.groq.com — very fast inference. Get a key there.',
    placeholder: 'gsk_...',
    keyStorageKey: 'groq_api_key',
    needsKey: true,
    models: [
      { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B (recommended)' },
      { id: 'llama-3.1-8b-instant',    label: 'Llama 3.1 8B (fastest)' },
      { id: 'mixtral-8x7b-32768',      label: 'Mixtral 8x7B' },
      { id: 'gemma2-9b-it',            label: 'Gemma 2 9B' },
    ],
  },
  {
    id: 'gemini',
    label: 'Google Gemini (free tier)',
    hint: 'Free tier at aistudio.google.com — generous daily limits. Get a key there.',
    placeholder: 'AIza...',
    keyStorageKey: 'gemini_api_key',
    needsKey: true,
    models: [
      { id: 'gemini-2.0-flash',   label: 'Gemini 2.0 Flash (recommended)' },
      { id: 'gemini-1.5-flash',   label: 'Gemini 1.5 Flash' },
      { id: 'gemini-1.5-pro',     label: 'Gemini 1.5 Pro' },
    ],
  },
  {
    id: 'openai',
    label: 'OpenAI (GPT)',
    hint: 'Paid API at platform.openai.com. GPT-4o-mini is cheapest.',
    placeholder: 'sk-...',
    keyStorageKey: 'openai_api_key',
    needsKey: true,
    models: [
      { id: 'gpt-4o-mini', label: 'GPT-4o Mini (cheapest)' },
      { id: 'gpt-4o',      label: 'GPT-4o' },
      { id: 'o3-mini',     label: 'o3-mini' },
    ],
  },
  {
    id: 'ollama',
    label: 'Ollama (local, free)',
    hint: 'Runs models on your machine — no API key needed. Install at ollama.com then run: ollama pull llama3',
    placeholder: '',
    keyStorageKey: null,
    needsKey: false,
    models: [
      { id: 'llama3',      label: 'Llama 3 8B' },
      { id: 'llama3:70b',  label: 'Llama 3 70B (needs ~40GB RAM)' },
      { id: 'mistral',     label: 'Mistral 7B' },
      { id: 'codellama',   label: 'Code Llama' },
      { id: 'phi3',        label: 'Phi-3 Mini' },
    ],
  },
  {
    id: 'custom',
    label: 'Custom (OpenAI-compatible)',
    hint: 'Any provider that exposes the OpenAI /chat/completions API.',
    placeholder: 'sk-...',
    keyStorageKey: 'custom_api_key',
    needsKey: true,
    models: [],
  },
]

function lsGet(key, fallback = '') {
  return localStorage.getItem(key) || fallback
}

export default function Settings({ onClose }) {
  const [provider, setProvider]   = useState(lsGet('provider', 'anthropic'))
  const [showKey, setShowKey]     = useState(false)
  const [saved, setSaved]         = useState(false)
  const [customBaseUrl, setCustomBaseUrl] = useState(lsGet('custom_base_url', 'https://api.openai.com/v1'))
  const [customModel, setCustomModel]     = useState(lsGet('custom_model', 'gpt-4o-mini'))

  const pDef = PROVIDERS.find(p => p.id === provider) || PROVIDERS[0]

  const [apiKey, setApiKey] = useState(
    pDef.keyStorageKey ? lsGet(pDef.keyStorageKey) : ''
  )
  const [model, setModel] = useState(
    lsGet(`${provider}_model`, pDef.models[0]?.id || '')
  )

  const switchProvider = (id) => {
    setProvider(id)
    const def = PROVIDERS.find(p => p.id === id) || PROVIDERS[0]
    setApiKey(def.keyStorageKey ? lsGet(def.keyStorageKey) : '')
    setModel(lsGet(`${id}_model`, def.models[0]?.id || ''))
    setShowKey(false)
  }

  const handleSave = () => {
    localStorage.setItem('provider', provider)
    if (pDef.keyStorageKey) {
      if (apiKey.trim()) {
        localStorage.setItem(pDef.keyStorageKey, apiKey.trim())
      } else {
        localStorage.removeItem(pDef.keyStorageKey)
      }
    }
    localStorage.setItem(`${provider}_model`, model)
    if (provider === 'custom') {
      localStorage.setItem('custom_base_url', customBaseUrl.trim())
      localStorage.setItem('custom_model', customModel.trim())
    }
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const handleClear = () => {
    setApiKey('')
    if (pDef.keyStorageKey) localStorage.removeItem(pDef.keyStorageKey)
  }

  const hasSavedKey = pDef.keyStorageKey
    ? Boolean(localStorage.getItem(pDef.keyStorageKey))
    : true  // ollama / keyless providers are always "ready"

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>

        <div className="modal-header">
          <h2>⚙ Settings</h2>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">

          {/* Provider selector */}
          <div className="field">
            <label>LLM Provider</label>
            <select
              className="select"
              value={provider}
              onChange={e => switchProvider(e.target.value)}
            >
              {PROVIDERS.map(p => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <p className="field-hint">{pDef.hint}</p>
          </div>

          {/* API key (hidden for Ollama) */}
          {pDef.needsKey && (
            <div className="field">
              <label>API Key</label>
              <div className="input-row">
                <input
                  type={showKey ? 'text' : 'password'}
                  className="input-key"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder={pDef.placeholder}
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
              <p className="field-hint">
                Stored only in your browser (<code>localStorage</code>). Never persisted on the server.
              </p>
            </div>
          )}

          {/* Model selector (hidden for custom, which uses free-text) */}
          {pDef.models.length > 0 && (
            <div className="field">
              <label>Model</label>
              <select
                className="select"
                value={model}
                onChange={e => setModel(e.target.value)}
              >
                {pDef.models.map(m => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
            </div>
          )}

          {/* Custom provider extra fields */}
          {provider === 'custom' && (
            <>
              <div className="field">
                <label>Base URL</label>
                <input
                  type="text"
                  className="input-key"
                  value={customBaseUrl}
                  onChange={e => setCustomBaseUrl(e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  spellCheck={false}
                />
              </div>
              <div className="field">
                <label>Model name</label>
                <input
                  type="text"
                  className="input-key"
                  value={customModel}
                  onChange={e => setCustomModel(e.target.value)}
                  placeholder="gpt-4o-mini"
                  spellCheck={false}
                />
              </div>
            </>
          )}

          {/* Mock mode info */}
          <div className="field">
            <label>Running without a key?</label>
            <p className="field-hint">
              Enable <strong>Mock mode</strong> on the main screen to run fully offline
              with deterministic fixtures — no API costs, no internet. Or use{' '}
              <strong>Groq</strong> or <strong>Gemini</strong> for a free live tier.
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
