<template>
  <v-navigation-drawer permanent width="300" color="#1b2e1b">
    <!--  Map picker -->
      <div class="map-picker">
        <p class="picker-label">Map</p>
        <v-btn-toggle
          v-model="mapStore.mapType"
          rounded
          divided
          variant="outlined"
          color="success"
          class="map-type-toggle"
        >
          <v-btn value="osm" prepend-icon="mdi-map">
            OSM
          </v-btn>
          <v-btn value="germany" prepend-icon="mdi-earth">
            Germany
          </v-btn>
          <v-btn value="orthophoto" prepend-icon="mdi-magnify">
            NRW
          </v-btn>
        </v-btn-toggle>
      </div>

      <v-divider/>
    
      <v-list class="procedure" lines="one">
        <!-- Area selection -->
          <v-list-item
            prepend-icon="mdi-numeric-1-circle"
            title="Area"
          ></v-list-item>
          
          <div class="area-buttons">
            <v-btn
              @click="mapStore.triggerDrawing()"
              class="select-button"
              prepend-icon="mdi-select"
            >Select Area</v-btn>

            <v-btn
              @click="mapStore.coordinateInputOpen = true"
              class="input-coords-button"
              aria-label="Enter coordinates manually"
              variant="tonal"
            >
              <v-icon icon="mdi-form-textbox" />
            </v-btn>
          </div>

          <div class="bbox-info" v-if="mapStore.bbox">
            <div class="bbox-coords">
              <span>N {{ mapStore.bbox.max_lat.toFixed(5) }}</span>
              <span>S {{ mapStore.bbox.min_lat.toFixed(5) }}</span>
              <span>E {{ mapStore.bbox.max_lon.toFixed(5) }}</span>
              <span>W {{ mapStore.bbox.min_lon.toFixed(5) }}</span>
            </div>
            <div class="bbox-area">
              <span class="area">{{ formatArea(mapStore.areaSqm) }}</span>
              <span class="area-fields">~ {{ formatSoccerFields(mapStore.areaSqm) }} soccer fields</span>
            </div>
          </div>

          <!-- Task selection  -->
          <v-list-item
            prepend-icon="mdi-numeric-2-circle"
            title="Task"
          ></v-list-item>
          
          <v-select
            :items="availableTasks"
            :disabled="!availableTasks.length"
            :placeholder="availableTasks.length ? 'Select Task' : 'No tasks available'"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
            v-model="mapStore.selectedTask"
            @update:model-value="onTaskChange"
          ></v-select>

          <template v-if="mapStore.selectedTask === 'Zero-Shot'">
          <v-list-item prepend-icon="mdi-plus" title="Keywords" />
          <v-text-field
            v-model="mapStore.keyword"
            placeholder="buildings, pools, cars"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
            prepend-inner-icon="mdi-magnify"
            @keyup.enter="mapStore.triggerRun()"
          />
        </template>

        <!-- Model selection -->
          <v-list-item
            prepend-icon="mdi-numeric-3-circle"
            title="Model"
          ></v-list-item>
          
          <v-select
            :items="modelLabels"
            v-model="selectedModel"
            :disabled="mapStore.selectedTask === 'Zero-Shot'"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
          ></v-select>

          <!-- Start prediction button-->
          <v-list-item
            prepend-icon="mdi-numeric-4-circle"
            title="Start Prediction"
          ></v-list-item>
          
          <v-btn
            @click="mapStore.triggerRun()"
            prepend-icon="mdi-rocket-launch"
            class="run-btn"
            color="success"
            :disabled="mapStore.mapType === 'osm' || !mapStore.bbox || !mapStore.selectedTask || (mapStore.selectedTask === 'Zero-Shot' && !mapStore.keyword.trim())"
          >Run</v-btn>

          <v-list-item
            prepend-icon="mdi-numeric-5-circle"
            title="Export"
          ></v-list-item>
          <v-btn
            @click="mapStore.openExportDialog()"
            prepend-icon="mdi-tray-arrow-down"
            class="run-btn"
            color="success"
            variant="tonal"
            :disabled="!mapStore.currentQueryId"
          >Export options</v-btn>
      </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

