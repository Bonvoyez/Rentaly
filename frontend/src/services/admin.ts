import type { DeviceRecord, DeviceStatus, FinalStatus, InspectionRecord } from '../domain/inspection'

export type AuthResult = { readonly kind: 'success'; readonly displayName: string } | { readonly kind: 'invalid-credentials' }

const statuses = ['PENDING_REVIEW', 'PASS', 'PASS', 'ERROR', 'PASS', 'FAIL', 'PASS'] as const satisfies readonly FinalStatus[]
const records: readonly InspectionRecord[] = Array.from({ length: 27 }, (_, index) => {
  const status = statuses[index % statuses.length] ?? 'PASS'
  const minute = 22 - (index * 3) % 60
  return {
    id: `${(index + 11).toString(16)}b2c4d91...${(0x1b90 + index * 17).toString(16).slice(-4)}`,
    device: `RPi-BOARD-${String((index % 4) + 1).padStart(3, '0')}`,
    inspectedAt: `2026.10.${String(21 - Math.floor(index / 15)).padStart(2, '0')} 14:${String((minute + 60) % 60).padStart(2, '0')}`,
    serial: status === 'ERROR' ? '—' : 'Verified',
    aiResult: status === 'ERROR' ? 'Capture failed' : status === 'PASS' ? 'No defects' : 'Defect suspected',
    status,
  }
})

let devices: readonly DeviceRecord[] = [
  { id: 'station-01', location: 'Engineering Bldg 1F Station', status: 'ONLINE', lastSeen: 'Just now', inspectionsToday: 18, firmware: 'v1.4.2' },
  { id: 'station-02', location: 'Library Lobby', status: 'INSPECTING', lastSeen: '12s ago', inspectionsToday: 14, firmware: 'v1.4.2' },
  { id: 'station-03', location: 'Startup Center 2F', status: 'OFFLINE', lastSeen: '18m ago', inspectionsToday: 5, firmware: 'v1.3.9' },
  { id: 'station-04', location: 'Electronics Bldg B1', status: 'MAINTENANCE', lastSeen: '2h ago', inspectionsToday: 0, firmware: 'v1.4.1' },
]

export const adminService = {
  async login(id: string, password: string): Promise<AuthResult> {
    await Promise.resolve()
    return id === 'admin' && password === 'admin' ? { kind: 'success', displayName: 'admin0301' } : { kind: 'invalid-credentials' }
  },
  async list(): Promise<readonly InspectionRecord[]> { await Promise.resolve(); return records },
  async listDevices(): Promise<readonly DeviceRecord[]> { await Promise.resolve(); return devices },
  async setDeviceStatus(id: string, status: DeviceStatus): Promise<readonly DeviceRecord[]> {
    await Promise.resolve()
    devices = devices.map((device) => device.id === id ? { ...device, status, lastSeen: status === 'ONLINE' ? 'Just now' : device.lastSeen } : device)
    return devices
  },
}
