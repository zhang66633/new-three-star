<template>
  <!-- 角色状态卡（仅在场有人时显示，父组件控制 v-if） -->
  <aside class="character-panel" :class="{ 'cp-reveal': reveal }">
    <div class="cp-title">在场</div>
    <div v-for="(rel, name) in rels" :key="name" class="character-chip">
      <span class="chip-avatar">{{ name[0] }}</span>
      <span class="chip-info">
        <span class="chip-name">{{ name }}</span>
        <span v-if="NPC_PERSONA[name]" class="chip-trait">{{ NPC_PERSONA[name].trait }}</span>
        <span class="chip-rels">
          <span class="chip-rel" :class="relClass(rel)">感{{ rel }}</span>
          <span class="chip-trust" :class="trustClass(trust[name] ?? 50)">信{{ trust[name] ?? 50 }}</span>
        </span>
        <span v-if="NPC_PERSONA[name]?.mechanism" class="chip-mech">{{ NPC_PERSONA[name].mechanism }}</span>
      </span>
    </div>
  </aside>
</template>

<script setup lang="ts">
// CharacterPanel —— 在场角色状态卡（PlayPage 抽离，纯展示）
// NPC 人设速查从 PlayPage 迁入（对齐 backend/engine/writer.py PERSONA_FULL）
import { relClass, trustClass } from '../utils/classes'

defineProps<{
  rels: Record<string, number>
  trust: Record<string, number>
  reveal: boolean
}>()

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