const TASK_OPTIONS_BY_MAP_TYPE = {
  orthophoto: [
    { title: 'Tree Detection', value: 'Tree Detection' },
    { title: 'Segment Anything', value: 'Zero-Shot' },
  ],
  germany: [
    { title: 'Tree Detection', value: 'Tree Detection' },
  ],
  osm: [],
}

const availableTasks = computed(() => TASK_OPTIONS_BY_MAP_TYPE[mapStore.mapType] ?? [])

// only the models that match the current dataset's resolution are displayed 
const TREE_MODELS_BY_MAP_TYPE = {
  orthophoto: [
    { title: 'TCD-Segformer (10cm ortho)', value: 'tree' },
    { title: 'DeepForest boxes (10cm ortho)', value: 'tree_deepforest' },
  ],
  germany: [
    { title: 'Satlas (5m satellite)', value: 'tree_satlas' },
    { title: 'UNet (5m satellite)', value: 'tree_unet' },
  ],
  osm: [],
}

const modelOptions = computed(() =>
  mapStore.selectedTask === 'Zero-Shot'
    ? [{ title: 'LangSAM', value: 'zeroshot' }]
    : TREE_MODELS_BY_MAP_TYPE[mapStore.mapType] ?? []
)


watch(() => mapStore.mapType, () => {
  if (!availableTasks.value.some((t) => t.value === mapStore.selectedTask)) {
    mapStore.selectedTask = null
  }
  onTaskChange()
})

const modelLabels = computed(() => modelOptions.value.map(m => m.title))

const selectedModel = computed({
  get: () => modelOptions.value.find(m => m.value === mapStore.modelType)?.title
             ?? modelOptions.value[0]?.title
             ?? null,
  set: (title) => {
    const match = modelOptions.value.find(m => m.title === title)
    if (match) mapStore.modelType = match.value
  },
})

function formatArea(sqm) {
  if (sqm == null) return ''
  return sqm > 1_000_000
    ? `${(sqm / 1_000_000).toFixed(2)} km²`
    : `${Math.round(sqm)} m²`
}

const SOCCER_FIELD_SQM = 7140

function formatSoccerFields(sqm) {
  if (sqm == null) return ''
  return (sqm / SOCCER_FIELD_SQM).toFixed(0)
}

// Update model type based on selected task
function onTaskChange() {
  if (mapStore.selectedTask === 'Zero-Shot') {
    mapStore.modelType = 'zeroshot'
  } else if (mapStore.selectedTask) {
    mapStore.modelType = modelOptions.value[0]?.value ?? null
    mapStore.keyword = ''   // clear keyword for non zero shot
  } else {
    mapStore.modelType = null
    mapStore.keyword = ''
  }
}

</script>

<style scoped>
.map-picker {
  padding: 16px 16px 12px;

  .v-btn {
    flex: 1;
  }
}

.picker-label {
  font-size: 11px;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.map-type-toggle {
  width: 100%;
}

.map-type-toggle :deep(.v-btn:not(.v-btn--active)) {
  color: white;
}

.map-type-toggle :deep(.v-btn) {
  border-color: rgba(255, 255, 255, 0.2);
}

.area-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 90%;
  margin: 0 16px;
}

.select-button {
  flex: 1;
  min-width: 0;
}

.input-coords-button {
  flex-shrink: 0;
  min-width: 0;
  padding: 0 14px;
}

.ml-task-dropdown {
  width: 90%;
  margin: 0 16px;
}

.run-btn {
  width: 90%;
  margin: 0 16px;
}

.run-btn.v-btn--disabled {
  opacity: 40%;
  background-color: grey;
}

.bottom-actions {
  display: flex;
  justify-content: flex-start;
  padding: 8px 12px;
}

.bbox-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 90%;
  margin: 8px 16px;
  padding: 10px 12px;
  background-color: rgba(139, 195, 74, 0.1);
  border: 1px solid rgba(139, 195, 74, 0.2);
  border-radius: 8px;
  font-size: 12px;
}

.bbox-coords {
  display: grid;
  grid-template-columns: auto auto;
  column-gap: 8px;
  row-gap: 2px;
  color: rgba(255, 255, 255, 0.85);
}

.bbox-area {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.area {
  color: #a5d6a7;
  white-space: nowrap;
}

.area-fields {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}
</style>
