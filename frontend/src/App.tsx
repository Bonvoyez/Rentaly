import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { z } from 'zod'
import { AdminShell } from './features/admin/AdminShell'
import { ForbiddenPage } from './features/admin/ForbiddenPage'
import { DeviceManagementPage } from './features/admin/DeviceManagementPage'
import { InspectionDetailPage } from './features/admin/InspectionDetailPage'
import { InspectionListPage } from './features/admin/InspectionListPage'
import { LoginPage } from './features/admin/LoginPage'
import { KioskPage } from './features/kiosk/KioskPage'
import { LiveInspectionDetail } from './features/admin/LiveInspectionDetail'

const appModeSchema = z.enum(['kiosk', 'admin', 'combined']).optional()

function readAppMode() {
  return appModeSchema.parse(import.meta.env.VITE_APP_MODE) ?? 'combined'
}

function App() {
  const appMode = readAppMode()
  const kioskEnabled = appMode !== 'admin'
  const adminEnabled = appMode !== 'kiosk'
  const homePath = appMode === 'kiosk' ? '/kiosk' : appMode === 'admin' ? '/admin/login' : '/admin/inspections'

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to={homePath} replace />} />
        {kioskEnabled ? <Route path="/kiosk" element={<KioskPage />} /> : null}
        {adminEnabled ? <>
          <Route path="/admin/login" element={<LoginPage live={appMode === 'admin'} />} />
          <Route path="/admin/forbidden" element={<ForbiddenPage />} />
          <Route path="/admin" element={<AdminShell live={appMode === 'admin'} />}>
            <Route index element={<Navigate to="inspections" replace />} />
            <Route path="inspections" element={<InspectionListPage live={appMode === 'admin'} />} />
            <Route path="inspections/:inspectionId" element={appMode === 'admin' ? <LiveInspectionDetail /> : <InspectionDetailPage />} />
            <Route path="devices" element={<DeviceManagementPage />} />
          </Route>
          <Route path="/admin/*" element={<Navigate to="/admin/login" replace />} />
        </> : null}
        <Route path="*" element={<Navigate to={homePath} replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
