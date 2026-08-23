import { Plus, Trash2 } from 'lucide-react'
import { Input } from './ui/Input'
import { Button } from './ui/Button'

export interface GlossaryRow {
  id: string
  term: string
  translation: string
}

interface GlossaryEditorProps {
  rows: GlossaryRow[]
  onChange: (rows: GlossaryRow[]) => void
}

export function GlossaryEditor({ rows, onChange }: GlossaryEditorProps) {
  function updateRow(id: string, field: 'term' | 'translation', value: string) {
    onChange(rows.map((row) => (row.id === id ? { ...row, [field]: value } : row)))
  }

  function addRow() {
    onChange([...rows, { id: crypto.randomUUID(), term: '', translation: '' }])
  }

  function removeRow(id: string) {
    onChange(rows.filter((row) => row.id !== id))
  }

  return (
    <div className="flex flex-col gap-2">
      {rows.length > 0 && (
        <div className="grid grid-cols-[1fr_1fr_auto] gap-2 text-xs font-medium text-muted-foreground">
          <span>Término</span>
          <span>Traducción fija</span>
          <span />
        </div>
      )}
      {rows.map((row) => (
        <div key={row.id} className="grid grid-cols-[1fr_1fr_auto] gap-2">
          <Input
            value={row.term}
            onChange={(e) => updateRow(row.id, 'term', e.target.value)}
            placeholder="p. ej. Prosodia"
          />
          <Input
            value={row.translation}
            onChange={(e) => updateRow(row.id, 'translation', e.target.value)}
            placeholder="p. ej. Prosodia"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => removeRow(row.id)}
            aria-label="Eliminar término"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        onClick={addRow}
      >
        <Plus className="h-4 w-4" />
        Agregar término
      </Button>
    </div>
  )
}
