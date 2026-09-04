import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useNavigate, useSearchParams } from 'react-router-dom'
import { Home } from './pages/Home'
import { Search } from './pages/Search'
import { ShowDetail } from './pages/ShowDetail'

export default function App() {
  return (
    <>
      <TopBar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/show/:slug" element={<ShowDetail />} />
        <Route
          path="*"
          element={
            <div className="state">
              <h2>That page wandered off</h2>
              <p>Try the home screen instead.</p>
            </div>
          }
        />
      </Routes>
      <div className="shell">
        <footer>
          Peblo TV reads only the published catalogue. Nothing on this screen talks to the CMS.
        </footer>
      </div>
    </>
  )
}

function TopBar() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  useEffect(() => setQ(params.get('q') ?? ''), [params])

  return (
    <div className="topbar">
      <div className="inner">
        <NavLink to="/" className="wordmark">
          Peblo<span>TV</span>
        </NavLink>
        <nav>
          <NavLink to="/">Home</NavLink>
          <NavLink to="/search">Browse</NavLink>
        </nav>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search')
          }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search shows and episodes"
            aria-label="Search shows and episodes"
          />
        </form>
      </div>
    </div>
  )
}
