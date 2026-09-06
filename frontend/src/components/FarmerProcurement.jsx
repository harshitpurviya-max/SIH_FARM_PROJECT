import { useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { API_BASE, apiFetch } from '../api'
import { useLanguage } from '../i18n'
import {
  documentsLoaded,
  notificationsLoaded,
  notificationRead,
  procurementConnectionChanged,
  procurementFailed,
  procurementLoaded,
  procurementRequested,
} from '../features/procurement/procurementSlice'

const steps = ['BOOKED', 'ARRIVED', 'WAITING', 'QUALITY_CHECK', 'WEIGHMENT', 'ACCEPTED', 'PAYMENT_PENDING', 'PAYMENT_INITIATED', 'PAYMENT_PROCESSING', 'PAYMENT_COMPLETED']
function freshnessLabel(value) {
  return value || 'FRESH'
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Not recorded'
}

function DataCard({ title, children }) {
  return <section className="info-card"><div className="card-label">{title}</div>{children}</section>
}

export default function FarmerProcurement({ onBook, user }) {
  const dispatch = useDispatch()
  const { active, notifications, documents, loading, error, connection } = useSelector((state) => state.procurement)
  const { t } = useLanguage()
  const socketRef = useRef(null)

  async function load() {
    dispatch(procurementRequested())
    try {
      const result = await apiFetch('/api/farmer/active-procurement')
      dispatch(procurementLoaded(result))
      const [noticeResult, documentResult] = await Promise.all([
        apiFetch('/api/notifications'),
        apiFetch(`/api/mandis/${result.mandi.id}/required-documents`),
      ])
      dispatch(notificationsLoaded(noticeResult))
      dispatch(documentsLoaded(documentResult))
    } catch (reason) {
      dispatch(procurementFailed(reason.message))
    }
  }

  useEffect(() => {
    load()
    let reconnectTimer
    let stopped = false
    function connect() {
      if (stopped) return
      const socket = new WebSocket(`${API_BASE.replace(/^http/, 'ws')}/ws/queue`)
      socketRef.current = socket
      socket.onopen = () => dispatch(procurementConnectionChanged('live'))
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data)
          if (['TOKEN_STATUS_UPDATED', 'QUALITY_UPDATED', 'WEIGHMENT_UPDATED', 'PAYMENT_UPDATED', 'QUEUE_UPDATED'].includes(event.type)) load()
        } catch {
          // Ignore malformed events; REST remains the source of truth.
        }
      }
      socket.onerror = () => dispatch(procurementConnectionChanged('offline'))
      socket.onclose = () => {
        dispatch(procurementConnectionChanged('offline'))
        if (!stopped) reconnectTimer = window.setTimeout(connect, 3000)
      }
    }
    connect()
    return () => {
      stopped = true
      window.clearTimeout(reconnectTimer)
      socketRef.current?.close()
    }
  }, [dispatch])

  if (loading && !active) return <section className="dashboard-section"><div className="loading-panel">Loading procurement status…</div></section>
  if (error && !active) return <section className="dashboard-section"><div className="empty-panel"><strong>Unable to load procurement.</strong><p>{error}</p><button className="primary-button compact" onClick={load}>Retry</button><button className="text-button" onClick={onBook}>Book a slot</button></div></section>
  if (!active) return <section className="dashboard-section"><div className="empty-panel"><strong>You do not have an active procurement.</strong><p>Book a slot to receive a token and track the journey.</p><button className="primary-button compact" onClick={onBook}>Book a slot</button></div></section>

  const { token, mandi, slot, queue, timeline, quality, weighment, payment } = active
  const currentIndex = steps.indexOf(token.status)
  const freshness = freshnessLabel(queue.freshness)
  const nextStep = token.status === 'REJECTED' ? t('rejectionReason') : t(`status.${steps[Math.min(currentIndex + 1, steps.length - 1)]}`)

  return (
    <section className="procurement-layout">
      <div className="procurement-heading">
        <div><p className="eyebrow">{t('farmerView')}</p><h2>{t('procurementJourney')}</h2><p className="muted-copy">{t('procurementIntro')}</p></div>
        <div className={`freshness ${freshness.toLowerCase()}`}><span /> {t(`freshness.${freshness}`)}<small>{t('updated')} {formatDate(queue.last_updated_at)}</small></div>
      </div>
      <div className="procurement-grid">
        <section className="token-hero">
          <div className="card-label">{t('yourToken')}</div>
          <strong>{token.token_code}</strong>
          <div className="token-meta">{mandi?.name || t('procurementCenter')} · {token.crop_type} · {token.expected_tonnage} quintals</div>
          <div className="token-meta">{t('farmerId')}: {user?.farmer_id || '—'} · {mandi?.district || '—'}</div>
          <div className="status-chip">{t(`status.${token.status}`)}</div>
          <div className="queue-stats">
            <div><span>{t('position')}</span><strong>{queue.queue_position ?? '—'}</strong></div>
            <div><span>{t('peopleAhead')}</span><strong>{queue.people_ahead}</strong></div>
            <div><span>{t('estimatedWait')}</span><strong>{queue.estimated_wait_minutes}<small> min</small></strong></div>
          </div>
          <p className="serving-line">{t('currentServing')} <strong>{queue.current_serving || t('noToken')}</strong></p>
        </section>
        <DataCard title={t('nextStep')}><h3>{nextStep}</h3><p className="muted-copy">{t('updated')} {formatDate(token.last_updated_at)}.</p></DataCard>
        <DataCard title={t('appointment')}><h3>{mandi?.name || t('selectCenter')}</h3><p className="muted-copy">{mandi?.location}<br />{slot?.date} · {slot?.start_time?.slice(0, 5)}–{slot?.end_time?.slice(0, 5)}</p></DataCard>
      </div>
      <div className="procurement-columns">
        <DataCard title="Procurement timeline">
          <div className="timeline">{timeline.map((event) => <div className="timeline-item" key={event.id}><span className="timeline-dot" /><div><strong>{t(`status.${event.new_status}`)}</strong><small>{formatDate(event.changed_at)}{event.remarks ? ` · ${event.remarks}` : ''}</small></div></div>)}</div>
          {steps.filter((step) => !timeline.some((event) => event.new_status === step)).map((step) => <div className="timeline-item pending" key={step}><span className="timeline-dot" /><div><strong>{t(`status.${step}`)}</strong><small>{t('upcoming')}</small></div></div>)}
        </DataCard>
        <div className="detail-stack">
          <DataCard title="Quality inspection">{quality ? <div className="detail-grid"><span>Grade<strong>{quality.grade || '—'}</strong></span><span>Moisture<strong>{quality.moisture_percentage ?? '—'}%</strong></span><span>Result<strong className={quality.decision === 'REJECTED' ? 'danger-text' : 'good-text'}>{quality.decision}</strong></span><span>Remarks<strong>{quality.rejection_reason || quality.remarks || '—'}</strong></span></div> : <p className="muted-copy">Quality inspection has not been recorded yet.</p>}</DataCard>
          <DataCard title="Weighment">{weighment ? <div className="detail-grid"><span>Gross<strong>{weighment.gross_weight} kg</strong></span><span>Tare<strong>{weighment.tare_weight} kg</strong></span><span>Net<strong>{weighment.net_weight} kg</strong></span><span>Recorded<strong>{formatDate(weighment.weighed_at)}</strong></span></div> : <p className="muted-copy">Weight will appear after the officer records it.</p>}</DataCard>
          <DataCard title="Payment">{payment ? <div className="payment-line"><strong>₹{Number(payment.amount || 0).toLocaleString('en-IN')}</strong><span className="status-chip subtle">{payment.status || 'PENDING'}</span></div> : <p className="muted-copy">Payment is created after procurement acceptance.</p>}</DataCard>
        </div>
      </div>
      <div className="utility-grid">
        <DataCard title="Required documents"><div className="document-list">{documents.length ? documents.map((document) => <div key={document.id}><span className="document-mark">{document.is_required ? '✓' : '○'}</span><span>{document.label}<small>{document.description || (document.is_required ? 'Required' : 'Optional')}</small></span></div>) : <p className="muted-copy">No documents configured for this mandi.</p>}</div></DataCard>
        <DataCard title={`Notifications${notifications.filter((item) => !item.is_read).length ? ` · ${notifications.filter((item) => !item.is_read).length} new` : ''}`}><div className="notification-list">{notifications.length ? notifications.slice(0, 5).map((item) => <button className={item.is_read ? 'notification read' : 'notification'} key={item.id} onClick={async () => { if (!item.is_read) { await apiFetch(`/api/notifications/${item.id}/read`, { method: 'PATCH' }); dispatch(notificationRead(item.id)) } }}><strong>{item.title}</strong><span>{item.message}</span></button>) : <p className="muted-copy">No notifications yet.</p>}</div></DataCard>
      </div>
      <DataCard title={t('smsNotifications')}><div className="notification-list">{notifications.filter((item) => item.channel === 'SMS').length ? notifications.filter((item) => item.channel === 'SMS').map((item) => <div className="notification read" key={`sms-${item.id}`}><strong>{item.title}</strong><span>{item.message}</span><small>{t('notificationType')}: {item.event_type} · {t('notificationStatus')}: {item.delivery_status} · {t('notificationTimestamp')}: {formatDate(item.sent_at || item.created_at)}</small></div>) : <p className="muted-copy">No SMS notifications yet.</p>}</div></DataCard>
      <div className="connection-note"><span className={connection === 'live' ? 'signal live' : 'signal'} /> {connection === 'live' ? 'Realtime updates connected' : 'Updates reconnecting; current data is from the server'}</div>
    </section>
  )
}
