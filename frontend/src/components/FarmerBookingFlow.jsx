import { useEffect, useMemo, useState } from 'react'
import { apiFetch, getStoredAuth } from '../api'
import { useLanguage } from '../i18n'

const initialForm = { farmer_phone: getStoredAuth()?.user?.phone || '', crop_type: 'Wheat', expected_tonnage: '' }

export default function FarmerBookingFlow({ onTrack, user, onContextChange }) {
  const { t } = useLanguage()
  const [districts, setDistricts] = useState([])
  const [mandis, setMandis] = useState([])
  const [slots, setSlots] = useState([])
  const [selectedDistrict, setSelectedDistrict] = useState('')
  const [selectedMandi, setSelectedMandi] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [form, setForm] = useState(initialForm)
  const [msp, setMsp] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState('')
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiFetch('/api/districts').then(setDistricts).catch((reason) => setError(reason.message))
    setForm((current) => ({ ...current, farmer_phone: user?.phone || current.farmer_phone }))
  }, [user])
  useEffect(() => {
    setSelectedMandi(''); setSlots([])
    setSelectedDate('')
    if (!selectedDistrict) { setMandis([]); return }
    apiFetch(`/api/mandis/district/${encodeURIComponent(selectedDistrict)}`).then(setMandis).catch((reason) => setError(reason.message))
  }, [selectedDistrict])
  useEffect(() => { onContextChange?.({ district: selectedDistrict, centerId: selectedMandi }) }, [selectedDistrict, selectedMandi, onContextChange])
  useEffect(() => {
    if (!selectedMandi) { setSlots([]); return }
    setSelectedSlot('')
    apiFetch(`/api/mandis/${selectedMandi}/slots`).then(setSlots).catch((reason) => setError(reason.message))
  }, [selectedMandi])
  useEffect(() => {
    setMsp(null)
    apiFetch(`/api/crops/${encodeURIComponent(form.crop_type)}/msp`).then(setMsp).catch((reason) => setError(reason.message))
  }, [form.crop_type])

  const center = useMemo(() => mandis.find((item) => String(item.id) === String(selectedMandi)), [mandis, selectedMandi])
  const availableDates = useMemo(() => [...new Set(slots.map((slot) => slot.date))], [slots])
  const dateSlots = useMemo(() => slots.filter((slot) => !selectedDate || slot.date === selectedDate), [slots, selectedDate])
  function updateField(event) { setForm((current) => ({ ...current, [event.target.name]: event.target.value })) }

  async function submitBooking(event) {
    event.preventDefault(); setError(''); setBooking(null); setLoading(true)
    try {
      const result = await apiFetch(`/api/slots/${selectedSlot}/book`, { method: 'POST', body: JSON.stringify({ ...form, expected_tonnage: Number(form.expected_tonnage) }) })
      setBooking(result); setForm(initialForm)
    } catch (reason) { setError(reason.message) } finally { setLoading(false) }
  }

  return (
    <section className="booking-layout">
      <div className="section-intro"><p className="eyebrow">{t('findCenter')}</p><h2>{t('reserveWindow')}</h2><p className="muted-copy">{t('bookingIntro')}</p>
        <div className="center-list">{mandis.map((item) => <button type="button" key={item.id} className={`center-option ${String(item.id) === String(selectedMandi) ? 'active' : ''}`} onClick={() => setSelectedMandi(item.id)}><strong>{item.name}</strong><span>{item.location}</span><small>{item.available_crops?.slice(0, 3).join(' · ') || t('supportedCrops')}</small></button>)}</div>
      </div>
      <form className="form-panel" onSubmit={submitBooking}>
        <label>{t('mobile')}<input name="farmer_phone" value={form.farmer_phone} onChange={updateField} placeholder="+91 98765 43210" required minLength="7" /></label>
        <div className="form-grid"><label>{t('district')}<select value={selectedDistrict} onChange={(event) => setSelectedDistrict(event.target.value)} required><option value="">{t('chooseDistrict')}</option>{districts.map((district) => <option key={district} value={district}>{district}</option>)}</select></label><label>{t('procurementCenter')}<select value={selectedMandi} onChange={(event) => setSelectedMandi(event.target.value)} required disabled={!selectedDistrict}><option value="">{selectedDistrict ? t('chooseCenter') : t('chooseDistrict')}</option>{mandis.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
        {center && <div className="center-facts"><strong>{center.name}</strong><span>{center.location} · {t('capacity')}: {center.daily_capacity_quintals || center.hourly_capacity} quintals/day</span><small>{t('operatingHours')}: {center.procurement_window_start?.slice(0, 5) || '08:00'}–{center.procurement_window_end?.slice(0, 5) || '16:00'}</small></div>}
        <div className="form-grid"><label>{t('crop')}<select name="crop_type" value={form.crop_type} onChange={updateField}>{Object.entries(t('crops')).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>{t('quintals')}<input name="expected_tonnage" type="number" min="0.001" step="0.001" value={form.expected_tonnage} onChange={updateField} placeholder="40" required /></label></div>
        {msp && <div className="center-facts"><span>{t('msp')}: <strong>₹{Number(msp.msp).toLocaleString('en-IN')} {t('perQuintal')}</strong></span><span>{t('indicativeValue')}: <strong>₹{(Number(form.expected_tonnage || 0) * Number(msp.msp)).toLocaleString('en-IN')}</strong></span></div>}
        <div className="form-grid"><label>{t('date')}<select value={selectedDate} onChange={(event) => { setSelectedDate(event.target.value); setSelectedSlot('') }} required disabled={!selectedMandi}><option value="">{selectedMandi ? t('date') : t('chooseCenter')}</option>{availableDates.map((date) => <option key={date} value={date}>{date}</option>)}</select></label><label>{t('mandiSlot')}<select value={selectedSlot} onChange={(event) => setSelectedSlot(event.target.value)} required disabled={!selectedDate}><option value="">{selectedDate ? t('chooseSlot') : t('date')}</option>{dateSlots.map((slot) => { const remaining = Number(slot.max_tonnage) - Number(slot.booked_tonnage); return <option key={slot.id} value={slot.id}>{slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)} · {remaining.toFixed(1)} {t('quintalsLeft')}</option> })}</select></label></div>
        {selectedMandi && !slots.length && <p className="form-hint">{t('noSlots')}</p>}{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button" disabled={loading || !selectedSlot}>{loading ? t('booking') : t('confirmBooking')}</button>
      </form>
      {booking && <div className="booking-success"><div><p className="eyebrow">{t('bookingConfirmed')}</p><h3>{t('showToken')}</h3><p className="muted-copy">{t('appName')} · {booking.crop_type} · {booking.expected_tonnage} quintals</p></div><div className="token-ticket"><span>{t('arrivalToken')}</span><strong>{booking.token_code}</strong><small>{center?.name || t('procurementCenter')}</small></div><button className="primary-button track-button" onClick={() => onTrack?.()}>{t('trackProcurement')} <span>→</span></button></div>}
    </section>
  )
}
