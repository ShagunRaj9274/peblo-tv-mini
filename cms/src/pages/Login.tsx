import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, post, session, type Session } from '../lib/api'

export function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState('admin@peblo.tv')
  const [password, setPassword] = useState('peblo-admin')

  const login = useMutation({
    mutationFn: () => post<Session>('/auth/login', { email, password }),
    onSuccess: (s) => {
      session.save(s)
      onSignedIn()
    },
  })

  return (
    <div className="login">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault()
          login.mutate()
        }}
      >
        <div className="title-row">
          <h1>Peblo CMS</h1>
        </div>
        <div className="body">
          {login.isError && <div className="banner error">{(login.error as ApiError).message}</div>}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" style={{ width: '100%' }} value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              style={{ width: '100%' }}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="primary" type="submit" disabled={login.isPending} style={{ width: '100%' }}>
            {login.isPending ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="hint">
            Demo accounts — admin can publish, editor cannot:
            <br />
            <code>admin@peblo.tv</code> / <code>peblo-admin</code>
            <br />
            <code>editor@peblo.tv</code> / <code>peblo-editor</code>
          </p>
        </div>
      </form>
    </div>
  )
}
