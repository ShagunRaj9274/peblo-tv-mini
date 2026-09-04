export type Artwork = {
  id: string
  kind: 'poster' | 'banner' | 'thumbnail'
  url: string
  width: number
  height: number
  bytes: number
  mime_type: string
}
export type Season = { id: string; season_number: number; title: string }
export type Show = {
  id: string
  slug: string
  title: string
  synopsis: string
  category: string | null
  section: string | null
  status: 'draft' | 'published' | 'archived'
  featured: boolean
  sort_weight: number
  updated_at: string
  seasons: Season[]
  artwork: Artwork[]
  episode_count: number
  languages: string[]
}
export type Episode = {
  id: string
  season_id: string
  episode_number: number
  title: string
  synopsis: string
  duration_seconds: number | null
  language: string
  content_group: string | null
  status: 'draft' | 'published' | 'archived'
  release_date: string | null
  artwork: Artwork[]
}
export type Page<T> = { items: T[]; total: number; page: number; page_size: number; pages: number }
export type Reference = {
  sections: string[]
  categories: string[]
  languages: string[]
  artwork: Record<string, { aspect_ratio: string; target_width: number; target_height: number; max_bytes: number }>
}
export type Issue = {
  severity: 'blocking' | 'warning'
  code: string
  problem: string
  fix: string
  target: { type: string; id: string; title: string; slug?: string }
}
export type ValidationReport = {
  can_publish: boolean
  blocking_count: number
  warning_count: number
  summary: string
  groups: { target_type: string; target_id: string; title: string; slug: string | null; issues: Issue[] }[]
}
export type PublishRun = {
  id: string
  actor_email: string | null
  started_at: string
  finished_at: string | null
  status: 'running' | 'success' | 'no_changes' | 'failed' | 'blocked' | 'dry_run'
  counts: Record<string, number>
  catalog_key: string | null
  checksum: string | null
  error: string | null
}
