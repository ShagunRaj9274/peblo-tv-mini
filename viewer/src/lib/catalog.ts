export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export type Art = { url: string; width: number; height: number } | null
export type Language = { code: string; label: string }
export type Entry = {
  content_group: string
  episode_number: number
  title: string
  synopsis: string
  duration_seconds: number | null
  release_date: string | null
  thumbnail: Art
  languages: Language[]
  variants: Record<string, { episode_id: string }>
}
export type Season = { season_number: number; title: string; episodes: Entry[] }
export type Show = {
  slug: string
  title: string
  synopsis: string
  category: string | null
  section: string
  featured: boolean
  artwork: { poster: Art; banner: Art }
  languages: Language[]
  season_count: number
  episode_count: number
  seasons: Season[]
  trailers: Entry[]
}
export type Catalog = {
  schema_version: number
  run_id?: string
  generated_at?: string
  hero: string | null
  sections: { name: string; shows: string[] }[]
  shows: Show[]
  counts: { shows: number; sections: number; episodes: number }
  message?: string
}

/** The viewer only ever calls these three read-only endpoints. It has no token,
 *  and nothing under /admin is reachable from this app. */
export async function fetchCatalog(): Promise<Catalog> {
  const res = await fetch(`${API_BASE}/catalog`)
  if (!res.ok) throw new Error('The catalogue is not available right now.')
  return res.json()
}

export async function fetchShow(slug: string): Promise<Show> {
  const res = await fetch(`${API_BASE}/catalog/shows/${slug}`)
  if (res.status === 404) throw new Error('That show is not in the catalogue.')
  if (!res.ok) throw new Error('That show could not be loaded.')
  return res.json()
}

export async function searchCatalog(params: {
  q?: string
  category?: string
  language?: string
  section?: string
}): Promise<{ count: number; results: Show[] }> {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => v && search.set(k, v))
  const res = await fetch(`${API_BASE}/catalog/search?${search}`)
  if (!res.ok) throw new Error('Search is unavailable right now.')
  return res.json()
}

export function runtime(seconds: number | null) {
  if (!seconds) return ''
  const m = Math.round(seconds / 60)
  return m < 1 ? `${seconds} sec` : `${m} min`
}
