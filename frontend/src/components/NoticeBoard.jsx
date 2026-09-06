import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useLanguage } from '../i18n'

function formatDate(value) {
  return value ? new Date(value).toLocaleDateString([], { dateStyle: 'medium' }) : '—'
}

export default function NoticeBoard({ district, centerId }) {
  const { language, t } = useLanguage()
  const [notices, setNotices] = useState([])
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const query = new URLSearchParams()
    if (district) query.set('district', district)
    if (centerId) query.set('center_id', centerId)
    apiFetch(`/api/notices${query.toString() ? `?${query}` : ''}`).then(setNotices).catch((reason) => setError(reason.message))
  }, [district, centerId])

  const label = (type) => ({ NEW: t('noticeNew'), IMPORTANT: t('noticeImportant'), GENERAL: t('noticeGeneral'), INFO: t('noticeInfo'), PAYMENT: t('noticePayment'), DISTRICT: t('noticeDistrict'), CENTER: t('noticeCenter'), SYSTEM: t('noticeSystem') }[type] || type)
  const content = (notice) => ({ title: notice[`title_${language}`] || notice.title_en || notice.title, description: notice[`description_${language}`] || notice.description_en || notice.description })

  return (
    <section className="dashboard-section notices-section" aria-labelledby="notices-heading">
      <div className="dashboard-heading">
        <div><p className="eyebrow">{t('noticeEyebrow')}</p><h2 id="notices-heading">{t('importantNotices')}</h2><p className="muted-copy">{t('noticeIntro')}</p></div>
        {district && <span className="status-chip subtle">{district}{centerId ? ` · ${t('procurementCenter')}` : ''}</span>}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="notice-grid">
        {notices.map((notice) => { const localized = content(notice); return <article className="notice-card" key={notice.id}>
          <div className="notice-card-top"><span className="notice-type">{label(notice.notice_type)}</span>{notice.notice_type === 'NEW' && <span className="notice-badge">{t('noticeNew')}</span>}</div>
          <h3>{localized.title}</h3><p>{localized.description}</p>
          <div className="notice-card-footer"><small>{t('published')}: {formatDate(notice.published_at)}</small><button className="text-button" onClick={() => setSelected(notice)}>{t('viewDetails')} →</button></div>
        </article> })}
        {!notices.length && !error && <div className="empty-panel"><strong>{t('noNotices')}</strong></div>}
      </div>
      {selected && <div className="notice-detail" role="dialog" aria-modal="true" aria-labelledby="notice-detail-title"><div className="notice-detail-panel"><button className="text-button" onClick={() => setSelected(null)}>← {t('backToNotices')}</button><span className="notice-type">{label(selected.notice_type)}</span><h3 id="notice-detail-title">{content(selected).title}</h3><p>{content(selected).description}</p><small>{t('published')}: {formatDate(selected.published_at)}{selected.expires_at ? ` · ${t('expiry')}: ${formatDate(selected.expires_at)}` : ''}{selected.district ? ` · ${t('district')}: ${selected.district}` : ''}{selected.center ? ` · ${t('procurementCenter')}: ${selected.center.name}` : ''}</small></div></div>}
    </section>
  )
}
