import { configureStore } from '@reduxjs/toolkit'
import queueReducer from './features/queue/queueSlice'
import authReducer from './features/auth/authSlice'
import procurementReducer from './features/procurement/procurementSlice'

export const store = configureStore({
  reducer: {
    queue: queueReducer,
    auth: authReducer,
    procurement: procurementReducer,
  },
})
