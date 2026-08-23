import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

export function ComingSoonPage({ title }: { title: string }) {
  const navigate = useNavigate()

  return (
    <div className="flex h-full items-center justify-center">
      <Card className="max-w-md">
        <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles className="h-6 w-6" />
          </div>
          <h1 className="text-lg font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">
            Este servicio estará disponible próximamente.
          </p>
          <Button variant="outline" onClick={() => navigate('/')}>
            Volver al inicio
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
