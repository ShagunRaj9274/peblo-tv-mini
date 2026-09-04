import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { ApiError, upload } from '../lib/api'
import type { Artwork, Reference } from '../lib/types'

type Props = {
  ownerType: 'show' | 'episode'
  ownerId: string
  kind: 'poster' | 'banner' | 'thumbnail'
  label: string
  usedFor: string
  spec: Reference['artwork'][string]
  current?: Artwork
}

/** The three labelled upload slots. Each one states its required size up front,
 *  previews what is there now, and shows the server's rejection reasons verbatim.
 *  Client-side checks exist only to save a round trip — the server decides. */
export function ArtworkSlot({ ownerType, ownerId, kind, label, usedFor, spec, current }: Props) {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [problems, setProblems] = useState<{ code: string; message: string }[]>([])
  const [done, setDone] = useState(false)

  const mutation = useMutation({
    mutationFn: (file: File) => upload<Artwork>(`/admin/artwork/${ownerType}/${ownerId}/${kind}`, file),
    onSuccess: () => {
      setProblems([])
      setDone(true)
      qc.invalidateQueries()
    },
    onError: (error: ApiError) => {
      setDone(false)
      setProblems(error.problems ?? [{ code: 'error', message: error.message }])
    },
  })

  function choose(file: File | undefined) {
    if (!file) return
    setPreview(URL.createObjectURL(file))
    setDone(false)
    setProblems([])
    mutation.mutate(file)
  }

  const shown = preview ?? current?.url
  const kb = (n: number) => `${Math.round(n / 1024)} KB`

  return (
    <div className={`slot${problems.length ? ' rejected' : ''}`}>
      <h3>{label}</h3>
      <p className="spec">
        {spec.target_width}×{spec.target_height} · {spec.aspect_ratio} · under {kb(spec.max_bytes)} · {usedFor}
      </p>
      <div className="preview">
        {shown ? (
          <img src={shown} alt={`${label} preview`} />
        ) : (
          <span className="empty">No {label.toLowerCase()} yet</span>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        style={{ display: 'none' }}
        onChange={(e) => choose(e.target.files?.[0])}
      />
      <button type="button" onClick={() => inputRef.current?.click()} disabled={mutation.isPending}>
        {mutation.isPending ? 'Checking image…' : current || done ? `Replace ${label.toLowerCase()}` : `Upload ${label.toLowerCase()}`}
      </button>
      {current && !problems.length && (
        <p className="meta" style={{ marginTop: 8 }}>
          On file: {current.width}×{current.height}, {kb(current.bytes)}
        </p>
      )}
      {done && <p className="meta" style={{ marginTop: 8, color: 'var(--ok)' }}>Saved.</p>}
      {problems.length > 0 && (
        <ul className="problems">
          {problems.map((p) => (
            <li key={p.code + p.message}>{p.message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
