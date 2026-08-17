<template>
  <!-- 角色状态卡（仅在场有人时显示，父组件控制 v-if） -->
  <!-- 在场角色优先取 character_states（自由大世界·决策10：当前地点角色），relations 兜底 -->
  <aside class="character-panel" :class="{ 'cp-reveal': reveal, 'cp-embedded': embedded }">
    <div class="cp-title">在场</div>
    <div v-for="name in presentNames" :key="name" class="character-chip">
      <span class="chip-avatar">{{ name[0] }}</span>
      <span class="chip-info">
        <span class="chip-name">{{ name }}</span>
        <span v-if="NPC_PERSONA[name]" class="chip-trait">{{ NPC_PERSONA[name].trait }}</span>
        <span v-if="cs(name)?.activity" class="chip-activity">正「{{ cs(name)?.activity }}」</span>
        <span v-if="known(name)" class="chip-rels">
          <span class="chip-rel" :class="relClass(relOf(name))">感{{ relOf(name) }}</span>
          <span v-if="trust[name] !== undefined" class="chip-trust" :class="trustClass(trust[name] ?? 50)">信{{ trust[name] ?? 50 }}</span>
          <span v-if="stances?.[name]" class="chip-stance">{{ stances[name] }}</span>
        </span>
        <span v-if="cs(name)?.goal" class="chip-goal">目标：{{ cs(name)?.goal }}</span>
        <span v-if="NPC_PERSONA[name]?.mechanism" class="chip-mech">{{ NPC_PERSONA[name].mechanism }}</span>
      </span>
    </div>
    <div v-if="!presentNames.length" class="cp-empty">此处暂无相识之人</div>
  </aside>
</template>

<script setup lang="ts">
// CharacterPanel —— 在场角色状态卡（PlayPage 抽离，纯展示）
// 在场角色来源：character_states（当前地点角色，含 activity/goal 演出依据）；relations 兜底。
// NPC 人设速查从 PlayPage 迁入（对齐 backend/engine/writer.py PERSONA_FULL）
import { computed } from 'vue'
import type { CharacterState } from '../types/play'
import { relClass, trustClass } from '../utils/classes'

const props = defineProps<{
  rels: Record<string, number>
  trust: Record<string, number>
  stances?: Record<string, string>
  characterStates?: Record<string, CharacterState>
  present?: string[]          // 后端权威在场名单（scene 事件下发，按地点过滤）
  reveal: boolean
  embedded?: boolean   // 主菜单页嵌入模式：中和 fixed 四角定位，内容区由菜单 tab 容器流式布局
}>()

// 在场角色（严格真实）：后端下发的 present（distance_map 权威在场名单，按地点过滤）。
// present 是数组（含空数组=当前确实无人）→ 一律以它为准；
// 仅 present 为 undefined（旧档/未接线）时退回 character_states 的 known/relations 启发式。
const presentNames = computed<string[]>(() => {
  if (Array.isArray(props.present)) {
    return [...props.present].sort((a, b) => a.localeCompare(b))
  }
  const csMap = props.characterStates ?? {}
  const fromStates = Object.keys(csMap).filter(name => {
    const c = csMap[name]
    return c?.known === true || (c && (props.rels ?? {})[name] !== undefined)
  })
  return fromStates
})
function cs(name: string): CharacterState | undefined {
  return (props.characterStates ?? {})[name]
}
function known(name: string): boolean {
  const c = cs(name)
  return c?.known === true || (props.rels ?? {})[name] !== undefined
}
function relOf(name: string): number {
  if (!known(name)) return 50
  const c = cs(name)
  if (c && typeof c.attitude === 'number') return c.attitude
  return props.rels[name] ?? 50
}

