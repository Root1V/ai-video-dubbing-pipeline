import { Captions, Image as ImageIcon, Mic, Music, Type, Volume2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import type { EditorTool } from './types'

const TOOLS: { id: EditorTool; label: string; icon: LucideIcon }[] = [
  { id: 'image', label: 'Imagen', icon: ImageIcon },
  { id: 'text', label: 'Texto', icon: Type },
  { id: 'narration', label: 'Narración', icon: Mic },
  { id: 'voice', label: 'Voz', icon: Volume2 },
  { id: 'music', label: 'Música', icon: Music },
  { id: 'subtitles', label: 'Subtítulos', icon: Captions },
]

interface EditorLeftToolbarProps {
  activeTool: EditorTool
  onSelect: (tool: EditorTool) => void
}

/** Riel vertical de herramientas del editor -- cada icono cambia que panel
 * se muestra a la derecha (EditorRightPanel). Mismo criterio visual del
 * item activo que Sidebar.tsx (bg-primary/10 text-primary). */
export function EditorLeftToolbar({ activeTool, onSelect }: EditorLeftToolbarProps) {
  return (
    <nav className="flex w-[72px] shrink-0 flex-col items-center gap-1 border-r border-border bg-card py-4">
      {TOOLS.map((tool) => (
        <button
          key={tool.id}
          type="button"
          onClick={() => onSelect(tool.id)}
          className={cn(
            'flex w-16 flex-col items-center gap-1 rounded-xl py-2.5 text-[11px] font-medium transition-colors',
            activeTool === tool.id
              ? 'bg-primary/10 text-primary'
              : 'text-muted-foreground hover:bg-secondary/50',
          )}
        >
          <tool.icon className="h-5 w-5" />
          {tool.label}
        </button>
      ))}
    </nav>
  )
}
