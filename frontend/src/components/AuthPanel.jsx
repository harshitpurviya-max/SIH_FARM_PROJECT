import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { apiFetch } from '../api'
import { authFailed, authIdle, authRequested, authSucceeded } from '../features/auth/authSlice'
import { useLanguage } from '../i18n'

export default function AuthPanel() {
  const dispatch = useDispatch()
  const { loading, error } = useSelector((state) => state.auth)
  const { t } = useLanguage()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ phone: '', password: '', full_name: '' })
  const [resetStep, setResetStep] = useState('request')
  const [otp, setOtp] = useState('')
  const [resetMessage, setResetMessage] = useState('')

  function update(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function submit(event) {
    event.preventDefault()
    dispatch(authRequested())
    try {
      const result = await apiFetch(mode === 'login' ? '/api/auth/login' : '/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(mode === 'login' ? { phone: form.phone, password: form.password } : form),
      })
      dispatch(authSucceeded(result))
    } catch (reason) {
      dispatch(authFailed(reason.message))
    }
  }

  async function requestReset(event) {
    event.preventDefault(); setResetMessage(''); dispatch(authRequested())
    try {
      const result = await apiFetch('/api/auth/forgot-password', { method: 'POST', body: JSON.stringify({ phone: form.phone }) })
      setOtp(result.demo_otp || ''); setResetStep('reset'); setResetMessage(t('otpSent')); dispatch(authIdle())
    } catch (reason) { dispatch(authFailed(reason.message)) }
  }

  async function resetPassword(event) {
    event.preventDefault(); setResetMessage(''); dispatch(authRequested())
    try {
      await apiFetch('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ phone: form.phone, otp, new_password: form.password }) })
      setMode('login'); setResetStep('request'); setResetMessage(t('resetPassword')); dispatch(authIdle())
    } catch (reason) { dispatch(authFailed(reason.message)) }
  }

  return (
    <section className="auth-layout">
      <div className="section-intro auth-intro">
        <p className="eyebrow">{t('appName')} · {t('farmerAccess')}</p>
        <h2>{t('authIntro')}</h2>
        <p className="muted-copy">{t('heroNote')}</p>
      </div>
      <form className="form-panel auth-panel" onSubmit={mode === 'forgot' ? (resetStep === 'request' ? requestReset : resetPassword) : submit}>
        <div className="auth-tabs" role="tablist">
          <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>{t('signIn')}</button>
          <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>{t('createAccount')}</button>
        </div>
        {mode === 'forgot' && <p className="eyebrow">{t('resetPassword')}</p>}
        {mode === 'register' && <label>{t('fullName')}<input name="full_name" value={form.full_name} onChange={update} placeholder={t('fullName')} required /></label>}
        <label>{t('mobile')}<input name="phone" value={form.phone} onChange={update} placeholder="+91 98765 43210" required minLength="7" /></label>
        {mode !== 'forgot' && <label>{t('password')}<input name="password" type="password" value={form.password} onChange={update} placeholder={t('password')} required minLength="8" /></label>}
        {mode === 'forgot' && resetStep === 'reset' && <><label>{t('otp')}<input value={otp} onChange={(event) => setOtp(event.target.value)} inputMode="numeric" minLength="6" maxLength="6" required /></label><label>{t('newPassword')}<input name="password" type="password" value={form.password} onChange={update} placeholder={t('newPassword')} required minLength="8" /></label></>}
        {error && <p className="form-error" role="alert">{error}</p>}
        {resetMessage && <p className="form-hint" role="status">{resetMessage}{otp && ` ${t('otp')}: ${otp}`}</p>}
        <button className="primary-button" disabled={loading}>{loading ? t('connect') : mode === 'forgot' ? (resetStep === 'request' ? t('requestOtp') : t('resetPassword')) : mode === 'login' ? t('signIn') : t('createAccount')}</button>
        {mode === 'login' && <button type="button" className="text-button" onClick={() => { setMode('forgot'); setResetStep('request'); dispatch(authIdle()) }}>{t('forgotPassword')}</button>}
        {mode === 'forgot' && <button type="button" className="text-button" onClick={() => { setMode('login'); setResetStep('request'); dispatch(authIdle()) }}>{t('signIn')}</button>}
        <p className="form-hint">{t('officerAccountNote')}</p>
      </form>
    </section>
  )
}