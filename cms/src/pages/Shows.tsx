import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { get } from '../lib/api'
import type { Page, Reference, Show } from '../lib/types'
import { Empty, ErrorState, Loading, Pill } from '../components/ui'

export function Shows() {
  const [q, setQ] = useState('')
  const [section, setSection] = useState('')
  const [status, setStatus] = useState('')
  const [language, setLanguage] = useState('')
  const [page, setPage] = useState(1)

  const reference = useQuery({ queryKey: ['reference'], queryFn: () => get<Reference>('/admin/reference') })

  const params = new URLSearchParams({ page: String(page), page_size: '10' })
  if (q) params.set('q', q)
  if (section) params.set('section', section)
  if (status) params.set('status', status)
  if (language) params.set('language', language)

  const shows = useQuery({
    queryKey: ['shows', params.toString()],
    queryFn: () => get<Page<Show>>(`/admin/shows?${params}`),
    placeholderData: keepPreviousData,
  })

  function reset(fn: () => void) {
    fn()
    setPage(1)
  }

  return (
    <>
      <div className="head">
        <div>
          <h1>Shows</h1>
          <p className="sub">{shows.data ? `${shows.data.total} shows` : 'Loading…'}</p>
        </div>
        <Link to="/shows/new">
          <button className="primary">Add a show</button>
        </Link>
      </div>

      <div className="filters">
        <input
          placeholder="Search shows and episodes"
          value={q}
          onChange={(e) => reset(() => setQ(e.target.value))}
          style={{ minWidth: 260 }}
          aria-label="Search shows and episodes"
        />
        <select value={section} onChange={(e) => reset(() => setSection(e.target.value))} aria-label="Section">
          <option value="">Every section</option>
          {reference.data?.sections.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => reset(() => setStatus(e.target.value))} aria-label="Status">
          <option value="">Any status</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
        <select value={language} onChange={(e) => reset(() => setLanguage(e.target.value))} aria-label="Language">
          <option value="">Any language</option>
          {reference.data?.languages.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
        {(q || section || status || language) && (
          <button
            className="link"
            onClick={() =>
              reset(() => {
                setQ('')
                setSection('')
                setStatus('')
                setLanguage('')
              })
            }
          >
            Clear filters
          </button>
        )}
      </div>

      <div className="card">
        {shows.isPending ? (
          <Loading rows={6} />
        ) : shows.isError ? (
          <ErrorState error={shows.error} onRetry={() => shows.refetch()} />
        ) : shows.data.items.length === 0 ? (
          <Empty title="No shows match those filters">
            <div>Try a different search, or clear the filters to see everything.</div>
          </Empty>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '30%' }}>Show</th>
                  <th>Section</th>
                  <th>Category</th>
                  <th>Episodes</th>
                  <th>Languages</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shows.data.items.map((show) => (
                  <tr key={show.id}>
                    <td>
                      <Link to={`/shows/${show.id}`}>
                        <strong>{show.title}</strong>
                      </Link>
                      <div className="sub mono">{show.slug}</div>
                    </td>
                    <td>{show.section ?? <span style={{ color: 'var(--block)' }}>Not set</span>}</td>
                    <td>{show.category ?? '—'}</td>
                    <td>{show.episode_count}</td>
                    <td>
                      {show.languages.map((l) => (
                        <span key={l} className="pill lang">
                          {l}
                        </span>
                      ))}
                    </td>
                    <td>
                      <Pill value={show.status} />
                    </td>
                    <td className="row-actions">
                      <Link to={`/shows/${show.id}`}>
                        <button>Open</button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pager">
              <span className="sub">
                Page {shows.data.page} of {shows.data.pages}
              </span>
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <button disabled={page >= shows.data.pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </>
  )
}
