import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import AuthPanel from './components/AuthPanel'
import FarmerBookingFlow from './components/FarmerBookingFlow'
import FarmerProcurement from './components/FarmerProcurement'
import MandiDashboard from './components/MandiDashboard'
import NoticeBoard from './components/NoticeBoard'
import { apiFetch, getStoredAuth } from './api'
import { authInitialized, authSucceeded, signedOut } from './features/auth/authSlice'
import { useLanguage } from './i18n'

export default function App() {
  const dispatch = useDispatch()
  const { user, initialized } = useSelector((state) => state.auth)
  const [view, setView] = useState('procurement')
  const [noticeContext, setNoticeContext] = useState({ district: '', centerId: '' })
  const { language, setLanguage, languages, t } = useLanguage()

  useEffect(() => {
    if (!getStoredAuth()) { dispatch(authInitialized()); return }
    apiFetch('/api/auth/me').then((currentUser) => {
      const saved = getStoredAuth()
      dispatch(authSucceeded({ ...saved, user: currentUser }))
    }).catch(() => dispatch(signedOut()))
  }, [dispatch])

  if (!initialized) return <main className="app-shell"><div className="loading-panel app-loading">Loading SIHFarm…</div></main>
  if (!user) return <main className="app-shell"><header className="topbar auth-topbar"><a className="brand" href="/" aria-label={t('home')}><span className="brand-mark">KS</span><span>{t('appName')}</span></a><div className="language-selector" aria-label={t('language')}>{languages.map((item) => <button key={item} className={language === item ? 'active' : ''} onClick={() => setLanguage(item)}>{item === 'en' ? 'English' : item === 'hi' ? 'हिंदी' : 'मराठी'}</button>)}</div><div className="network-badge"><span /> {t('subtitle')}</div></header><AuthPanel /><NoticeBoard /></main>

  const isOfficer = user.role === 'OFFICER' || user.role === 'ADMIN'
  function logout() { dispatch(signedOut()) }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label={t('home')}><span className="brand-mark">KS</span><span>{t('appName')}</span></a>
        <nav className="view-switcher" aria-label="Application views">
          {isOfficer ? <button className="active">Mandi control</button> : <><button className={view === 'procurement' ? 'active' : ''} onClick={() => setView('procurement')}>My procurement</button><button className={view === 'booking' ? 'active' : ''} onClick={() => setView('booking')}>Book a slot</button></>}
        </nav>
        <div className="user-menu"><span>{user.full_name || user.phone}</span><small>{user.role === 'FARMER' ? `${t('farmerId')}: ${user.farmer_id || '—'}` : user.role.toLowerCase()}</small><button className="text-button" onClick={logout}>Sign out</button></div>
        <div className="language-selector" aria-label={t('language')}>{languages.map((item) => <button key={item} className={language === item ? 'active' : ''} onClick={() => setLanguage(item)}>{item === 'en' ? 'English' : item === 'hi' ? 'हिंदी' : 'मराठी'}</button>)}</div>
      </header>
      <section className="hero-band compact-hero"><div><p className="eyebrow">{isOfficer ? t('fieldOperations') : t('farmerTransparency')}</p><h1>{isOfficer ? t('officerHero') : t('heroTitle')} {!isOfficer && <em>{t('heroEmphasis')}</em>}</h1></div><p className="hero-note">{isOfficer ? t('officerNote') : t('heroNote')}</p></section>
      {!isOfficer && <NoticeBoard district={noticeContext.district} centerId={noticeContext.centerId} />}
      {isOfficer ? <MandiDashboard /> : view === 'booking' ? <FarmerBookingFlow user={user} onContextChange={setNoticeContext} onTrack={() => setView('procurement')} /> : <FarmerProcurement user={user} onBook={() => setView('booking')} />}
      <footer><span>{t('platform')}</span><span>{t('footer')}</span></footer>
    </main>
  )
}
