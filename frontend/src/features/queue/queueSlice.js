import { createSlice } from '@reduxjs/toolkit'

const queueSlice = createSlice({
  name: 'queue',
  initialState: {
    tokens: [],
    loading: false,
    error: null,
    connection: 'offline',
  },
  reducers: {
    tokensRequested(state) {
      state.loading = true
      state.error = null
    },
    tokensLoaded(state, action) {
      state.tokens = action.payload
      state.loading = false
    },
    tokensFailed(state, action) {
      state.loading = false
      state.error = action.payload
    },
    tokenStatusChanged(state, action) {
      const incoming = action.payload
      const index = state.tokens.findIndex((token) => token.id === incoming.id)
      if (index === -1) state.tokens.unshift(incoming)
      else state.tokens[index] = { ...state.tokens[index], ...incoming }
    },
    connectionChanged(state, action) {
      state.connection = action.payload
    },
  },
})

export const {
  tokensRequested,
  tokensLoaded,
  tokensFailed,
  tokenStatusChanged,
  connectionChanged,
} = queueSlice.actions

export default queueSlice.reducer
