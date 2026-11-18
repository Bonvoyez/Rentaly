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
    serial: status === 'ERROR' ? '—' : '인식 완료',
    aiResult: status === 'ERROR' ? '촬영 실패' : status === 'PASS' ? '이상 없음' : '결함 의심',
    status,
  }
})

let devices: readonly DeviceRecord[] = [
  { id: 'station-01', location: '공학관 1층 반납대', status: 'ONLINE', lastSeen: '방금 전', inspectionsToday: 18, firmware: 'v1.4.2' },
  { id: 'station-02', location: '도서관 로비', status: 'INSPECTING', lastSeen: '12초 전', inspectionsToday: 14, firmware: 'v1.4.2' },
  { id: 'station-03', location: '창업지원관 2층', status: 'OFFLINE', lastSeen: '18분 전', inspectionsToday: 5, firmware: 'v1.3.9' },
  { id: 'station-04', location: '전자정보관 B1', status: 'MAINTENANCE', lastSeen: '2시간 전', inspectionsToday: 0, firmware: 'v1.4.1' },
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
    devices = devices.map((device) => device.id === id ? { ...device, status, lastSeen: status === 'ONLINE' ? '방금 전' : device.lastSeen } : device)
    return devices
  },
}
