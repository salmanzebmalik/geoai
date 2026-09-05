<template>
  <div
    v-if="mapStore.hasPrediction"
    class="legend"
    :class="{ 'legend--shifted': mapStore.historyDrawerOpen }"
  >
    <template v-if="classes.length">
      <div class="legend-classes">
        <button
          v-for="entry in visibleClasses"
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
              backgroundColor: fillColor(entry.color, 0.5),
              borderColor: entry.color,
            }"
          />
          <span class="label">{{ entry.name }}</span>
        </button>
      </div>

      <button
        v-if="isCollapsible"
        type="button"
        class="legend-row legend-row--toggle legend-more"
        @click="expanded = !expanded"
      >
        <v-icon
          size="14"
          :icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
        />
        <span class="label">
          {{ expanded ? 'Show less' : `${classes.length - COLLAPSED_COUNT} more` }}
        </span>
      </button>
    </template>

    <div v-else class="legend-row">
      <span class="swatch swatch--default" />
      <span class="label">Detected objects</span>
    </div>

    <div v-if="treeCount !== null" class="legend-row">
      <span class="label">Number of detected trees: <span class="count">{{ treeCount }}</span></span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'
import { fillColor } from '@/utils/predictionColors'

const mapStore = useMapStore()

const classes = computed(() => mapStore.predictionClasses)

const COLLAPSED_COUNT = 5
const expanded = ref(false)

const isCollapsible = computed(
  () => classes.value.length > COLLAPSED_COUNT,
)

const visibleClasses = computed(() =>
  isCollapsible.value && !expanded.value
    ? classes.value.slice(0, COLLAPSED_COUNT)
    : classes.value,
)

watch(classes, () => {
  expanded.value = false
})

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
  background-color: rgba(255, 255, 255, 0.94);
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
  font-size: 13px;
  color: rgba(0, 0, 0, 0.87);
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

.legend-row--off {
  opacity: 0.55;
}

.legend-row--off .label {
  text-decoration: line-through;
}

.legend-row--off .swatch {
  background-color: transparent !important;
}

.legend-classes {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 45vh;
  overflow-y: auto;
}

.legend-more {
  opacity: 0.8;
}

.legend-more .label {
  font-style: italic;
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
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.15);
}

.swatch--default {
  background-color: rgba(0, 200, 100, 0.5);
  border-color: #00c864;
}
</style>
