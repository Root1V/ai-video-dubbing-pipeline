import axios from 'axios'

interface FastApiValidationError {
  msg: string
}

/**
 * FastAPI puts a plain string in `detail` for a manually raised
 * HTTPException, but a LIST of validation-error objects for an automatic
 * 422 (Pydantic body validation) -- rendering that list directly as a
 * string crashes React ("Objects are not valid as a React child"). This
 * normalizes both shapes into a single display string.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback
  const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === 'object' && 'msg' in item
          ? String((item as FastApiValidationError).msg)
          : null,
      )
      .filter((msg): msg is string => Boolean(msg))
    if (messages.length > 0) return messages.join(' ')
  }
  return fallback
}
