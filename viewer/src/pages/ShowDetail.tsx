import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchShow, runtime, type Entry } from '../lib/catalog'
import { Img } from '../components/Img'

export function ShowDetail() {
  const { slug } = useParams()
  const show = useQuery({ queryKey: ['show', slug], queryFn: () => fetchShow(slug!) })
  const [season, setSeason] = useState(0)

  if (show.isPending)
    return (
      <div className="shell">
        <div className="detail-head">
          <div className="pulse" style={{ aspectRatio: '2 / 3' }} />
          <div>
            <div className="pulse" style={{ height: 42, marginBottom: 14 }} />
            <div className="pulse" style={{ height: 68 }} />
          </div>
        </div>
      </div>
    )

  if (show.isError)
    return (
      <div className="state">
        <h2>We can't find that show</h2>
        <p>It may not be published yet, or the link may be out of date.</p>
        <Link className="btn" to="/">
          Back to Peblo TV
        </Link>
      </div>
    )

  const data = show.data
  // Season 0 is trailers by convention, and the catalogue already keeps it out
  // of `seasons`. It gets its own strip below instead of a season tab.
  const current = data.seasons[Math.min(season, data.seasons.length - 1)]

  return (
    <div className="shell">
      <div className="detail-head">
        <div className="art">
          <Img src={data.artwork.poster?.url} alt={data.title} seed={data.slug} eager />
        </div>
        <div>
          <h1>{data.title}</h1>
          <p>{data.synopsis}</p>
          <div className="chips">
            {data.category && <span className="chip">{data.category}</span>}
            <span className="chip">
              {data.season_count} season{data.season_count === 1 ? '' : 's'}
            </span>
            <span className="chip">{data.episode_count} episodes</span>
            {data.languages.map((l) => (
              <span className="chip lang" key={l.code}>
                {l.label}
              </span>
            ))}
          </div>
        </div>
      </div>

      {data.trailers.length > 0 && (
        <section className="row" id="trailers">
          <h2>Trailer{data.trailers.length === 1 ? '' : 's'}</h2>
          <div className="strip" style={{ gridAutoColumns: '260px' }}>
            {data.trailers.map((t) => (
              <article key={t.content_group}>
                <div className="art" style={{ aspectRatio: '16 / 9', borderRadius: 12, overflow: 'hidden' }}>
                  <Img src={t.thumbnail?.url} alt={t.title} seed={t.content_group} />
                </div>
                <h3 style={{ fontSize: 14, margin: '8px 0 2px' }}>{t.title}</h3>
                <span className="chip trailer">{runtime(t.duration_seconds)}</span>
              </article>
            ))}
          </div>
        </section>
      )}

      {data.seasons.length > 1 && (
        <div className="season-tabs">
          {data.seasons.map((s, i) => (
            <button key={s.season_number} aria-pressed={i === season} onClick={() => setSeason(i)}>
              {s.title}
            </button>
          ))}
        </div>
      )}

      <h2 style={{ fontFamily: 'var(--display)', fontWeight: 500, fontSize: 21, margin: '28px 0 12px' }}>
        {data.seasons.length > 1 ? current.title : 'Episodes'}
      </h2>
      <div>
        {current.episodes.map((ep) => (
          <EpisodeRow key={ep.content_group} entry={ep} />
        ))}
      </div>
    </div>
  )
}

/** A grouped episode is one row with a language picker, not one row per
 *  language. `languages` comes straight from the catalogue's content_group
 *  collapsing. */
function EpisodeRow({ entry }: { entry: Entry }) {
  const [language, setLanguage] = useState(entry.languages[0]?.code)
  return (
    <article className="episode">
      <div className="art">
        <Img src={entry.thumbnail?.url} alt={entry.title} seed={entry.content_group} />
      </div>
      <div>
        <span className="runtime">
          Episode {entry.episode_number}
          {entry.duration_seconds ? ` · ${runtime(entry.duration_seconds)}` : ''}
        </span>
        <h3>{entry.title}</h3>
        <p>{entry.synopsis}</p>
        <div className="chips" style={{ margin: 0 }}>
          {entry.languages.length > 1 ? (
            entry.languages.map((l) => (
              <button
                key={l.code}
                className="chip lang"
                style={{
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  outline: l.code === language ? '2px solid var(--mint)' : 'none',
                }}
                onClick={() => setLanguage(l.code)}
              >
                {l.label}
              </button>
            ))
          ) : (
            <span className="chip lang">{entry.languages[0]?.label}</span>
          )}
        </div>
      </div>
    </article>
  )
}
