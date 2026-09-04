import type { ReactNode } from 'react'
import { ApiError } from '../lib/api'

export function Loading({ rows = 4 }: { rows?: number }) {
  return (
    <div className="body" aria-live="polite" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ marginBottom: 10, width: `${100 - i * 9}%` }} />
      ))}
      <span style={{ position: 'absolute', left: -9999 }}>Loading</span>
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <strong>{title}</strong>
      {children}
    </div>
  )
}

/** One place decides what a failure looks like, including the 403 case, so
 *  every screen handles permission-denied the same way. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const err = error as ApiError
  const forbidden = err?.status === 403
  return (
    <div className="state">
      <strong>{forbidden ? 'You do not have access to this' : "That didn't load"}</strong>
      <div>{err?.message ?? 'Unknown error.'}</div>
      {forbidden && <div className="hint">Ask an admin to change your role, or sign in as one.</div>}
      {onRetry && !forbidden && (
        <button onClick={onRetry}>Try again</button>
      )}
    </div>
  )
}

export function Pill({ value }: { value: string }) {
  return <span className={`pill ${value}`}>{value.replace('_', ' ')}</span>
}

export function duration(seconds: number | null) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${String(s).padStart(2, '0')}s`
}

export function when(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
