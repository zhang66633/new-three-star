<template>
  <!-- 关系网总览（GameMenu 嵌入模式）：好感/信任/立场，按亲疏排序 -->
  <div class="relnet">
    <div class="relnet-head">
      <span class="relnet-title">关系网</span>
      <span class="relnet-count">{{ list.length }} 人</span>
    </div>
    <div v-if="list.length" class="relnet-list">
      <div v-for="item in list" :key="item.name" class="relnet-row">
        <span class="relnet-avatar">{{ item.name[0] }}</span>
        <div class="relnet-main">
          <div class="relnet-top">
            <span class="relnet-name">{{ item.name }}</span>
            <span v-if="item.stance" class="relnet-stance">{{ item.stance }}</span>
          </div>
          <div v-if="item.tags.length" class="relnet-tags">
            <span v-for="(t, ti) in item.tags" :key="ti" class="relnet-tag">{{ t }}</span>
          </div>
          <div class="relnet-meters">
            <div class="relnet-meter">
              <span class="relnet-label" :class="relClass(item.rel)">感 {{ item.rel }}</span>
              <div class="relnet-bar">
                <div class="relnet-fill" :class="relClass(item.rel)" :style="{ width: item.rel + '%' }"></div>
              </div>
            </div>
            <div class="relnet-meter">
              <span class="relnet-label" :class="trustClass(item.trust)">信 {{ item.trust }}</span>
              <div class="relnet-bar">
                <div class="relnet-fill" :class="trustClass(item.trust)" :style="{ width: item.trust + '%' }"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="relnet-empty">天下之大，尚未有相识之人</div>
  </div>
</template>

<script setup lang="ts">
// RelationshipPanel —— 关系网总览（新·自由大世界关系网）
// 展示已相遇 NPC（encountered 或 relations 键）：抽象人设标签（character_personas.json 静态库，多条）
// + 好感条 + 信任条 + 立场标签，按 好感+信任 排序。未相遇的角色不显示（决策 14 哲学）。
import { computed } from 'vue'
import { relClass, trustClass } from '../utils/classes'
import personasData from '../assets/personas/character_personas.json'

const props = defineProps<{
  rels: Record<string, number>
  trust?: Record<string, number>
  stances?: Record<string, string>
  encountered?: string[]
}>()

// 静态人设标签库：name → tags[]（后端 character_personas.json 同步副本）
const personaTags = computed(() => {
  const m: Record<string, string[]> = {}
  const list = (personasData as any)?.personas ?? []
  for (const p of list) {
    if (p && typeof p.name === 'string') m[p.name] = Array.isArray(p.tags) ? p.tags : []
  }
  return m
})

const list = computed(() => {
  const tr = props.trust ?? {}
  const st = props.stances ?? {}
  const enc = new Set(props.encountered ?? [])
  // 已相遇 = encountered 集合 ∪ relations 键（兼容旧档/早期存档无 encountered 字段）
  const isMet = (n: string) => enc.has(n) || n in (props.rels ?? {})
  return Object.entries(props.rels)
    .filter(([name, v]) => typeof v === 'number' && isMet(name))
    .map(([name, rel]) => ({
      name,
      rel,
      trust: tr[name] ?? 50,
      stance: st[name] ?? '',
      tags: personaTags.value[name] ?? [],
    }))
    .sort((a, b) => (b.rel + b.trust) - (a.rel + a.trust))
})
</script>

<style scoped>
.relnet {
  padding: 6px 2px;
}
.relnet-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}
.relnet-title {
  font-family: var(--font-display, 'Ma Shan Zheng', serif);
  font-size: 18px;
  color: var(--accent-gold, #c9a24b);
  letter-spacing: 2px;
}
.relnet-count {
  font-size: 12px;
  color: var(--text-muted, rgba(200, 200, 220, 0.5));
}
.relnet-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 56vh;
  overflow-y: auto;
  padding-right: 4px;
}
.relnet-row {
  display: flex;
  gap: 10px;
  align-items: center;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(202, 138, 4, 0.12);
  border-radius: 10px;
  padding: 8px 10px;
}
.relnet-avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  color: #0a0a12;
  background: linear-gradient(135deg, var(--accent-gold, #c9a24b), #8a6a2a);
  font-weight: 600;
}
.relnet-main {
  flex: 1;
  min-width: 0;
}
.relnet-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}
.relnet-name {
  font-size: 14px;
  color: #ececf2;
}
.relnet-stance {
  font-size: 11px;
  color: rgba(202, 138, 4, 0.85);
  border: 1px solid rgba(202, 138, 4, 0.3);
  border-radius: 4px;
  padding: 0 5px;
  white-space: nowrap;
}
/* 抽象人设标签（多条，金色小胶囊，可换行） */
.relnet-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 5px;
}
.relnet-tag {
  font-size: 10.5px;
  color: rgba(240, 220, 174, 0.92);
  background: rgba(202, 138, 4, 0.14);
  border: 1px solid rgba(202, 138, 4, 0.35);
  border-radius: 999px;
  padding: 1px 8px;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.relnet-meters {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.relnet-meter {
  display: flex;
  align-items: center;
  gap: 8px;
}
.relnet-label {
  font-size: 11px;
  width: 44px;
  flex: 0 0 44px;
  text-align: right;
}
.relnet-bar {
  flex: 1;
  height: 5px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}
.relnet-fill {
  height: 100%;
  border-radius: 3px;
}
.rel-high { color: #34d399; }
.rel-mid  { color: #fbbf24; }
.rel-low  { color: #f87171; }
.trust-high { color: #34d399; }
.trust-mid  { color: #fbbf24; }
.trust-low  { color: #f87171; }
.relnet-fill.rel-high { background: #34d399; }
.relnet-fill.rel-mid  { background: #fbbf24; }
.relnet-fill.rel-low  { background: #f87171; }
.relnet-fill.trust-high { background: #34d399; }
.relnet-fill.trust-mid  { background: #fbbf24; }
.relnet-fill.trust-low  { background: #f87171; }
.relnet-empty {
  color: var(--text-muted, rgba(200, 200, 220, 0.5));
  font-size: 13px;
  padding: 16px 4px;
  text-align: center;
}
</style>
