import { createSlice } from '@reduxjs/toolkit'
import { clearStoredAuth, getStoredAuth, storeAuth } from '../../api'

const saved = getStoredAuth()

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: saved?.user || null,
    accessToken: saved?.access_token || null,
    loading: false,
    initialized: Boolean(saved),
    error: null,
  },
  reducers: {
    authRequested(state) {
      state.loading = true
      state.error = null
    },
    authSucceeded(state, action) {
      const auth = action.payload
      state.user = auth.user
      state.accessToken = auth.access_token
      state.loading = false
      state.initialized = true
      state.error = null
      storeAuth(auth)
    },
    authFailed(state, action) {
      state.loading = false
      state.initialized = true
      state.error = action.payload
    },
    signedOut(state) {
      state.user = null
      state.accessToken = null
      state.initialized = true
      state.error = null
      clearStoredAuth()
    },
    authInitialized(state) {
      state.initialized = true
    },
    authIdle(state) {
      state.loading = false
      state.error = null
      state.initialized = true
    },
  },
})

export const { authRequested, authSucceeded, authFailed, signedOut, authInitialized, authIdle } = authSlice.actions
export default authSlice.reducer