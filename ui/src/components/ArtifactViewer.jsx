import { useState, useEffect } from 'react'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import plaintext from 'highlight.js/lib/languages/plaintext'
import 'highlight.js/styles/github-dark.css'

hljs.registerLanguage('python', python)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('plaintext', plaintext)

const EXT_LANG = {
  py: 'python', json: 'json', md: 'markdown', txt: 'plaintext', toml: 'plaintext',
}

function detectLang(path) {
  const ext = path.split('.').pop().toLowerCase()
  return EXT_LANG[ext] || 'plaintext'
}

function highlight(code, path) {
  const lang = detectLang(path)
  try {
    return hljs.highlight(code, { language: lang }).value
  } catch {
    return code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
}

export default function ArtifactViewer({ refreshKey }) {
  const [files, setFiles]       = useState([])
  const [selected, setSelected] = useState(null)
  const [content, setContent]   = useState(null)
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    fetch('/api/artifacts')
      .then(r => r.json())
      .then(data => {
        setFiles(data)
        // Auto-select first file when artifacts refresh after a run
        if (data.length > 0 && refreshKey > 0) {
          selectFile(data[0])
        }
      })
      .catch(() => {})
  }, [refreshKey])

  const selectFile = async (path) => {
    setSelected(path)
    setLoading(true)
    try {
      const r = await fetch(`/api/artifacts/${path}`)
      const data = await r.json()
      setContent(data.content)
    } catch {
      setContent('(could not load file)')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="artifact-viewer">
      {/* File tree */}
      <div className="artifact-tree">
        <div className="artifact-tree-header">
          Generated files {files.length > 0 && `(${files.length})`}
        </div>
        {files.length === 0 ? (
          <div style={{ padding: '8px 14px', fontSize: 12, color: 'var(--text-dim)' }}>
            No artifacts yet.
          </div>
        ) : (
          files.map(f => (
            <button
              key={f}
              className={`artifact-file ${selected === f ? 'selected' : ''}`}
              onClick={() => selectFile(f)}
              title={f}
            >
              {fileIcon(f)} {f}
            </button>
          ))
        )}
      </div>

      {/* Content */}
      <div className="artifact-content" style={{ display: 'flex', flexDirection: 'column' }}>
        {selected ? (
          <>
            <div className="artifact-content-header">{selected}</div>
            {loading ? (
              <div style={{ padding: 16, color: 'var(--text-dim)' }}>Loading…</div>
            ) : (
              <pre
                className="artifact-code"
                dangerouslySetInnerHTML={{ __html: highlight(content ?? '', selected) }}
              />
            )}
          </>
        ) : (
          <div className="artifact-empty">
            <span className="artifact-empty-icon">📂</span>
            <span>Select a file to view its content</span>
          </div>
        )}
      </div>
    </div>
  )
}

function fileIcon(path) {
  if (path.endsWith('.py'))   return '🐍'
  if (path.endsWith('.md'))   return '📝'
  if (path.endsWith('.json')) return '📋'
  if (path.endsWith('.txt'))  return '📄'
  return '📄'
}
