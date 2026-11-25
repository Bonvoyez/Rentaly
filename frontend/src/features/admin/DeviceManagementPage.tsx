import { Activity, MapPin, MoreHorizontal, Power, RotateCcw, Settings2, Wifi, WifiOff } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Button, StatusBadge } from '../../components/ui'
import type { DeviceRecord, DeviceStatus } from '../../domain/inspection'
import { adminService } from '../../services/admin'

const statusView: Readonly<Record<DeviceStatus, { readonly label: string; readonly tone: 'success' | 'warning' | 'error' | 'neutral' }>> = { ONLINE: { label: 'ONLINE', tone: 'success' }, INSPECTING: { label: 'Inspecting', tone: 'warning' }, OFFLINE: { label: 'OFFLINE', tone: 'error' }, MAINTENANCE: { label: 'Maintenance', tone: 'neutral' } }

export function DeviceManagementPage() {
  const [devices, setDevices] = useState<readonly DeviceRecord[]>([])
  const [selected, setSelected] = useState<DeviceRecord | null>(null)
  const [notice, setNotice] = useState('')
  useEffect(() => { void adminService.listDevices().then(setDevices) }, [])
  const updateStatus = async (device: DeviceRecord, status: DeviceStatus) => {
    const updated = await adminService.setDeviceStatus(device.id, status)
    setDevices(updated); setSelected(updated.find((item) => item.id === device.id) ?? null)
    setNotice(`Changed ${device.id} status to ${statusView[status].label}. Reflected in mock session only.`)
  }
  return <section className="min-h-full px-4 pb-8 pt-6 sm:px-6 md:px-10 md:pb-10 md:pt-8"><div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-[28px] font-bold tracking-tight">Device Management</h1><p className="mt-2 text-sm text-secondary dark:text-dark-secondary">Manage inspection station connection status and maintenance mode.</p></div><span className="rounded-full bg-warning-soft px-3 py-1.5 text-xs font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">Mock Device Data</span></div><div className="mt-6 grid gap-3 sm:grid-cols-3 sm:gap-4"><Summary icon={<Wifi />} label="Online" value={devices.filter((device) => device.status === 'ONLINE' || device.status === 'INSPECTING').length} tone="text-success" /><Summary icon={<Activity />} label="Today's Inspections" value={devices.reduce((sum, device) => sum + device.inspectionsToday, 0)} tone="text-primary" /><Summary icon={<WifiOff />} label="Needs Attention" value={devices.filter((device) => device.status === 'OFFLINE' || device.status === 'MAINTENANCE').length} tone="text-danger" /></div>{notice ? <div role="status" className="mt-5 rounded-xl bg-primary-soft px-4 py-3 text-sm text-primary dark:bg-dark-selected">{notice}</div> : null}<div className="mt-6 hidden overflow-x-auto rounded-2xl border sm:block border-line-soft dark:border-dark-line"><table className="w-full min-w-[800px] border-collapse text-left text-sm"><thead className="bg-slate-50 text-xs text-secondary dark:bg-dark-raised dark:text-dark-secondary"><tr><th className="px-5 py-4">Device ID</th><th>Location</th><th>Status</th><th>Last Seen</th><th>Today's Inspections</th><th>Firmware</th><th className="pr-5 text-right">Actions</th></tr></thead><tbody>{devices.map((device) => { const view = statusView[device.status]; return <tr key={device.id} className="border-t border-line-soft dark:border-dark-line"><td className="px-5 py-5 font-semibold">{device.id}</td><td><span className="inline-flex items-center gap-1.5 text-secondary dark:text-dark-secondary"><MapPin className="size-4" />{device.location}</span></td><td><StatusBadge tone={view.tone}>{view.label}</StatusBadge></td><td className="text-secondary dark:text-dark-secondary">{device.lastSeen}</td><td>{device.inspectionsToday}</td><td>{device.firmware}</td><td className="pr-5 text-right"><button type="button" onClick={() => setSelected(device)} aria-label={`Manage ${device.id}`} className="inline-grid size-10 place-items-center rounded-xl text-secondary hover:bg-primary-soft hover:text-primary dark:hover:bg-dark-selected"><MoreHorizontal className="size-5" /></button></td></tr> })}</tbody></table></div><DeviceCards devices={devices} onSelect={setSelected} />{selected ? <aside className="fixed inset-0 z-20 grid place-items-center bg-slate-950/35 p-4" role="dialog" aria-modal="true" aria-labelledby="device-title" onMouseDown={(event) => { if (event.currentTarget === event.target) setSelected(null) }}><div className="w-full max-w-[520px] rounded-2xl bg-white p-5 shadow-2xl sm:p-7 dark:bg-dark-raised"><div className="flex items-start justify-between"><div><span className="text-xs text-primary">Device Management</span><h2 id="device-title" className="mt-1 text-2xl font-bold">{selected.id}</h2><p className="mt-2 text-sm text-secondary dark:text-dark-secondary">{selected.location}</p></div><StatusBadge tone={statusView[selected.status].tone}>{statusView[selected.status].label}</StatusBadge></div><div className="mt-7 grid gap-3 sm:grid-cols-2"><Button onClick={() => void updateStatus(selected, 'ONLINE')}><RotateCcw className="mr-2 inline size-4" />Reconnect</Button><Button tone="secondary" onClick={() => void updateStatus(selected, 'MAINTENANCE')}><Settings2 className="mr-2 inline size-4" />Maintenance Mode</Button><Button tone="secondary" className="text-danger sm:col-span-2" onClick={() => void updateStatus(selected, 'OFFLINE')}><Power className="mr-2 inline size-4" />Disconnect</Button></div><button type="button" onClick={() => setSelected(null)} className="mt-6 min-h-10 w-full text-sm text-secondary dark:text-dark-secondary">Close</button></div></aside> : null}</section>
}

function Summary({ icon, label, value, tone }: { readonly icon: ReactNode; readonly label: string; readonly value: number; readonly tone: string }) {
  return <article className="flex h-28 items-center gap-4 rounded-2xl border border-line-soft p-5 dark:border-dark-line dark:bg-dark-raised"><span className={`grid size-11 place-items-center rounded-xl bg-slate-50 dark:bg-dark-hover ${tone}`}>{icon}</span><div><p className="text-xs text-secondary dark:text-dark-secondary">{label}</p><strong className="text-2xl">{value}</strong></div></article>
}

function DeviceCards({ devices, onSelect }: { readonly devices: readonly DeviceRecord[]; readonly onSelect: (device: DeviceRecord) => void }) {
  return <div className="mt-6 grid gap-3 sm:hidden">
    {devices.map(device => <article key={device.id} className="rounded-2xl border border-line-soft p-4 dark:border-dark-line dark:bg-dark-raised">
      <div className="flex items-start justify-between gap-2"><strong>{device.id}</strong><StatusBadge tone={statusView[device.status].tone}>{statusView[device.status].label}</StatusBadge></div>
      <p className="mt-2 text-xs text-secondary">{device.location}</p>
      <p className="mt-2 text-xs text-secondary">Last seen · {device.lastSeen} / Today · {device.inspectionsToday}</p>
      <Button tone="secondary" className="mt-4 w-full" onClick={() => onSelect(device)}>Manage Device</Button>
    </article>)}
  </div>
}
