// useInkSplash —— 全局墨迹点击粒子（PlayPage 抽离）
// 点击时按当前背景 atmo 主题色生成：水面细波扩散 + 中央落点微光 + 弧线飞溅的亮墨滴。
// 粒子 append 到 document.body（因此样式必须全局，见 src/styles/ink-splash.css）。
import '../styles/ink-splash.css'

const SPLASH_COLORS: Record<string, { edge: string; flash: string; drop: string }> = {
  '雨夜沉静': { edge: '#a8d4ec', flash: '#e2f3ff', drop: '#9cc8e2' },
  '荒野苍茫': { edge: '#dcbc90', flash: '#f7e8cd', drop: '#c6a475' },
  '战火远方': { edge: '#ff9a68', flash: '#ffddc5', drop: '#e87d50' },
  '洛阳暗巷': { edge: '#e6c97a', flash: '#fff0c4', drop: '#cfb060' },
  '水墨山岚': { edge: '#c6d6de', flash: '#f0f6f9', drop: '#a9bcc5' },
  '破晓行军': { edge: '#e6c97a', flash: '#fff0c4', drop: '#cfb060' },
  '竹林清幽': { edge: '#a7c997', flash: '#e8f2e1', drop: '#8ab07c' },
  '黄河怒涛': { edge: '#e7c27c', flash: '#fff3c8', drop: '#d4ac6e' },
  '帐中暖光': { edge: '#ffc65e', flash: '#fff3ce', drop: '#eab353' },
  '雪夜孤城': { edge: '#ecf5fb', flash: '#ffffff', drop: '#d2e4f0' },
  '星空原野': { edge: '#deeaf4', flash: '#f5faff', drop: '#c9d9e8' },
  '血色残阳': { edge: '#db6a50', flash: '#ffd5c5', drop: '#b24e3a' },
}

const BASE = 220
const WAVES = [
  { from: 0.1,  delay: 0,   dur: 0.8 },
  { from: 0.45, delay: 130, dur: 0.95 },
  { from: 0.75, delay: 260, dur: 1.1 },
]

export function useInkSplash(getAtmo: () => string) {
  function inkSplash(e: PointerEvent) {
    // 系统减弱动态效果时静默跳过：粒子是纯装饰，不值得触犯无障碍偏好
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    // 文本输入/文本域不触发（避免干扰打字）
    const t = e.target as HTMLElement | null
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
    const x = e.clientX
    const y = e.clientY
    // 当前背景主题色：溅色随 atmo 背景绑定
    const pal = SPLASH_COLORS[getAtmo()] ?? SPLASH_COLORS['雨夜沉静']

    // 节点自移除：animationend 主通道 + setTimeout 兜底（tab 隐藏/动画被抑制时也能清掉）
    const selfRemove = (node: HTMLElement, ms: number) => {
      node.addEventListener('animationend', () => node.remove())
      setTimeout(() => node.remove(), ms)
    }

    // 1) 水面细波：3 圈薄亮缘，指数外扩、先亮后淡（克制，不糊）
    for (const w of WAVES) {
      const wave = document.createElement('span')
      wave.className = 'click-wave'
      wave.style.left = x + 'px'
      wave.style.top = y + 'px'
      wave.style.width = wave.style.height = BASE + 'px'
      wave.style.setProperty('--ws', String(w.from))
      wave.style.setProperty('--wdur', w.dur + 's')
      wave.style.setProperty('--wdelay', w.delay + 'ms')
      wave.style.setProperty('--s-edge', pal.edge)
      document.body.appendChild(wave)
      selfRemove(wave, w.delay + w.dur * 1000 + 200)
    }

    // 2) 中央落点微光：轻闪一下即散（不是浓晕）
    const flash = document.createElement('span')
    flash.className = 'click-flash'
    flash.style.left = x + 'px'
    flash.style.top = y + 'px'
    flash.style.setProperty('--s-flash', pal.flash)
    document.body.appendChild(flash)
    selfRemove(flash, 600)

    // 3) 墨滴飞溅：细而密的青白水珠，上抛弧线下落，微光晕精致克制
    for (let i = 0; i < 16; i++) {
      const d = document.createElement('span')
      d.className = 'click-drop'
      const angle = (Math.PI * 2 * i) / 16 + (Math.random() - 0.5) * 0.8
      const dist = 26 + Math.random() * 46
      // toFixed(2)：避免极小的 cos/sin 序列化成指数记法（1e-15px 是非法 CSS 长度，
      // 该声明会被丢弃，墨滴原地淡出而不飞）
      d.style.setProperty('--dx', `${(Math.cos(angle) * dist).toFixed(2)}px`)
      d.style.setProperty('--dy', `${(Math.sin(angle) * dist).toFixed(2)}px`)
      d.style.setProperty('--sag', `${dist * 0.35 + 6}px`)
      d.style.setProperty('--s-drop', pal.drop)
      d.style.left = x + 'px'
      d.style.top = y + 'px'
      d.style.width = d.style.height = `${3 + Math.random() * 3}px`
      d.style.background = `radial-gradient(circle at 35% 30%, color-mix(in srgb, white 40%, ${pal.drop}), ${pal.drop})`
      document.body.appendChild(d)
      selfRemove(d, 900)
    }
  }

  return { inkSplash, SPLASH_COLORS }
}