const NPC_PERSONA: Record<string, { trait: string; mechanism?: string }> = {
  '曹操':   { trait: '枭雄·窥天侵蚀', mechanism: '魏武挥鞭/世人看错' },
  '刘备':   { trait: '仁义面具·内心盘算', mechanism: '自刎归天/心灵控制' },
  '关羽':   { trait: '傲慢武圣·摸须装逼', mechanism: '一刀斩/水淹七军' },
  '张飞':   { trait: '暴躁猛将·性如烈火', mechanism: '酿制美酒' },
  '诸葛亮': { trait: '天才受气包·窥天最深', mechanism: '人体炼成/向下霸凌' },
  '司马懿': { trait: '隐忍老狐狸·视人如NPC', mechanism: '化骨绵掌' },
  '吕布':   { trait: '率真莽夫·武力+100%', mechanism: '三姓家奴' },
  '董卓':   { trait: '自认大汉忠臣', mechanism: '视刘协为亲人' },
  '袁绍':   { trait: '宽厚明主·屡失良机', mechanism: '死亡抗性II' },
  '孙权':   { trait: '受气主公', mechanism: '江东之主诅咒' },
  '周瑜':   { trait: '水火无敌·暴怒降寿', mechanism: '大都督诅咒' },
  '貂蝉':   { trait: '间谍·身不由己' },
  '陈宫':   { trait: '谋士·虫系宝可梦大师' },
  '赵云':   { trait: '忠勇无双' },
  '马超':   { trait: '西凉铁骑' },
  '黄忠':   { trait: '老当益壮' },
  '魏延':   { trait: '脑后有反骨' },
  '庞统':   { trait: '凤雏·黑暗兵法' },
  '姜维':   { trait: '天水麒麟儿' },
  '鲁肃':   { trait: '老实人·受气包' },
  '吕蒙':   { trait: '吴下阿蒙' },
  '陆逊':   { trait: '书生拜将' },
}
</script>

<style scoped>
.character-panel {
  position: fixed;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  width: 170px;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.18);
  border-radius: 14px;
  padding: 14px 12px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 20;
  animation: panel-slide-in 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  box-shadow: 0 0 30px rgba(202, 138, 4, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
/* 主菜单页嵌入：中和 fixed 四角定位，由菜单 tab 容器流式布局 */
.character-panel.cp-embedded {
  position: static;
  transform: none;
  width: 100%;
  background: transparent;
  border: none;
  box-shadow: none;
  backdrop-filter: none;
  padding: 0;
  animation: none;
}
@keyframes panel-slide-in {
  from { opacity: 0; transform: translateY(-50%) translateX(12px); }
  to   { opacity: 1; transform: translateY(-50%) translateX(0); }
}
.cp-title {
  font-size: 0.65rem;
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: rgba(202, 138, 4, 0.55);
  margin-bottom: 12px;
  text-align: center;
}
.character-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.06);
}
.character-chip:last-child { border-bottom: none; }
.chip-avatar {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: rgba(202, 138, 4, 0.12);
  color: rgba(202, 138, 4, 0.7);
  font-size: 0.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chip-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.chip-name {
  font-size: 0.8rem; color: #f1f5f9; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chip-rels { display: flex; gap: 8px; font-size: 0.65rem; }
.chip-trait {
  font-size: 0.6rem;
  color: rgba(202, 138, 4, 0.55);
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-mech {
  font-size: 0.55rem;
  color: rgba(90, 122, 106, 0.5);    /* 青铜绿 — 机制标注 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.02em;
}
.chip-activity {
  font-size: 0.62rem;
  color: rgba(226, 232, 240, 0.75);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-goal {
  font-size: 0.55rem;
  color: rgba(148, 163, 184, 0.55);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cp-empty {
  font-size: 0.72rem;
  color: rgba(148, 163, 184, 0.35);
  font-style: italic;
  text-align: center;
  padding: 16px 0;
}
.chip-rel, .chip-trust {
  display: inline-flex; align-items: center; gap: 2px;
}
.rel-high, .trust-high { color: #4a9ea0; }
.rel-mid,  .trust-mid  { color: #e8a838; }
.rel-low,  .trust-low  { color: #c04030; }
/* 人物状态浮现高亮 */
.character-panel.cp-reveal {
  animation: cp-glow 0.6s ease-in-out;
  border-color: rgba(202, 138, 4, 0.45) !important;
  box-shadow: 0 0 22px rgba(202, 138, 4, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
@keyframes cp-glow {
  0%   { box-shadow: 0 0 0px rgba(202, 138, 4, 0); }
  50%  { box-shadow: 0 0 30px rgba(202, 138, 4, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08); }
  100% { box-shadow: 0 0 30px rgba(202, 138, 4, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.03); }
}
/* 响应式：小屏隐藏角色卡 */
@media (max-width: 768px) {
  .character-panel { display: none; }
}
</style>
