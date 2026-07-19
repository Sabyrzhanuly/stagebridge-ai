export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const utc = !iso.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(iso) ? iso + 'Z' : iso
    return new Date(utc).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}
