import { useEffect, useRef } from 'react'

export default function LogStream({ logs, status, running }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const statusBanner = () => {
    if (!status) return null
    if (status.type === 'done') {
      const tests = status.tests_passed === true
        ? ' · tests ✓'
        : status.tests_passed === false
          ? ' · tests ✗'
          : ''
      return (
        <div className="status-banner status-done">
          ✓ Run {status.run_id} complete — {status.artifacts} artifact(s){tests}
        </div>
      )
    }
    if (status.type === 'halted') {
      return (
        <div className="status-banner status-halted">
          ⏸ Halted for human review — {status.reason}
        </div>
      )
    }
    return (
      <div className="status-banner status-error">
        ✗ {status.msg}
      </div>
    )
  }

  return (
    <div className="log-stream">
      <div className="log-header">
        <span>Live logs</span>
        {running && <span style={{ color: 'var(--blue)' }}>● running…</span>}
      </div>

      <div className="log-body">
        {logs.length === 0 && !running && (
          <div className="log-empty">Logs will appear here when a run starts.</div>
        )}
        {logs.map((entry, i) => (
          <div key={i} className="log-entry">
            <span className={`log-level ${entry.level}`}>{entry.level}</span>
            <span className="log-msg">{entry.msg}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {statusBanner()}
    </div>
  )
}
