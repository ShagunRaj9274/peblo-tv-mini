import { Link } from 'react-router-dom'
import type { Show } from '../lib/catalog'
import { Img } from './Img'

/** Rows use the poster (2:3) — that is the surface it was cut for. */
export function Poster({ show }: { show: Show }) {
  return (
    <Link className="poster" to={`/show/${show.slug}`}>
      <figure>
        <div className="art">
          <Img src={show.artwork.poster?.url} alt={show.title} seed={show.slug} />
        </div>
        <figcaption>
          <h3>{show.title}</h3>
          <p className="sub">
            {show.category} · {show.season_count} season{show.season_count === 1 ? '' : 's'}
          </p>
        </figcaption>
      </figure>
    </Link>
  )
}
