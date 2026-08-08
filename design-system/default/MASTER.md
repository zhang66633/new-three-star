# Design System Master File · 新三国 星空

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** 新三国 星空
**Updated:** 2026-08-07
**Category:** Immersive Narrative Game（沉浸式叙事游戏）
**Design Dials:** Variance 7/10 (Bold/Cinematic) | Motion 8/10 (Complex) | Density 4/10 (Spacious/Cinematic)

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable | Usage |
|------|-----|--------------|-------|
| Background | `#050508` | `--space-black` | 主背景（深空底色） |
| Surface | `#0a0a12` | `--space-deep` | 卡片/面板底 |
| Elevated | `#12121e` | `--space-surface` | 悬浮层 |
| Text Primary | `#f0f0f8` | `--text-bright` | 主文字（冷白） |
| Text Body | `#c8c8d8` | `--text-primary` | 正文 |
| Text Muted | `#6a6a80` | `--text-muted` | 次要文字 |
| Accent Gold | `#e8a838` | `--accent-gold` | 主强调色（天意/鎏金） |
| Accent Cinnabar | `#c04030` | `--accent-cinnabar` | 次强调色（朱砂/赤铁/tension-high） |
| Accent Bronze | `#5a7a6a` | `--accent-bronze` | 辅助色（青铜绿/注释/机制引用） |
| Tension Low | `#4a9ea0` | `--tension-low` | 青·顺历史 (0-30) |
| Tension Mid | `#e8a838` | `--tension-mid` | 鎏金·局部干预 (31-70) |
| Tension High | `#c04030` | `--tension-high` | 赤铁·硬干预 (71-100) |
| Panel BG | `rgba(10,10,18,0.92)` | `--panel-bg` | 面板背景 |
| Panel Border | `rgba(160,160,200,0.1)` | `--panel-border` | 面板边框 |

**Color Notes:** 深空冷黑底色 + 鎏金主强调 + 朱砂/青铜辅助。整体如古卷展开于星空之下——冷峻中有暖意，暗沉中见金辉。

### Typography

