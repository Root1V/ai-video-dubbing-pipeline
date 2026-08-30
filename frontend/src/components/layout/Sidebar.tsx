import { NavLink } from 'react-router-dom'
import {
  AudioLines,
  Captions,
  Clapperboard,
  FileText,
  FolderOpen,
  LayoutGrid,
  Music,
  Sparkles,
  Users,
  Volume2,
} from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { cn } from '../../lib/cn'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutGrid
}

const mainNav: NavItem[] = [{ to: '/', label: 'Inicio', icon: LayoutGrid }]

const servicesNav: NavItem[] = [
  { to: '/dubbing/new', label: 'Doblaje de Video', icon: AudioLines },
  { to: '/subtitles/new', label: 'Subtítulos', icon: Captions },
  { to: '/transcription/new', label: 'Transcripción', icon: FileText },
  { to: '/tts/new', label: 'Voz y Clonación', icon: Volume2 },
  { to: '/micro-video/new', label: 'Micro-Video', icon: Clapperboard },
]

const libraryNav: NavItem[] = [
  { to: '/projects', label: 'Proyectos', icon: FolderOpen },
]

const adminNav: NavItem[] = [
  { to: '/users', label: 'Usuarios', icon: Users },
  { to: '/music-tracks', label: 'Música de fondo', icon: Music },
]

function NavSection({ title, items }: { title?: string; items: NavItem[] }) {
  return (
    <div className="flex flex-col gap-1">
      {title && (
        <span className="px-3 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-sidebar-foreground/50">
          {title}
        </span>
      )}
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground',
            )
          }
        >
          <item.icon className="h-4 w-4" />
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

export function Sidebar() {
  const { user } = useAuth()

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-4 py-6 text-sidebar-foreground">
      <div className="mb-6 flex items-center gap-2 px-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </div>
        <span className="text-lg font-semibold">Prosodia</span>
      </div>

      <nav className="flex flex-1 flex-col gap-4 overflow-y-auto">
        <NavSection items={mainNav} />
        <NavSection title="Servicios" items={servicesNav} />
        <NavSection title="Biblioteca" items={libraryNav} />
        {user?.role === 'admin' && <NavSection title="Administración" items={adminNav} />}
      </nav>
    </aside>
  )
}
