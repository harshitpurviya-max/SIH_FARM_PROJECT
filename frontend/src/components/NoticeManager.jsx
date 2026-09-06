import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useLanguage } from '../i18n'

const initialForm = { title: '', description: '', notice_type: 'GENERAL', scope: 'GLOBAL', district: '', center_id: '', status: 'PUBLISHED' }

export default function NoticeManager() {
  const { t } = useLanguage()
  const [form, setForm] = useState(initialForm)
  const [notices, setNotices] = useState([])
  const [districts, setDistricts] = useState([])
  const [centers, setCenters] = useState([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try { setNotices(await apiFetch('/api/officer/notices')) } catch (reason) { setError(reason.message) }
  }
  useEffect(() => { load(); apiFetch('/api/districts').then(setDistricts).catch(() => {}); apiFetch('/api/mandis').then(setCenters).catch(() => {}) }, [])
  function update(event) { setForm((current) => ({ ...current, [event.target.name]: event.target.value })) }
  async function submit(event) {
    event.preventDefault(); setMessage(''); setError('')
    try {
      await apiFetch('/api/officer/notices', { method: 'POST', body: JSON.stringify({ ...form, center_id: form.scope === 'CENTER' ? Number(form.center_id) : null, district: form.scope === 'GLOBAL' ? null : form.district || null }) })
      setForm(initialForm); setMessage(t('noticePublished')); load()
    } catch (reason) { setError(reason.message) }
  }
  async function archive(id) {
    try { await apiFetch(`/api/officer/notices/${id}`, { method: 'DELETE' }); load() } catch (reason) { setError(reason.message) }
  }
  const visibleCenters = centers.filter((center) => !form.district || center.district === form.district)
  return <section className="officer-action-panel notice-manager"><div className="action-heading"><div><p className="eyebrow">{t('notices')}</p><h3>{t('publishNotice')}</h3></div></div>
    <form className="action-form" onSubmit={submit}><div className="form-grid"><label>{t('noticeTitle')}<input name="title" value={form.title} onChange={update} maxLength="180" required /></label><label>{t('noticeType')}<select name="notice_type" value={form.notice_type} onChange={update}><option>GENERAL</option><option>IMPORTANT</option><option>NEW</option><option>INFO</option><option>PAYMENT</option><option>SYSTEM</option></select></label></div><label>{t('noticeDescription')}<textarea name="description" value={form.description} onChange={update} maxLength="3000" required /></label><div className="form-grid"><label>{t('targetScope')}<select name="scope" value={form.scope} onChange={update}><option value="GLOBAL">{t('allFarmers')}</option><option value="DISTRICT">{t('district')}</option><option value="CENTER">{t('procurementCenter')}</option></select></label>{form.scope !== 'GLOBAL' && <label>{t('district')}<select name="district" value={form.district} onChange={update} required><option value="">{t('chooseDistrict')}</option>{districts.map((district) => <option key={district}>{district}</option>)}</select></label>}{form.scope === 'CENTER' && <label>{t('procurementCenter')}<select name="center_id" value={form.center_id} onChange={update} required><option value="">{t('chooseCenter')}</option>{visibleCenters.map((center) => <option key={center.id} value={center.id}>{center.name}</option>)}</select></label>}</div>{error && <p className="form-error">{error}</p>}{message && <p className="form-hint">{message}</p>}<button className="primary-button compact">{t('publishNotice')}</button></form>
    <div className="notice-admin-list">{notices.slice(0, 6).map((notice) => <div className="notice-admin-row" key={notice.id}><span><strong>{notice.title}</strong><small>{notice.status} · {notice.scope}</small></span>{notice.status !== 'ARCHIVED' && <button className="text-button" onClick={() => archive(notice.id)}>{t('archive')}</button>}</div>)}</div>
  </section>
}
