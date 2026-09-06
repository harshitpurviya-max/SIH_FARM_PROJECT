import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { API_BASE, apiFetch } from '../api'
import { connectionChanged, tokenStatusChanged, tokensFailed, tokensLoaded, tokensRequested } from '../features/queue/queueSlice'
import { useLanguage } from '../i18n'
import NoticeManager from './NoticeManager'

const columns = [
  { key: 'BOOKED', label: 'Booked', accent: 'border-lime' },
  { key: 'ARRIVED', label: 'Arrived', accent: 'border-sky' },
  { key: 'WAITING', label: 'Waiting', accent: 'border-aqua' },
  { key: 'QUALITY_CHECK', label: 'Quality', accent: 'border-clay' },
  { key: 'WEIGHMENT', label: 'Weighment', accent: 'border-gold' },
  { key: 'PAYMENT_PENDING', label: 'Payment', accent: 'border-ink' },
]
const transitions = { BOOKED: 'ARRIVED', ARRIVED: 'WAITING', WAITING: 'QUALITY_CHECK' }

export default function MandiDashboard() {
  const dispatch = useDispatch()
  const { t } = useLanguage()
  const { tokens, loading, error, connection } = useSelector((state) => state.queue)
  const [selected, setSelected] = useState(null)
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const [smsNotifications, setSmsNotifications] = useState([])
  const [qualityForm, setQualityForm] = useState({ grade: 'A', moisture_percentage: '', decision: 'ACCEPTED', remarks: '', rejection_reason: '' })
  const [weightForm, setWeightForm] = useState({ gross_weight: '', tare_weight: '', reference_number: '', remarks: '' })

  async function loadTokens() {
    dispatch(tokensRequested())
    try { dispatch(tokensLoaded(await apiFetch('/api/tokens'))) } catch (reason) { dispatch(tokensFailed(reason.message)) }
  }

  useEffect(() => {
    loadTokens()
    let reconnectTimer
    let stopped = false
    function connect() {
      if (stopped) return null
      const socket = new WebSocket(`${API_BASE.replace(/^http/, 'ws')}/ws/queue`)
      socket.onopen = () => dispatch(connectionChanged('live'))
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data)
          if (event.token?.id) dispatch(tokenStatusChanged(event.token))
          if (event.type === 'PAYMENT_UPDATED') loadTokens()
        } catch { /* REST remains authoritative. */ }
      }
      socket.onerror = () => dispatch(connectionChanged('offline'))
      socket.onclose = () => { dispatch(connectionChanged('offline')); if (!stopped) reconnectTimer = window.setTimeout(connect, 3000) }
      return socket
    }
    const socket = connect()
    return () => { stopped = true; window.clearTimeout(reconnectTimer); socket?.close() }
  }, [dispatch])

  useEffect(() => {
    if (!selected) { setSmsNotifications([]); return }
    apiFetch(`/api/officer/tokens/${selected.id}/notifications`).then(setSmsNotifications).catch(() => setSmsNotifications([]))
  }, [selected])

  const counts = useMemo(() => columns.map((column) => tokens.filter((token) => token.status === column.key).length), [tokens])

  async function move(token, status) {
    setBusy(true); setActionError('')
    try {
      const updated = await apiFetch(`/api/tokens/${token.id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
      dispatch(tokenStatusChanged(updated)); setSelected(updated)
    } catch (reason) { setActionError(reason.message) } finally { setBusy(false) }
  }

  async function submitQuality(event) {
    event.preventDefault(); setBusy(true); setActionError('')
    try {
      const updated = await apiFetch(`/api/officer/tokens/${selected.id}/quality`, { method: 'POST', body: JSON.stringify({ ...qualityForm, moisture_percentage: qualityForm.moisture_percentage === '' ? null : Number(qualityForm.moisture_percentage) }) })
      dispatch(tokenStatusChanged(updated)); setSelected(updated)
    } catch (reason) { setActionError(reason.message) } finally { setBusy(false) }
  }

  async function submitWeight(event) {
    event.preventDefault(); setBusy(true); setActionError('')
    try {
      const updated = await apiFetch(`/api/officer/tokens/${selected.id}/weighment`, { method: 'POST', body: JSON.stringify({ ...weightForm, gross_weight: Number(weightForm.gross_weight), tare_weight: Number(weightForm.tare_weight) }) })
      dispatch(tokenStatusChanged(updated)); setSelected(updated)
    } catch (reason) { setActionError(reason.message) } finally { setBusy(false) }
  }

  async function decide(accepted) {
    const reason = accepted ? null : window.prompt('Rejection reason')
    if (!accepted && !reason) return
    setBusy(true); setActionError('')
    try {
      const updated = await apiFetch(`/api/officer/tokens/${selected.id}/decision`, { method: 'POST', body: JSON.stringify({ accepted, reason }) })
      dispatch(tokenStatusChanged(updated)); setSelected(updated)
    } catch (reasonError) { setActionError(reasonError.message) } finally { setBusy(false) }
  }

  async function updatePayment(status) {
    setBusy(true); setActionError('')
    try {
      await apiFetch(`/api/officer/tokens/${selected.id}/payment`, { method: 'PATCH', body: JSON.stringify({ status }) })
      const nextStatus = { INITIATED: 'PAYMENT_INITIATED', PROCESSING: 'PAYMENT_PROCESSING', COMPLETED: 'PAYMENT_COMPLETED', FAILED: 'PAYMENT_FAILED' }[status]
      setSelected((current) => ({ ...current, status: nextStatus }))
    } catch (reason) { setActionError(reason.message) } finally { setBusy(false) }
  }

  const columnLabels = { BOOKED: t('status.BOOKED'), ARRIVED: t('status.ARRIVED'), WAITING: t('status.WAITING'), QUALITY_CHECK: t('qualityInspection'), WEIGHMENT: t('weighment'), PAYMENT_PENDING: t('payment') }
  return (
    <section className="dashboard-section officer-section">
      <div className="dashboard-heading"><div><p className="eyebrow">{t('mandiControl')}</p><h2>{t('mandiControlTitle')}</h2><p className="muted-copy">{t('mandiControlIntro')}</p></div><div className={`live-indicator ${connection}`}><span /> {connection === 'live' ? t('liveUpdates') : t('reconnecting')}</div></div>
      <div className="metric-strip officer-metrics">{columns.map((column, index) => <div key={column.key}><span>{columnLabels[column.key]}</span><strong>{counts[index]}</strong></div>)}</div>
      {(error || actionError) && <p className="form-error" role="alert">{error || actionError}</p>}
      {loading ? <div className="loading-panel">{t('loadingQueue')}</div> : <div className="queue-board officer-board">{columns.map((column) => { const stageTokens = tokens.filter((token) => token.status === column.key); return <div className={`queue-column ${column.accent}`} key={column.key}><div className="column-heading"><h3>{columnLabels[column.key]}</h3><span>{stageTokens.length}</span></div><div className="token-stack">{stageTokens.map((token) => <button className={`token-card officer-token ${selected?.id === token.id ? 'selected' : ''}`} key={token.id} onClick={() => setSelected(token)}><div className="token-card-top"><strong>{token.token_code}</strong><span>{t(`status.${token.status}`)}</span></div><p>{token.crop_type} · {token.expected_tonnage} quintals</p><small>{token.farmer_display_id || t('farmerId')}: {token.farmer_phone}</small><small>{token.district || '—'} · {token.mandi_name || '—'}</small></button>)}{stageTokens.length === 0 && <div className="column-empty">{t('noTokens')}</div>}</div></div>})}</div>}
      {selected && <section className="officer-action-panel"><div className="action-heading"><div><p className="eyebrow">{t('selectedToken')}</p><h3>{selected.token_code} <span>{t(`status.${selected.status}`)}</span></h3><p className="muted-copy">{selected.crop_type} · {selected.expected_tonnage} quintals · {selected.farmer_display_id || t('farmerId')}: {selected.farmer_phone}</p><p className="muted-copy">{selected.district || '—'} · {selected.mandi_name || '—'}</p></div><button className="text-button" onClick={() => setSelected(null)}>{t('close')}</button></div>
        <div className="notification-list"><strong>SMS notification history</strong>{smsNotifications.length ? smsNotifications.slice(0, 3).map((item) => <div className="notification read" key={item.id}><span>{item.message}</span><small>{item.event_type} · {item.delivery_status}</small></div>) : <p className="muted-copy">No SMS notifications generated yet.</p>}</div>
        {transitions[selected.status] && <button className="primary-button compact" disabled={busy} onClick={() => move(selected, transitions[selected.status])}>{selected.status === 'BOOKED' ? t('markArrived') : selected.status === 'ARRIVED' ? t('moveWaiting') : t('startQuality')} <span>→</span></button>}
        {selected.status === 'QUALITY_CHECK' && <form className="action-form" onSubmit={submitQuality}><h4>{t('recordQuality')}</h4><div className="form-grid"><label>{t('grade')}<input value={qualityForm.grade} onChange={(event) => setQualityForm({ ...qualityForm, grade: event.target.value })} /></label><label>{t('moisture')}<input type="number" min="0" max="100" step="0.1" value={qualityForm.moisture_percentage} onChange={(event) => setQualityForm({ ...qualityForm, moisture_percentage: event.target.value })} required /></label></div><label>{t('decision')}<select value={qualityForm.decision} onChange={(event) => setQualityForm({ ...qualityForm, decision: event.target.value })}><option value="ACCEPTED">{t('accepted')}</option><option value="REJECTED">{t('rejected')}</option></select></label><label>{t('remarks')}<textarea value={qualityForm.remarks} onChange={(event) => setQualityForm({ ...qualityForm, remarks: event.target.value })} /></label>{qualityForm.decision === 'REJECTED' && <label>{t('rejectionReason')}<textarea required value={qualityForm.rejection_reason} onChange={(event) => setQualityForm({ ...qualityForm, rejection_reason: event.target.value })} /></label>}<button className="primary-button compact" disabled={busy}>{t('saveQuality')}</button></form>}
        {selected.status === 'WEIGHMENT' && <form className="action-form" onSubmit={submitWeight}><h4>{t('recordWeighment')}</h4><div className="form-grid"><label>{t('grossWeight')}<input type="number" min="0.001" step="0.001" value={weightForm.gross_weight} onChange={(event) => setWeightForm({ ...weightForm, gross_weight: event.target.value })} required /></label><label>{t('tareWeight')}<input type="number" min="0" step="0.001" value={weightForm.tare_weight} onChange={(event) => setWeightForm({ ...weightForm, tare_weight: event.target.value })} required /></label></div><label>{t('reference')}<input value={weightForm.reference_number} onChange={(event) => setWeightForm({ ...weightForm, reference_number: event.target.value })} /></label><label>{t('remarks')}<textarea value={weightForm.remarks} onChange={(event) => setWeightForm({ ...weightForm, remarks: event.target.value })} /></label><button className="primary-button compact" disabled={busy}>{t('saveWeighment')}</button></form>}
        {selected.status === 'WEIGHMENT' && <div className="decision-actions"><button className="primary-button compact" disabled={busy} onClick={() => decide(true)}>{t('acceptProcurement')}</button><button className="danger-button" disabled={busy} onClick={() => decide(false)}>{t('rejectProcurement')}</button></div>}
        {selected.status === 'PAYMENT_PENDING' && <button className="primary-button compact" disabled={busy} onClick={() => updatePayment('INITIATED')}>{t('initiatePayment')} <span>→</span></button>}
        {selected.status === 'PAYMENT_INITIATED' && <button className="primary-button compact" disabled={busy} onClick={() => updatePayment('PROCESSING')}>{t('processPayment')} <span>→</span></button>}
        {selected.status === 'PAYMENT_PROCESSING' && <div className="decision-actions"><button className="primary-button compact" disabled={busy} onClick={() => updatePayment('COMPLETED')}>{t('completePayment')}</button><button className="danger-button" disabled={busy} onClick={() => updatePayment('FAILED')}>{t('markFailed')}</button></div>}
      </section>}
      <NoticeManager />
    </section>
  )
}
