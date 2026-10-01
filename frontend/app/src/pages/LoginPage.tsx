import { useState, type FormEvent } from 'react'

export default function LoginPage({ onLogin }: { onLogin: (u: string, p: string) => Promise<any> }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onLogin(username, password)
    } catch (err: any) {
      setError(err.detail || err.message || 'Giriş başarısız')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-tp-bg">
      <form
        onSubmit={submit}
        className="bg-tp-surface border border-tp-border-strong rounded-lg p-10 w-[360px]"
      >
        <div className="text-2xl font-bold text-tp-accent-light mb-1 text-center">
          MachiningPro AI
        </div>
        <div className="text-xs text-tp-text-3 text-center mb-8">
          AI-assisted machining engineering platform
        </div>

        <div className="mb-4">
          <label className="block text-xs text-tp-text-2 mb-1">Kullanıcı adı</label>
          <input
            value={username}
            onChange={e => setUsername(e.target.value)}
            className="w-full bg-tp-surface-2 border border-tp-border rounded-md px-3 py-2
                       text-sm text-tp-text outline-none focus:border-tp-accent transition-colors"
            autoFocus
          />
        </div>

        <div className="mb-6">
          <label className="block text-xs text-tp-text-2 mb-1">Şifre</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full bg-tp-surface-2 border border-tp-border rounded-md px-3 py-2
                       text-sm text-tp-text outline-none focus:border-tp-accent transition-colors"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-tp-accent hover:bg-tp-accent-light text-white py-2.5
                     rounded-md text-sm font-semibold transition-colors disabled:opacity-50"
        >
          {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
        </button>

        {error && <div className="text-tp-error text-xs mt-3 text-center">{error}</div>}

        <div className="text-[10px] text-tp-text-3 text-center mt-6">
          MachiningPro AI — engineering research preview
        </div>
      </form>
    </div>
  )
}
