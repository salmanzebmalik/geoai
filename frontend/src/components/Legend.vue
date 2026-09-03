<template>
  <div
    v-if="mapStore.hasPrediction"
    class="legend"
    :class="{ 'legend--shifted': mapStore.historyDrawerOpen }"
  >
    <div class="legend-row">
      <span class="swatch" />
      <span class="label">Detected objects</span>
    </div>
    <div v-if="treeCount !== null" class="legend-row">
      <span class="label">Number of detected trees: <span class="count">{{ treeCount }}</span></span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

const treeCount = computed(() => {
  if (mapStore.viewedPredictionMeta?.model_name !== 'deepforest-tree') return null
  return mapStore.viewedPredictionMeta?.feature_count ?? null
})
</script>

<style scoped>
.legend {
  position: fixed;
  top: 84px;
  right: 76px;
  z-index: 1005;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  background-color: #1b2e1be1;
  border-radius: 8px;
  font-size: 13px;
  color: #ffffff;
  white-space: nowrap;
  transition: right 0.2s ease;
}

.legend--shifted {
  right: 416px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 24px;
}

.count {
  font-weight: 700;
}

.swatch {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background-color: rgba(0, 200, 100, 0.35);
  border: 1.5px solid #00c864;
}
</style>
