<template>
  <div
    v-if="mapStore.hasPrediction"
    class="legend"
    :style="{ right: legendRight }"
  >
    <template v-if="classes.length">
      <div class="legend_classes">
        <button
          v-for="entry in visibleClasses"
          :key="entry.name"
          type="button"
          class="legend_row"
          :class="{ 'legend_row_hidden': isHidden(entry.name) }"
          :title="isHidden(entry.name) ? 'Show this class' : 'Hide this class'"
          @click="mapStore.togglePredictionClass(entry.name)"
        >
          <span
            class="color_swatch"
            :style="swatchStyle(entry.color)"
          />
          <span class="class_label">{{ entry.name }}</span>
        </button>
      </div>

      <button
        v-if="isCollapsible"
        type="button"
        class="legend_row legend_show_more"
        @click="expanded = !expanded"
      >
        <v-icon
          size="14"
          :icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
        />
        <span class="class_label">
          {{ expanded ? 'Show less' : `${classes.length - COLLAPSED_COUNT} more` }}
        </span>
      </button>
    </template>

    <div v-else class="legend_row">
      <span
        class="color_swatch"
        :style="swatchStyle()"
      />
      <span class="class_label">Detected objects</span>
    </div>

    <div v-if="treeCount !== null" class="legend_row">
      <span class="class_label">
        Number of detected trees: 
        <span class="count">{{ treeCount }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'
import { DEFAULT_CLASS_COLOR, fillColor } from '@/utils/predictionColors'

const mapStore = useMapStore()

const classes = computed(() => mapStore.predictionClasses) // prediction classes from the currently viewed prediction layer

// history width to compute position of legend
const HISTORY_TAB_WIDTH = 34
const HISTORY_DRAWER_WIDTH = 340
const GAP_FROM_HISTORY = 42

// compute right position of legend
const legendRight = computed(() => {
  const tabRight = mapStore.historyDrawerOpen ? HISTORY_DRAWER_WIDTH : 0
  return `${tabRight + HISTORY_TAB_WIDTH + GAP_FROM_HISTORY}px`
})

const COLLAPSED_COUNT = 5 // max number of classes before collapsing the legend
const expanded = ref(false)

const isCollapsible = computed(
  () => classes.value.length > COLLAPSED_COUNT,
)

// compute the classes to show in the legend
const visibleClasses = computed(() =>
  isCollapsible.value && !expanded.value
    ? classes.value.slice(0, COLLAPSED_COUNT)
    : classes.value,
)

watch(classes, () => {
  expanded.value = false // reset expanded state when classes change
})

// get color swatch style for a given class color
function swatchStyle(color = DEFAULT_CLASS_COLOR) {
  return {
    backgroundColor: fillColor(color, 0.5),
    borderColor: color,
  }
}

// check if a class is hidden/disabled
function isHidden(name) {
  return mapStore.hiddenPredictionClasses.includes(name)
}

// number of detected trees (deepforest)
const treeCount = computed(() => {
  if (mapStore.viewedPredictionMeta?.model_name !== 'deepforest-tree') return null
  return mapStore.viewedPredictionMeta?.feature_count ?? null
})
</script>

<style scoped>
.legend {
  position: fixed;
  top: 84px;
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

.legend_row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 24px;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
}

button.legend_row {
  cursor: pointer;
}

button.legend_row:hover .class_label {
  text-decoration: underline;
}

.legend_row_hidden {
  opacity: 0.55;
}

.legend_row_hidden .class_label {
  text-decoration: line-through;
}

.legend_row_hidden .color_swatch {
  background-color: transparent !important;
}

.legend_classes {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 45vh;
  overflow-y: auto;
}

.legend_show_more {
  opacity: 0.8;
}

.legend_show_more .class_label {
  font-style: italic;
}

.count {
  font-weight: 700;
}

.color_swatch {
  width: 14px;
  height: 14px;
  flex: none;
  border-radius: 3px;
  border: 1.5px solid transparent;
}
</style>
