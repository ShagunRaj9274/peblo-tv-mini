import { useState } from 'react'
import { NavLink, Route, Routes, Navigate } from 'react-router-dom'
import { session } from './lib/api'
import { Login } from './pages/Login'
import { Publish } from './pages/Publish'
import { ShowEditor } from './pages/ShowEditor'
import { Shows } from './pages/Shows'

const VIEWER_URL = import.meta.env.VITE_VIEWER_URL ?? 'http://localhost:5174'

export default function App() {
  const [user, setUser] = useState(session.get())

  if (!user) return <Login onSignedIn={() => setUser(session.get())} />

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">Peblo CMS</div>
        <NavLink to="/shows">Shows</NavLink>
        <NavLink to="/publish">Publish</NavLink>
        <a href={VIEWER_URL} target="_blank" rel="noreferrer">
          Open Peblo TV ↗
        </a>
        <div className="who">
          <strong>{user.name}</strong>
          {user.email}
          <div style={{ marginTop: 4 }}>
            Role: {user.role}
            {user.role === 'editor' && ' — cannot publish'}
          </div>
          <button
            className="link"
            style={{ paddingLeft: 0, marginTop: 6 }}
            onClick={() => {
              session.clear()
              setUser(null)
            }}
          >
            Sign out
          </button>
        </div>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/shows" replace />} />
          <Route path="/shows" element={<Shows />} />
          <Route path="/shows/:showId" element={<ShowEditor />} />
          <Route path="/publish" element={<Publish />} />
          <Route path="*" element={<Navigate to="/shows" replace />} />
        </Routes>
      </main>
    </div>
  )
}
