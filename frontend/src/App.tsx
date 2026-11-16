import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AdminShell } from './features/admin/AdminShell'
import { ForbiddenPage } from './features/admin/ForbiddenPage'
import { DeviceManagementPage } from './features/admin/DeviceManagementPage'
import { InspectionDetailPage } from './features/admin/InspectionDetailPage'
import { InspectionListPage } from './features/admin/InspectionListPage'
import { LoginPage } from './features/admin/LoginPage'
import { KioskPage } from './features/kiosk/KioskPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/kiosk" replace />} />
        <Route path="/kiosk" element={<KioskPage />} />
        <Route path="/admin/login" element={<LoginPage />} />
        <Route path="/admin/forbidden" element={<ForbiddenPage />} />
        <Route path="/admin" element={<AdminShell />}>
          <Route index element={<Navigate to="inspections" replace />} />
          <Route path="inspections" element={<InspectionListPage />} />
          <Route path="inspections/:inspectionId" element={<InspectionDetailPage />} />
          <Route path="devices" element={<DeviceManagementPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/kiosk" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
