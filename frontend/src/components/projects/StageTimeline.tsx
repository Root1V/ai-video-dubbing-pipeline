import { Check, Loader2, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { getStageLabel } from '../../lib/labels'
import type { ProjectStage, ProjectStatus } from '../../types/project'

interface StageTimelineProps {
  /** Full predicted stage plan for this project (see getExpectedStageNames),
   * shown upfront so the user sees every step before it happens, not just
   * the ones that already ran. */
  expectedStageNames: string[]
  stages: ProjectStage[]
  currentStageName?: string | null
  dbStatus: ProjectStatus
}

type StepState = 'done' | 'active' | 'failed' | 'pending'

interface Step {
  key: string
  label: string
  state: StepState
  seconds?: number
}

function formatDuration(seconds: number | undefined): string | null {
  if (seconds === undefined) return null
  if (seconds < 1) return '<1s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes}m ${rest}s`
}

function buildSteps(
  expectedStageNames: string[],
  realStages: ProjectStage[],
  currentStageName: string | null | undefined,
  dbStatus: ProjectStatus,
): Step[] {
  const realByName = new Map(realStages.map((stage) => [stage.name, stage]))

  const steps: Step[] = expectedStageNames.map((name) => {
    const real = realByName.get(name)
    const seconds = typeof real?.seconds === 'number' ? real.seconds : undefined
    if (real) {
      return { key: name, label: getStageLabel(name), state: 'done', seconds }
    }
    if (name === currentStageName) {
      return { key: name, label: getStageLabel(name), state: 'active' }
    }
    return { key: name, label: getStageLabel(name), state: 'pending' }
  })

  // Real stages the predicted plan didn't anticipate (config mismatch, or a
  // future pipeline stage this list doesn't know about yet) still show up,
  // appended at the end, rather than silently disappearing.
  for (const real of realStages) {
    if (!expectedStageNames.includes(real.name)) {
      steps.push({
        key: real.name,
        label: getStageLabel(real.name),
        state: 'done',
        seconds: typeof real.seconds === 'number' ? real.seconds : undefined,
      })
    }
  }
  if (currentStageName && !steps.some((step) => step.key === currentStageName)) {
    steps.push({ key: currentStageName, label: getStageLabel(currentStageName), state: 'active' })
  }

  // On failure, the stage right after the last completed one is the most
  // likely point of failure (it either errored mid-run or never got a
  // chance to start) -- mark just that one as failed and leave the rest
  // visibly pending, so it's clear both where it broke and what never ran.
  if (dbStatus === 'failed') {
    const firstPendingIndex = steps.findIndex((step) => step.state === 'pending')
    if (firstPendingIndex !== -1) {
      steps[firstPendingIndex] = { ...steps[firstPendingIndex], state: 'failed' }
    }
  }

  return steps
}

const CIRCLE_BASE =
  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-medium'

const CIRCLE_STATE: Record<StepState, string> = {
  done: 'border-primary bg-primary text-primary-foreground',
  active: 'border-primary bg-primary/10 text-primary',
  failed: 'border-destructive bg-destructive text-destructive-foreground',
  pending: 'border-border bg-background text-muted-foreground',
}

const LABEL_STATE: Record<StepState, string> = {
  done: 'text-foreground',
  active: 'font-semibold text-primary',
  failed: 'font-semibold text-destructive',
  pending: 'text-muted-foreground',
}

const LINE_STATE: Record<StepState, string> = {
  done: 'bg-primary',
  active: 'bg-primary/30',
  failed: 'bg-destructive/30',
  pending: 'bg-border',
}

export function StageTimeline({
  expectedStageNames,
  stages,
  currentStageName,
  dbStatus,
}: StageTimelineProps) {
  const steps = buildSteps(expectedStageNames, stages, currentStageName, dbStatus)

  return (
    <ol className="flex flex-col">
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1
        const duration = formatDuration(step.seconds)
        return (
          <li key={step.key} className="relative flex gap-4 pb-8 last:pb-0">
            {!isLast && (
              <span
                aria-hidden
                className={cn(
                  'absolute left-4 top-8 h-[calc(100%-1.5rem)] w-0.5 -translate-x-1/2',
                  LINE_STATE[step.state],
                )}
              />
            )}
            <span className={cn(CIRCLE_BASE, CIRCLE_STATE[step.state])}>
              {step.state === 'done' && <Check className="h-4 w-4" />}
              {step.state === 'active' && <Loader2 className="h-4 w-4 animate-spin" />}
              {step.state === 'failed' && <X className="h-4 w-4" />}
              {step.state === 'pending' && <span className="h-2 w-2 rounded-full bg-current" />}
            </span>
            <div className="flex flex-1 items-center justify-between pt-1">
              <span className={cn('text-sm', LABEL_STATE[step.state])}>{step.label}</span>
              {duration && <span className="text-xs text-muted-foreground">{duration}</span>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
