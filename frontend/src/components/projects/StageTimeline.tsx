import { useEffect, useRef, useState } from 'react'
import { Check, Loader2, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { formatSecondsDuration, formatTime } from '../../lib/format'
import { getStageLabel, getStageSubtitle } from '../../lib/labels'
import type { ProjectStage, ProjectStatus } from '../../types/project'

/** How long a stage stays visually "in progress" after we first notice it's
 * done, so short stages (a few seconds or less) still get a moment of
 * spinner feedback instead of jumping straight from pending to a checkmark
 * -- with a 3s poll interval, a short stage can easily finish between two
 * polls and never get sampled while actually active. Purely cosmetic: it
 * doesn't delay real data, just how long the checkmark takes to appear. */
const REVEAL_DELAY_MS = 700

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
  subtitle?: string | null
}

/** `rendering_dubbed`'s own timer in translate_video.py wraps the whole
 * dubbed-rendering block, which internally times tts_synthesis and
 * audio_mixing_and_muxing AGAIN as their own stage entries -- so its
 * reported `seconds` includes theirs, not just the final mux step (a 2min
 * clip's "rendering_dubbed: 4m" is really ~4s of actual muxing plus the
 * ~4min TTS/mixing already shown as separate steps). Subtract the nested
 * children's time to show this step's own real, non-overlapping duration. */
const NESTED_STAGE_CHILDREN: Record<string, string[]> = {
  rendering_dubbed: ['tts_synthesis', 'audio_mixing_and_muxing'],
}

function resolveOwnSeconds(
  stage: ProjectStage,
  realByName: Map<string, ProjectStage>,
): number | undefined {
  if (typeof stage.seconds !== 'number') return undefined
  const children = NESTED_STAGE_CHILDREN[stage.name]
  if (!children) return stage.seconds
  const childrenTotal = children.reduce((sum, childName) => {
    const child = realByName.get(childName)
    return sum + (typeof child?.seconds === 'number' ? child.seconds : 0)
  }, 0)
  return Math.max(0, stage.seconds - childrenTotal)
}

function buildSteps(
  expectedStageNames: string[],
  realStages: ProjectStage[],
  currentStageName: string | null | undefined,
  dbStatus: ProjectStatus,
  revealDelayKeys: Set<string>,
): Step[] {
  const realByName = new Map(realStages.map((stage) => [stage.name, stage]))

  const steps: Step[] = expectedStageNames.map((name) => {
    const real = realByName.get(name)
    if (real) {
      // Held as "active" for a moment even though the backend already
      // reports it done -- see REVEAL_DELAY_MS.
      const state: StepState = revealDelayKeys.has(name) ? 'active' : 'done'
      return {
        key: name,
        label: getStageLabel(name),
        state,
        seconds: resolveOwnSeconds(real, realByName),
        subtitle: getStageSubtitle(real),
      }
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
        state: revealDelayKeys.has(real.name) ? 'active' : 'done',
        seconds: resolveOwnSeconds(real, realByName),
        subtitle: getStageSubtitle(real),
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

  // The first and last steps are the only ones where "when exactly" is more
  // useful than a domain metric -- they mark when the whole run itself
  // started/finished, not just this one stage. Every stage already carries
  // started_at/ended_at; only the first/last actually need showing it.
  const first = steps[0]
  if (first?.state === 'done') {
    const startedAt = realByName.get(first.key)?.started_at
    if (typeof startedAt === 'string') {
      const label = `inicio ${formatTime(startedAt)}`
      first.subtitle = first.subtitle ? `${first.subtitle} · ${label}` : label
    }
  }
  const last = steps[steps.length - 1]
  if (last && last !== first && last.state === 'done') {
    const endedAt = realByName.get(last.key)?.ended_at
    if (typeof endedAt === 'string') {
      const label = `fin ${formatTime(endedAt)}`
      last.subtitle = last.subtitle ? `${last.subtitle} · ${label}` : label
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
  const [revealDelayKeys, setRevealDelayKeys] = useState<Set<string>>(new Set())
  const seenDoneKeys = useRef<Set<string>>(new Set())
  const isFirstRun = useRef(true)

  useEffect(() => {
    const doneKeys = stages.map((stage) => stage.name)
    const newlyDone = doneKeys.filter((key) => !seenDoneKeys.current.has(key))
    doneKeys.forEach((key) => seenDoneKeys.current.add(key))

    // Never fake the "in progress" reveal for stages that were already done
    // the moment this component first mounted (e.g. opening an already-
    // completed or already-failed project) -- only for ones that finish
    // while the user is actually watching.
    if (isFirstRun.current) {
      isFirstRun.current = false
      return
    }
    if (newlyDone.length === 0) return

    setRevealDelayKeys((prev) => new Set([...prev, ...newlyDone]))
    const timers = newlyDone.map((key) =>
      setTimeout(() => {
        setRevealDelayKeys((prev) => {
          const next = new Set(prev)
          next.delete(key)
          return next
        })
      }, REVEAL_DELAY_MS),
    )
    return () => timers.forEach(clearTimeout)
  }, [stages])

  const steps = buildSteps(expectedStageNames, stages, currentStageName, dbStatus, revealDelayKeys)

  return (
    <ol className="flex flex-col">
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1
        const duration = step.seconds === undefined ? null : formatSecondsDuration(step.seconds)
        return (
          <li key={step.key} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast && (
              <span
                aria-hidden
                className={cn(
                  'absolute left-4 top-8 h-[calc(100%-1.25rem)] w-0.5 -translate-x-1/2',
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
            <div className="flex flex-1 items-start justify-between gap-3 pt-1">
              <div className="flex flex-col">
                <span className={cn('text-sm', LABEL_STATE[step.state])}>
                  {index + 1}. {step.label}
                </span>
                {step.subtitle && (
                  <span className="mt-0.5 text-xs text-muted-foreground/80">{step.subtitle}</span>
                )}
              </div>
              {duration && (
                <span className="shrink-0 text-xs text-muted-foreground">{duration}</span>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
