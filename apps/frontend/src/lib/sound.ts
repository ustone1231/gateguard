// api-contract.md §4-C-2: severity별 알림음
// info: 짧은 비프, warning: 두 번, critical: 사이렌 톤

function beep(frequency: number, duration: number, delay = 0) {
  const ctx = new AudioContext()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.frequency.value = frequency
  gain.gain.setValueAtTime(0.3, ctx.currentTime + delay)
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + duration)
  osc.start(ctx.currentTime + delay)
  osc.stop(ctx.currentTime + delay + duration)
}

export function playAlert(severity: 'info' | 'warning' | 'critical') {
  try {
    if (severity === 'info') {
      beep(880, 0.2)
    } else if (severity === 'warning') {
      beep(880, 0.2, 0)
      beep(880, 0.2, 0.3)
    } else {
      // critical: 사이렌 톤 (주파수 교차)
      beep(1200, 0.4, 0)
      beep(800,  0.4, 0.45)
      beep(1200, 0.4, 0.9)
    }
  } catch {
    // 브라우저 정책으로 재생 불가한 경우 무시
  }
}
