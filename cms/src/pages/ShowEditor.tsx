import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, del, get, patch, post } from '../lib/api'
import type { Episode, Reference, Show } from '../lib/types'
import { ArtworkSlot } from '../components/ArtworkSlot'
import { Empty, ErrorState, Loading, Pill, duration } from '../components/ui'

const BLANK = {
  slug: '',
  title: '',
  synopsis: '',
  category: '',
  section: '',
  status: 'draft' as const,
  featured: false,
  sort_weight: 100,
}

export function ShowEditor() {
  const { showId } = useParams()
  const isNew = showId === 'new'
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [form, setForm] = useState<typeof BLANK>(BLANK)
  const [saved, setSaved] = useState(false)

  const reference = useQuery({ queryKey: ['reference'], queryFn: () => get<Reference>('/admin/reference') })
  const show = useQuery({
    queryKey: ['show', showId],
    queryFn: () => get<Show>(`/admin/shows/${showId}`),
    enabled: !isNew,
  })
  const episodes = useQuery({
    queryKey: ['episodes', showId],
    queryFn: () => get<Episode[]>(`/admin/shows/${showId}/episodes`),
    enabled: !isNew,
  })

  useEffect(() => {
    if (show.data)
      setForm({
        slug: show.data.slug,
        title: show.data.title,
        synopsis: show.data.synopsis ?? '',
        category: show.data.category ?? '',
        section: show.data.section ?? '',
        status: show.data.status as 'draft',
        featured: show.data.featured,
        sort_weight: show.data.sort_weight,
      })
  }, [show.data])

  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form,
        category: form.category || null,
        section: form.section || null,
      }
      return isNew ? post<Show>('/admin/shows', body) : patch<Show>(`/admin/shows/${showId}`, body)
    },
    onSuccess: (result) => {
      setSaved(true)
      qc.invalidateQueries()
      if (isNew) navigate(`/shows/${result.id}`)
    },
  })

  const remove = useMutation({
    mutationFn: () => del(`/admin/shows/${showId}`),
    onSuccess: () => {
      qc.invalidateQueries()
      navigate('/shows')
    },
  })

  if (!isNew && show.isPending) return <Loading rows={8} />
  if (!isNew && show.isError) return <ErrorState error={show.error} onRetry={() => show.refetch()} />

  const artOf = (kind: string) => show.data?.artwork.find((a) => a.kind === kind)
  const specs = reference.data?.artwork

  return (
    <>
      <div className="head">
        <div>
          <p className="sub">
            <Link to="/shows">Shows</Link> / {isNew ? 'New show' : show.data?.title}
          </p>
          <h1>{isNew ? 'Add a show' : show.data?.title}</h1>
        </div>
        {!isNew && (
          <button
            className="danger"
            onClick={() => {
              if (confirm(`Delete “${show.data?.title}” and all its episodes? This can't be undone.`))
                remove.mutate()
            }}
          >
            Delete show
          </button>
        )}
      </div>

      {save.isError && <div className="banner error">{(save.error as ApiError).message}</div>}
      {saved && !save.isError && <div className="banner ok">Saved.</div>}

      <div className="card">
        <div className="title-row">
          <h2 style={{ margin: 0 }}>Details</h2>
          {!isNew && <Pill value={form.status} />}
        </div>
        <div className="body">
          <div className="grid2">
            <div className="field">
              <label htmlFor="title">Title</label>
              <input
                id="title"
                style={{ width: '100%' }}
                value={form.title}
                onChange={(e) => {
                  const title = e.target.value
                  setForm((f) => ({
                    ...f,
                    title,
                    slug: isNew
                      ? title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
                      : f.slug,
                  }))
                }}
              />
            </div>
            <div className="field">
              <label htmlFor="slug">URL slug</label>
              <input
                id="slug"
                style={{ width: '100%' }}
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="synopsis">Synopsis</label>
            <textarea
              id="synopsis"
              value={form.synopsis}
              onChange={(e) => setForm((f) => ({ ...f, synopsis: e.target.value }))}
            />
          </div>
          <div className="grid3">
            <div className="field">
              <label htmlFor="section">Section — the row this appears in</label>
              <select
                id="section"
                style={{ width: '100%' }}
                value={form.section}
                onChange={(e) => setForm((f) => ({ ...f, section: e.target.value }))}
              >
                <option value="">Not set</option>
                {reference.data?.sections.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="category">Category</label>
              <select
                id="category"
                style={{ width: '100%' }}
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              >
                <option value="">Not set</option>
                {reference.data?.categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="status">Status</label>
              <select
                id="status"
                style={{ width: '100%' }}
                value={form.status}
                onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as 'draft' }))}
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, color: 'var(--ink)' }}>
            <input
              type="checkbox"
              checked={form.featured}
              onChange={(e) => setForm((f) => ({ ...f, featured: e.target.checked }))}
            />
            Feature this show in the hero on the Peblo TV home screen
          </label>
          <div style={{ marginTop: 14 }}>
            <button className="primary" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? 'Saving…' : isNew ? 'Create show' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>

      {isNew ? (
        <div className="card">
          <div className="body">
            <p className="sub">Artwork and episodes can be added once the show is created.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="card">
            <div className="title-row">
              <h2 style={{ margin: 0 }}>Artwork</h2>
              <span className="sub">Images are checked when you upload. Nothing is saved until it passes.</span>
            </div>
            <div className="body">
              {specs && (
                <div className="slots">
                  <ArtworkSlot
                    ownerType="show"
                    ownerId={showId!}
                    kind="poster"
                    label="Poster"
                    usedFor="browse rows"
                    spec={specs.poster}
                    current={artOf('poster')}
                  />
                  <ArtworkSlot
                    ownerType="show"
                    ownerId={showId!}
                    kind="banner"
                    label="Banner"
                    usedFor="the home hero"
                    spec={specs.banner}
                    current={artOf('banner')}
                  />
                  <div className="slot">
                    <h3>Thumbnail</h3>
                    <p className="spec">
                      {specs.thumbnail.target_width}×{specs.thumbnail.target_height} ·{' '}
                      {specs.thumbnail.aspect_ratio} · episode lists
                    </p>
                    <div className="preview">
                      <span className="empty">
                        Thumbnails belong to episodes, not the show. Open an episode below to upload one.
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <EpisodeTable show={show.data!} episodes={episodes} />
        </>
      )}
    </>
  )
}

