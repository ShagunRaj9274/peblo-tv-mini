import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, get, post, session } from '../lib/api'
import type { PublishRun, ValidationReport } from '../lib/types'
import { Empty, ErrorState, Loading, Pill, when } from '../components/ui'

type DryRun = {
  diff: {
    added: { slug: string; title: string }[]
    removed: { slug: string; title: string }[]
    changed: { slug: string; title: string }[]
    counts: Record<string, number>
    would_change: boolean
  }
}

export function Publish() {
  const qc = useQueryClient()
  const isAdmin = session.get()?.role === 'admin'
  const [result, setResult] = useState<string | null>(null)
  const [dry, setDry] = useState<DryRun['diff'] | null>(null)

  const report = useQuery({
    queryKey: ['report'],
    queryFn: () => get<ValidationReport>('/admin/validation-report'),
  })
  const runs = useQuery({ queryKey: ['runs'], queryFn: () => get<PublishRun[]>('/admin/catalog/runs') })

  const publish = useMutation({
    mutationFn: () => post<PublishRun>('/admin/catalog/publish'),
    onSuccess: (run) => {
      setResult(
        run.status === 'no_changes'
          ? 'Nothing had changed since the last publish, so the live catalogue was left alone.'
          : `Published. ${run.counts.shows} shows and ${run.counts.episodes} episodes are now live.`,
      )
      qc.invalidateQueries()
    },
  })

  const dryRun = useMutation({
    mutationFn: () => post<DryRun>('/admin/catalog/dry-run'),
    onSuccess: (data) => setDry(data.diff),
  })

  const rollback = useMutation({
    mutationFn: (runId: string) => post<PublishRun>(`/admin/catalog/rollback/${runId}`),
    onSuccess: () => {
      setResult('Rolled back. The viewer is now serving the catalogue from that run.')
      qc.invalidateQueries()
    },
  })

  return (
    <>
      <div className="head">
        <div>
          <h1>Publish</h1>
          <p className="sub">Building the catalogue is what makes your changes visible in Peblo TV.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => dryRun.mutate()} disabled={dryRun.isPending}>
            {dryRun.isPending ? 'Checking…' : 'Preview changes'}
          </button>
          <button
            className="primary"
            onClick={() => publish.mutate()}
            disabled={!isAdmin || !report.data?.can_publish || publish.isPending}
            title={
              !isAdmin
                ? 'Only an admin can publish.'
                : !report.data?.can_publish
                  ? 'Fix the problems listed below first.'
                  : undefined
            }
          >
            {publish.isPending ? 'Publishing…' : 'Publish catalogue'}
          </button>
        </div>
      </div>

      {!isAdmin && (
        <div className="banner warn">
          You are signed in as an editor. You can see and fix everything here, but only an admin can press
          Publish.
        </div>
      )}
      {publish.isError && (
        <div className="banner error">{(publish.error as ApiError).message}</div>
      )}
      {result && <div className="banner ok">{result}</div>}

      {dry && (
        <div className="card">
          <div className="title-row">
            <h2 style={{ margin: 0 }}>What would change</h2>
            <button className="link" onClick={() => setDry(null)}>
              Hide
            </button>
          </div>
          <div className="body">
            {!dry.would_change ? (
              <p className="sub">Nothing. The live catalogue already matches what is in the CMS.</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {dry.added.map((s) => (
                  <li key={s.slug}>
                    <strong>Appears:</strong> {s.title}
                  </li>
                ))}
                {dry.changed.map((s) => (
                  <li key={s.slug}>
                    <strong>Updated:</strong> {s.title}
                  </li>
                ))}
                {dry.removed.map((s) => (
                  <li key={s.slug}>
                    <strong>Disappears:</strong> {s.title}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="card">
        <div className="title-row">
          <h2 style={{ margin: 0 }}>Before you publish</h2>
          {report.data && (
            <span className="sub">
              {report.data.blocking_count} blocking · {report.data.warning_count} to look at
            </span>
          )}
        </div>
        {report.isPending ? (
          <Loading rows={5} />
        ) : report.isError ? (
          <ErrorState error={report.error} onRetry={() => report.refetch()} />
        ) : (
          <div className="body">
            <div className={`banner ${report.data.can_publish ? 'ok' : 'error'}`}>{report.data.summary}</div>
            {report.data.groups.length === 0 ? (
              <Empty title="Nothing needs attention">
                <div>Every published show and episode has what it needs.</div>
              </Empty>
            ) : (
              report.data.groups.map((group) => (
                <div className="issue-group" key={`${group.target_type}:${group.target_id}`}>
                  <header>
                    <strong>{group.title}</strong>
                    {group.target_type === 'show' ? (
                      <Link to={`/shows/${group.target_id}`}>
                        <button>Open show</button>
                      </Link>
                    ) : (
                      <span className="sub">{group.target_type.replace('_', ' ')}</span>
                    )}
                  </header>
                  {group.issues.map((issue, i) => (
                    <div className={`issue ${issue.severity}`} key={i}>
                      <div>{issue.problem}</div>
                      <div className="fix">{issue.fix}</div>
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <div className="card">
        <div className="title-row">
          <h2 style={{ margin: 0 }}>Publish history</h2>
        </div>
        {runs.isPending ? (
          <Loading rows={3} />
        ) : runs.isError ? (
          <ErrorState error={runs.error} onRetry={() => runs.refetch()} />
        ) : runs.data.length === 0 ? (
          <Empty title="Nothing has been published yet">
            <div>The first publish will appear here with who ran it and what it contained.</div>
          </Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>Outcome</th>
                <th>Contents</th>
                <th>Catalogue file</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.data.map((run) => (
                <tr key={run.id}>
                  <td>{when(run.started_at)}</td>
                  <td>{run.actor_email ?? 'system'}</td>
                  <td>
                    <Pill value={run.status} />
                    {run.error && <div className="sub">{run.error}</div>}
                  </td>
                  <td>
                    {run.counts?.shows != null
                      ? `${run.counts.shows} shows · ${run.counts.episodes} episodes`
                      : '—'}
                  </td>
                  <td className="mono">{run.catalog_key?.split('/').pop() ?? '—'}</td>
                  <td className="row-actions">
                    {isAdmin && run.catalog_key && run.status === 'success' && (
                      <button
                        onClick={() => {
                          if (confirm('Point Peblo TV back at this catalogue?')) rollback.mutate(run.id)
                        }}
                      >
                        Roll back to this
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
