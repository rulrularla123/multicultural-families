export type View =
  | { name: 'home' }
  | { name: 'chat'; analysisId?: string; q?: string }
  | { name: 'provision'; id: string }
  | { name: 'newDocument' }
  | { name: 'document'; id: string }
  | { name: 'myDocuments' }

export function sameView(a: View, b: View): boolean {
  if (a.name !== b.name) return false
  if (a.name === 'provision' && b.name === 'provision') return a.id === b.id
  if (a.name === 'document' && b.name === 'document') return a.id === b.id
  return true
}
