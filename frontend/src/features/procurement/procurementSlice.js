import { createSlice } from '@reduxjs/toolkit'

const procurementSlice = createSlice({
  name: 'procurement',
  initialState: {
    active: null,
    notifications: [],
    documents: [],
    loading: false,
    error: null,
    connection: 'offline',
  },
  reducers: {
    procurementRequested(state) {
      state.loading = true
      state.error = null
    },
    procurementLoaded(state, action) {
      state.active = action.payload
      state.loading = false
      state.error = null
    },
    procurementFailed(state, action) {
      state.loading = false
      state.error = action.payload
    },
    notificationsLoaded(state, action) {
      state.notifications = action.payload
    },
    notificationRead(state, action) {
      const notification = state.notifications.find((item) => item.id === action.payload)
      if (notification) notification.is_read = true
    },
    documentsLoaded(state, action) {
      state.documents = action.payload
    },
    procurementConnectionChanged(state, action) {
      state.connection = action.payload
    },
  },
})

export const {
  procurementRequested,
  procurementLoaded,
  procurementFailed,
  notificationsLoaded,
  notificationRead,
  documentsLoaded,
  procurementConnectionChanged,
} = procurementSlice.actions

export default procurementSlice.reducer