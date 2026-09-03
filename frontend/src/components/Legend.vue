<template>
  <div
    v-if="mapStore.hasPrediction"
    class="legend"
    :class="{ 'legend--shifted': mapStore.historyDrawerOpen }"
  >
    <!-- Zero-shot runs tag every polygon with its keyword, so one prediction
         can carry several classes; click a row to hide or show that class. -->
    <template v-if="classes.length">
      <button
        v-for="entry in classes"
        :key="entry.name"
        type="button"
        class="legend-row legend-row--toggle"
        :class="{ 'legend-row--off': isHidden(entry.name) }"
        :title="isHidden(entry.name) ? 'Show this class' : 'Hide this class'"
        @click="mapStore.togglePredictionClass(entry.name)"
      >
        <span
          class="swatch"
          :style="{
            backgroundColor: fillColor(entry.color, 0.35),
            borderColor: entry.color,
          }"
        />
        <span class="label">{{ entry.name }}</span>
      </button>
    </template>

    <!-- The fixed tree models don't label their output. -->
    <div v-else class="legend-row">
      <span class="swatch swatch--default" />
      <span class="label">Detected objects</span>
    </div>

    <!-- Only the detection model counts actual objects; the segmentation
         models return polygons/clusters, which are not countable objects. -->
    <div v-if="treeCount !== null" class="legend-row">
      <span class="label">Number of detected trees: <span class="count">{{ treeCount }}</span></span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useMapStore } from '@/stores/map'
import { fillColor } from '@/utils/predictionColors'

const mapStore = useMapStore()

const classes = computed(() => mapStore.predictionClasses)

function isHidden(name) {
  return mapStore.hiddenPredictionClasses.includes(name)
}

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

.legend-row--toggle {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.legend-row--toggle:hover .label {
  text-decoration: underline;
}

/* Hidden class: keep the row readable but clearly switched off. */
.legend-row--off {
  opacity: 0.45;
}

.legend-row--off .label {
  text-decoration: line-through;
}

.legend-row--off .swatch {
  background-color: transparent !important;
}

.count {
  font-weight: 700;
}

.swatch {
  width: 14px;
  height: 14px;
  flex: none;
  border-radius: 3px;
  border: 1.5px solid transparent;
  border-style: solid;
}

.swatch--default {
  background-color: rgba(0, 200, 100, 0.35);
  border-color: #00c864;
}
</style>
