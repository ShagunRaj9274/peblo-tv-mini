import { useState } from 'react'

/** Images arrive over whatever connection a family has. Three things keep this
 *  pleasant: the box reserves its aspect ratio so nothing jumps, the placeholder
 *  is a calm colour derived from the title (so a slow row still looks composed
 *  rather than grey), and the real image fades in when it decodes. Offscreen
 *  rows load lazily. */
function tint(seed: string) {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 360
  return `hsl(${h} 34% 22%)`
}

export function Img({
  src,
  alt,
  seed,
  eager = false,
}: {
  src?: string | null
  alt: string
  seed: string
  eager?: boolean
}) {
  const [ready, setReady] = useState(false)
  return (
    <div className="img">
      <div className="tint" style={{ background: tint(seed) }} aria-hidden="true" />
      {src && (
        <img
          src={src}
          alt={alt}
          className={ready ? 'ready' : ''}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          onLoad={() => setReady(true)}
          onError={() => setReady(false)}
        />
      )}
    </div>
  )
}
