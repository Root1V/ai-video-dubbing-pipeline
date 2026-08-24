/**
 * Splits a decoded AudioBuffer into `barCount` equal time segments and
 * computes each segment's RMS amplitude (root-mean-square, a better proxy
 * for perceived loudness than a raw peak/max sample -- one stray spike
 * doesn't make a whole segment look artificially tall). Normalizes the
 * result so the loudest segment reaches 1.0, the same `normalize: true`
 * convention the static wavesurfer waveform already uses, so both visuals
 * read on the same scale.
 */
export function computeAmplitudeEnvelope(buffer: AudioBuffer, barCount: number): number[] {
  const channelData = buffer.getChannelData(0)
  const segmentSize = Math.max(1, Math.floor(channelData.length / barCount))
  const rmsValues: number[] = []

  for (let i = 0; i < barCount; i++) {
    const start = i * segmentSize
    const end = i === barCount - 1 ? channelData.length : start + segmentSize
    let sumSquares = 0
    let count = 0
    for (let j = start; j < end; j++) {
      sumSquares += channelData[j] * channelData[j]
      count++
    }
    rmsValues.push(count > 0 ? Math.sqrt(sumSquares / count) : 0)
  }

  const max = Math.max(...rmsValues, 1e-6)
  return rmsValues.map((v) => v / max)
}
