export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const TOKEN_KEY = 'peblo.cms.token'
const USER_KEY = 'peblo.cms.user'

export type Session = { access_token: string; role: 'editor' | 'admin'; name: string; email: string }

export const session = {
  get(): Session | null {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  },
  save(s: Session) {
    localStorage.setItem(TOKEN_KEY, s.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(s))
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
  token: () => localStorage.getItem(TOKEN_KEY),
}

/** Errors carry the server's message, because the server writes the messages
 *  an editor should read. The UI never invents its own copy for a failure. */
export class ApiError extends Error {
  status: number
  problems?: { code: string; message: string }[]
  constructor(status: number, message: string, problems?: { code: string; message: string }[]) {
    super(message)
    this.status = status
    this.problems = problems
  }
}

function extract(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown })?.detail
  if (typeof detail === 'string') return new ApiError(status, detail)
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: string; problems?: { code: string; message: string }[] }
    if (d.problems) return new ApiError(status, d.message ?? 'That upload was rejected.', d.problems)
    if (d.message) return new ApiError(status, d.message, undefined)
  }
  if (Array.isArray(detail)) {
    // Pydantic validation errors: surface the message, drop the field paths.
    const msgs = detail.map((e: { msg?: string }) => (e.msg ?? '').replace(/^Value error, /, ''))
    return new ApiError(status, msgs.filter(Boolean).join(' '))
  }
  return new ApiError(status, `Something went wrong (${status}). Try again.`)
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = session.token()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, "We can't reach the API. Check that the backend is running.")
  }
  if (res.status === 401) {
    session.clear()
    throw new ApiError(401, 'Your session expired. Sign in again.')
  }
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch { /* empty body */ }
    throw extract(res.status, body)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const get = <T,>(p: string) => api<T>(p)
export const post = <T,>(p: string, body?: unknown) =>
  api<T>(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
export const patch = <T,>(p: string, body: unknown) =>
  api<T>(p, { method: 'PATCH', body: JSON.stringify(body) })
export const del = (p: string) => api<void>(p, { method: 'DELETE' })
export const upload = <T,>(p: string, file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return api<T>(p, { method: 'POST', body: fd })
}