function EpisodeTable({
  show,
  episodes,
}: {
  show: Show
  episodes: ReturnType<typeof useQuery<Episode[]>>
}) {
  const qc = useQueryClient()
  const [openId, setOpenId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  if (episodes.isPending) return <Loading rows={5} />
  if (episodes.isError) return <ErrorState error={episodes.error} onRetry={() => episodes.refetch()} />

  const seasonOf = (id: string) => show.seasons.find((s) => s.id === id)
  const rows = [...(episodes.data ?? [])].sort((a, b) => {
    const sa = seasonOf(a.season_id)?.season_number ?? 0
    const sb = seasonOf(b.season_id)?.season_number ?? 0
    return sa - sb || a.episode_number - b.episode_number || a.language.localeCompare(b.language)
  })

  return (
    <div className="card">
      <div className="title-row">
        <h2 style={{ margin: 0 }}>Episodes</h2>
        <button onClick={() => setAdding((v) => !v)}>{adding ? 'Cancel' : 'Add an episode'}</button>
      </div>
      {adding && (
        <div className="body" style={{ borderBottom: '1px solid var(--line)' }}>
          <EpisodeForm
            show={show}
            onDone={() => {
              setAdding(false)
              qc.invalidateQueries()
            }}
          />
        </div>
      )}
      {rows.length === 0 ? (
        <Empty title="No episodes yet">
          <div>Add the first episode to get this show ready for publishing.</div>
        </Empty>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Season</th>
              <th>#</th>
              <th style={{ width: '28%' }}>Title</th>
              <th>Language</th>
              <th>Content group</th>
              <th>Runtime</th>
              <th>Thumb</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((ep) => {
              const season = seasonOf(ep.season_id)
              const thumb = ep.artwork.find((a) => a.kind === 'thumbnail')
              return (
                <>
                  <tr key={ep.id}>
                    <td>{season?.season_number === 0 ? 'Trailers' : `S${season?.season_number}`}</td>
                    <td>{ep.episode_number}</td>
                    <td>{ep.title}</td>
                    <td>
                      <span className="pill lang">{ep.language}</span>
                    </td>
                    <td className="mono">{ep.content_group ?? <span style={{ color: 'var(--block)' }}>Not set</span>}</td>
                    <td>{duration(ep.duration_seconds)}</td>
                    <td>{thumb ? '✓' : <span style={{ color: 'var(--block)' }}>Missing</span>}</td>
                    <td>
                      <Pill value={ep.status} />
                    </td>
                    <td className="row-actions">
                      <button onClick={() => setOpenId(openId === ep.id ? null : ep.id)}>
                        {openId === ep.id ? 'Close' : 'Edit'}
                      </button>
                    </td>
                  </tr>
                  {openId === ep.id && (
                    <tr key={`${ep.id}-edit`}>
                      <td colSpan={9} style={{ background: '#fafbfd' }}>
                        <EpisodeForm
                          show={show}
                          episode={ep}
                          onDone={() => {
                            setOpenId(null)
                            qc.invalidateQueries()
                          }}
                        />
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      )}
      <div className="body">
        <p className="sub">
          Episodes that share a content group are language versions of the same episode. Peblo TV shows
          them as one entry with a language picker.
        </p>
      </div>
    </div>
  )
}

function EpisodeForm({ show, episode, onDone }: { show: Show; episode?: Episode; onDone: () => void }) {
  const reference = useQuery({ queryKey: ['reference'], queryFn: () => get<Reference>('/admin/reference') })
  const specs = reference.data?.artwork
  const [form, setForm] = useState({
    season_id: episode?.season_id ?? show.seasons.find((s) => s.season_number === 1)?.id ?? show.seasons[0].id,
    episode_number: episode?.episode_number ?? 1,
    title: episode?.title ?? '',
    synopsis: episode?.synopsis ?? '',
    minutes: episode?.duration_seconds ? Math.floor(episode.duration_seconds / 60) : 0,
    seconds: episode?.duration_seconds ? episode.duration_seconds % 60 : 0,
    language: episode?.language ?? 'en',
    content_group: episode?.content_group ?? '',
    status: episode?.status ?? 'draft',
  })

  const save = useMutation({
    mutationFn: () => {
      const total = form.minutes * 60 + form.seconds
      const body = {
        season_id: form.season_id,
        episode_number: Number(form.episode_number),
        title: form.title,
        synopsis: form.synopsis,
        duration_seconds: total > 0 ? total : null,
        language: form.language,
        content_group: form.content_group || null,
        status: form.status,
      }
      return episode ? patch<Episode>(`/admin/episodes/${episode.id}`, body) : post<Episode>('/admin/episodes', body)
    },
    onSuccess: onDone,
  })

  const remove = useMutation({ mutationFn: () => del(`/admin/episodes/${episode!.id}`), onSuccess: onDone })

  return (
    <div style={{ padding: episode ? '12px 0' : 0 }}>
      {save.isError && <div className="banner error">{(save.error as ApiError).message}</div>}
      <div className="grid3">
        <div className="field">
          <label>Season</label>
          <select
            style={{ width: '100%' }}
            value={form.season_id}
            onChange={(e) => setForm((f) => ({ ...f, season_id: e.target.value }))}
          >
            {show.seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.season_number === 0 ? 'Trailers (season 0)' : `Season ${s.season_number}`}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Episode number</label>
          <input
            type="number"
            min={1}
            style={{ width: '100%' }}
            value={form.episode_number}
            onChange={(e) => setForm((f) => ({ ...f, episode_number: Number(e.target.value) }))}
          />
        </div>
        <div className="field">
          <label>Language</label>
          <select
            style={{ width: '100%' }}
            value={form.language}
            onChange={(e) => setForm((f) => ({ ...f, language: e.target.value }))}
          >
            {reference.data?.languages.map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Title</label>
        <input
          style={{ width: '100%' }}
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
      </div>
      <div className="grid3">
        <div className="field">
          <label>Runtime</label>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              type="number"
              min={0}
              style={{ width: 70 }}
              value={form.minutes}
              onChange={(e) => setForm((f) => ({ ...f, minutes: Number(e.target.value) }))}
            />
            <span className="sub">min</span>
            <input
              type="number"
              min={0}
              max={59}
              style={{ width: 70 }}
              value={form.seconds}
              onChange={(e) => setForm((f) => ({ ...f, seconds: Number(e.target.value) }))}
            />
            <span className="sub">sec</span>
          </div>
        </div>
        <div className="field">
          <label>Content group — same value on every language of this episode</label>
          <input
            style={{ width: '100%' }}
            placeholder="mango-and-moon-s1e1"
            value={form.content_group}
            onChange={(e) => setForm((f) => ({ ...f, content_group: e.target.value }))}
          />
        </div>
        <div className="field">
          <label>Status</label>
          <select
            style={{ width: '100%' }}
            value={form.status}
            onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as 'draft' }))}
          >
            <option value="draft">Draft</option>
            <option value="published">Published</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>

      {episode && specs && (
        <div className="slots" style={{ marginBottom: 14, maxWidth: 300 }}>
          <ArtworkSlot
            ownerType="episode"
            ownerId={episode.id}
            kind="thumbnail"
            label="Thumbnail"
            usedFor="episode lists"
            spec={specs.thumbnail}
            current={episode.artwork.find((a) => a.kind === 'thumbnail')}
          />
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button className="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? 'Saving…' : episode ? 'Save episode' : 'Add episode'}
        </button>
        {episode && (
          <button
            className="danger"
            onClick={() => {
              if (confirm(`Delete “${episode.title}”?`)) remove.mutate()
            }}
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}