- **Display Font:** Noto Serif SC（思源宋体）— 标题、章节铭牌、加载画面
- **Body Font:** Noto Serif SC（思源宋体）— 叙事正文、选项、UI文字
- **Mood:** cinematic, immersive, ancient-scroll, dark, premium, restrained-elegance
- **Google Fonts:** [Noto Serif SC + decorative set](https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&family=ZCOOL+KuaiLe&family=Ma+Shan+Zheng&family=ZCOOL+XiaoWei&family=Long+Cang&family=Liu+Jian+Mao+Cao&family=Zhi+Mang+Xing&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&family=ZCOOL+KuaiLe&family=Ma+Shan+Zheng&family=ZCOOL+XiaoWei&family=Long+Cang&family=Liu+Jian+Mao+Cao&family=Zhi+Mang+Xing&display=swap');
```

**Type Scale:**
| Token | Size | Usage |
|-------|------|-------|
| `--text-xs` | `0.65rem` | 标签/辅助 |
| `--text-sm` | `0.82rem` | 记忆条目/效果说明 |
| `--text-base` | `1.05rem` | 叙事正文 |
| `--text-lg` | `1.35rem` | 章节标题 |
| `--text-xl` | `clamp(2.2rem, 5vw, 3.4rem)` | 加载画面标题 |
| `--leading-relaxed` | `2` | 叙事正文行高 |
| `--leading-normal` | `1.6` | UI组件行高 |
| `--tracking-wide` | `0.3em` | 标题字间距 |
| `--tracking-normal` | `0.03em` | 正文微间距 |

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | 紧凑间隔 |
| `--space-sm` | `8px` / `0.5rem` | 选项间距/gap |
| `--space-md` | `16px` / `1rem` | 标准内边距 |
| `--space-lg` | `24px` / `1.5rem` | 区块间距 |
| `--space-xl` | `32px` / `2rem` | 大间距 |
| `--space-2xl` | `48px` / `3rem` | 段落间距 |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 0 14px rgba(202,138,4,0.06)` | 微金辉 |
| `--shadow-md` | `0 0 30px rgba(202,138,4,0.04), inset 0 1px 0 rgba(255,255,255,0.03)` | 面板辉光 |
| `--shadow-lg` | `0 8px 40px rgba(0,0,0,0.5)` | 抽屉/弹层 |
| `--shadow-gold` | `0 0 30px rgba(202,138,4,0.15)` | 标题金辉 |

---

## Component Specs

### Narrative Text

```css
.narrative-text {
  font-family: var(--font-body);
  font-size: 1.05rem;
  line-height: 2;
  letter-spacing: 0.03em;
  color: rgba(248, 250, 252, 0.92);
  text-align: justify;
  white-space: pre-line;
}

/* 玩家视角差异（思绪段落） */
.narrative-text.playerPov {
  color: rgba(202, 138, 4, 0.75);
  font-style: italic;
}
```

### Choice Buttons (选项)

```css
.choice-btn {
  display: flex; align-items: flex-start; gap: 8px;
  background: rgba(15, 15, 30, 0.55);
  border: 1px solid;
  border-left: 3px solid;  /* 左侧粗线 = tension 色彩指示 */
  border-radius: 0 10px 10px 0;
  padding: 8px 14px;
  backdrop-filter: blur(6px);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Tension 三色 */
.tension-low  { border-color: rgba(74, 158, 160, 0.2); border-left-color: #4a9ea0; }  /* 青 */
.tension-mid  { border-color: rgba(232, 168, 56, 0.2); border-left-color: #e8a838; }  /* 鎏金 */
.tension-high { border-color: rgba(192, 64, 48, 0.2);  border-left-color: #c04030; }  /* 赤铁 */
```

### Character Panel (角色状态卡)

```css
.character-panel {
  position: fixed; right: 20px; top: 50%; transform: translateY(-50%);
  width: 150px;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.18);
  border-radius: 14px;
  backdrop-filter: blur(12px);
  z-index: 20;
}
```

### Memory Drawer (记忆抽屉)

```css
.memory-drawer {
  position: fixed; right: 20px; bottom: 64px;
  width: 300px; max-height: 44vh;
  background: rgba(10, 10, 18, 0.94);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 14px;
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}
```

### Cinematic Loader (加载动画)

```css
.cinematic-loader {
  /* 全屏遮罩：深空底色 + 金箔光柱 + 章节标题 + 台词轮播 */
  background: radial-gradient(ellipse at 50% 40%, rgba(15,15,35,0.3) 0%, rgba(5,5,8,0.98) 70%);
}
/* 标题显影：从模糊到清晰（如古卷浮现文字） */
.cinematic-title {
  animation: title-develop 0.9s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes title-develop {
  from { filter: blur(8px); opacity: 0; transform: translateY(16px); }
  to   { filter: blur(0);   opacity: 1; transform: translateY(0); }
}
```

---

## Style Guidelines

**Style:** Cinematic Immersive Narrative（电影史诗感沉浸叙事）

**Keywords:** dark, immersive, cinematic, ancient-scroll, gold-accent, particle-atmosphere, restrained-motion, ink-wash

**Key Effects:**
- 墨染转场（clip-path circle 扩散/收缩，1.2s）
- 金色粒子爆发（选项点击反馈，18粒子径向扩散）
- Stagger 入场动画（选项/记忆条目依次滑入）
- Canvas 粒子氛围层（雨/火/尘/雪/星/雾按场景切换）
- 光标琥珀辉光（流式输出时 pulsate）
- 文本淡入（narrative-block enter: opacity + translateY）

**Page Pattern:** Full-screen immersive single-page narrative

- **Layout:** 全屏单一叙事页，无路由跳转
- **Z-layers:** AtmoBackground(z=0) → ParticleLayer(z=1) → Main UI(z=2) → Character Panel(z=20) → Memory Drawer(z=30) → Ink Transition(z=50) → Spark Particles(z=100)
- **Section Order:** 章节铭牌 → 叙事正文区（流式/打字机）→ 选项区（2-3选项+自由输入）→ 角色状态卡（右侧悬浮）→ 记忆抽屉（右下弹出）

---

## Motion

**Page Transition** (Complex) — Trigger: scene change | Duration: 1.2s | Easing: `cubic-bezier(0.4, 0, 0.2, 1)`

```css
/* 墨染转场 */
.ink-transition.active {
  animation: ink-spread 1.2s cubic-bezier(0.4, 0, 0.2, 1) both;
}
@keyframes ink-spread {
  0%   { clip-path: circle(0% at 50% 50%); }
  60%  { clip-path: circle(100% at 50% 50%); }
  100% { clip-path: circle(0% at 50% 50%); }
}
```

- ✅ Trigger ink transition on `scene.scene_id` change (not every turn)
- ✅ Spark burst on option click (18 particles, radial spread, 0.5-0.9s)
- ✅ Stagger entrance for options (`animation-delay: 0.04s` steps)
- ✅ `prefers-reduced-motion` respected globally
- ❌ Don't animate width/height — use transform/opacity/clip-path
- ❌ Don't block interaction during animations

---

## Anti-Patterns (Do NOT Use)

- ❌ Emojis as icons — Use Unicode symbols (▸ ▾ ●) or CSS shapes
- ❌ Meta language in UI — Never show "系统/AI/世界是假的" text
- ❌ Bright white backgrounds — Always dark (contrast ratio ≥ 4.5:1 on text)
- ❌ Instant state changes — Always transition (150-300ms for micro, 1-3s for scene)
- ❌ Horizontal scroll — Everything scrolls vertically or is fixed
- ❌ Raw hex values in components — Use CSS variables from this system
- ❌ Decorative-only animation — Motion must convey meaning (entrance, feedback, transition)
- ❌ Missing focus states — All interactive elements need visible `:focus-visible`

### Additional Forbidden Patterns

- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] All colors from CSS variables, no raw hex
- [ ] Typography uses --font-display or --font-body
- [ ] `cursor:pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No horizontal scroll on mobile
- [ ] No meta language in UI text
- [ ] Z-index hierarchy maintained per spec
- [ ] Tension colors use the three-tier system (青/鎏金/赤铁)

---

## 8 PHASE Quality System (Ref: 引擎设计规范 §三)

Each LLM output passes through 8 quality gates. The `phase_report` from backend contains:

| PHASE | Check | Type |
|-------|-------|------|
| P0 时空锚定 | 时间/季节/天气/位置连续 | Hard |
| P1 真实性 | 地理/人物/事件符合设定 | Hard |
| P2 意图记忆 | 玩家选择被回应，伏笔追踪 | Hard |
| P3 人物一致 | 无OOC，语言风格一致 | Hard |
| P4 防崩坏 | 防神化/渐进性/真实性 | Hard |
| P5 行为后果 | 法律/经济/关系/声望已结算 | Hard |
| P6 场景氛围 | 光/声/味/温/人流覆盖 | Soft |
| P7 输出质量 | 描写均衡/感官细节/情感链 | Soft |

## Information Fog (Ref: 引擎设计规范 §六)

| Tier | Content | Visual Treatment |
|------|---------|-----------------|
| `public` | 玩家已见/已闻 | Normal narrative text |
| `hidden` | 世界真实（禁止泄漏） | Never rendered in UI |
| `player` | 穿越记忆/历史直觉 | Gold italic + `·思绪` marker |
