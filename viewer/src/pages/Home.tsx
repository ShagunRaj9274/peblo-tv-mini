import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCatalog, type Show } from '../lib/catalog'
import { Img } from '../components/Img'
import { Poster } from '../components/Poster'

export function Home() {
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: fetchCatalog })

  if (catalog.isPending)
    return (
      <div className="shell">
        <div className="pulse" style={{ aspectRatio: '16 / 7', margin: '26px 0' }} />
        <div className="strip" style={{ overflow: 'hidden' }}>
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="pulse" style={{ aspectRatio: '2 / 3' }} />
          ))}
        </div>
      </div>
    )

  if (catalog.isError)
    return (
      <div className="state">
        <h2>Peblo TV is having a nap</h2>
        <p>We couldn't load the catalogue. Check back in a moment.</p>
        <button className="btn" onClick={() => catalog.refetch()}>
          Try again
        </button>
      </div>
    )

  const bySlug = new Map(catalog.data.shows.map((s) => [s.slug, s]))
  const hero = catalog.data.hero ? bySlug.get(catalog.data.hero) : undefined

  if (catalog.data.shows.length === 0)
    return (
      <div className="state">
        <h2>Nothing to watch just yet</h2>
        <p>
          The catalogue is empty. Once someone publishes in the CMS, the shows will appear here.
        </p>
      </div>
    )

  return (
    <>
      {hero && <Hero show={hero} />}
      <div className="shell">
        {catalog.data.sections.map((section) => (
          <section className="row" key={section.name}>
            <h2>{section.name}</h2>
            <div className="strip">
              {section.shows
                .map((slug) => bySlug.get(slug))
                .filter((s): s is Show => Boolean(s))
                .map((show) => (
                  <Poster key={show.slug} show={show} />
                ))}
            </div>
          </section>
        ))}
      </div>
    </>
  )
}

/** The hero uses the banner (16:9) — the only place that artwork is used. */
function Hero({ show }: { show: Show }) {
  return (
    <header className="hero">
      <div className="frame">
        <Img src={show.artwork.banner?.url} alt={show.title} seed={show.slug} eager />
        <div className="scrim" />
        <div className="lamp" />
        <div className="words">
          <p className="meta">
            {show.category} · {show.season_count} season{show.season_count === 1 ? '' : 's'} ·{' '}
            {show.languages.map((l) => l.label).join(', ')}
          </p>
          <h1>{show.title}</h1>
          <p>{show.synopsis}</p>
          <div style={{ display: 'flex', gap: 10 }}>
            <Link className="btn" to={`/show/${show.slug}`}>
              Watch
            </Link>
            {show.trailers.length > 0 && (
              <Link className="btn ghost" to={`/show/${show.slug}#trailers`}>
                Trailer
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
