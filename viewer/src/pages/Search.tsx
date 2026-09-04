import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchCatalog, searchCatalog } from '../lib/catalog'
import { Poster } from '../components/Poster'

export function Search() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const language = params.get('language') ?? ''

  // Filter options come from what is actually in the published catalogue, so we
  // never offer a filter that returns nothing.
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: fetchCatalog })
  const categories = [
    ...new Set((catalog.data?.shows ?? []).map((s) => s.category).filter(Boolean)),
  ] as string[]
  const languages = new Map(
    (catalog.data?.shows ?? []).flatMap((s) => s.languages).map((l) => [l.code, l.label]),
  )

  const results = useQuery({
    queryKey: ['search', q, category, language],
    queryFn: () => searchCatalog({ q, category, language }),
  })

  function set(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  return (
    <div className="shell">
      <h1 style={{ fontFamily: 'var(--display)', fontSize: 32, margin: '26px 0 4px' }}>
        {q ? `Results for “${q}”` : 'Browse everything'}
      </h1>

      <div className="filters">
        <select value={category} onChange={(e) => set('category', e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select value={language} onChange={(e) => set('language', e.target.value)} aria-label="Language">
          <option value="">All languages</option>
          {[...languages].map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
        {(q || category || language) && (
          <button className="btn ghost" onClick={() => setParams(new URLSearchParams())}>
            Clear
          </button>
        )}
      </div>

      {results.isPending ? (
        <div className="grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="pulse" style={{ aspectRatio: '2 / 3' }} />
          ))}
        </div>
      ) : results.isError ? (
        <div className="state">
          <h2>Search is resting</h2>
          <p>We couldn't run that search. Try again in a moment.</p>
        </div>
      ) : results.data.count === 0 ? (
        <div className="state">
          <h2>Nothing matched</h2>
          <p>
            {q
              ? `We don't have anything called “${q}” yet.`
              : 'No shows match those filters.'}{' '}
            Try a different word, or clear the filters.
          </p>
          <button className="btn" onClick={() => setParams(new URLSearchParams())}>
            Show everything
          </button>
        </div>
      ) : (
        <>
          <p className="count">
            {results.data.count} show{results.data.count === 1 ? '' : 's'}
          </p>
          <div className="grid">
            {results.data.results.map((show) => (
              <Poster key={show.slug} show={show} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
