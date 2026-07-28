<template>
  <v-navigation-drawer permanent width="300" color="#1b2e1b">
    <!--  Map picker -->
      <div class="map-picker">
        <div class="picker-title">
          <v-icon size="18" class="mr-2">mdi-layers</v-icon>
          <p class="picker-label">MAP</p>
        </div>
        <v-select
          v-model="mapStore.mapType"
          :items="mapTypeOptions"
          variant="outlined"
          density="comfortable"
          hide-details
          class="map-type-select"
        >
          <template #item="{ item, props: itemProps }">
            <v-list-item v-bind="itemProps" title="" class="map-select-item">
              <template #prepend>
                <img :src="item.thumbnail" alt="" class="map-thumb" />
              </template>
              <v-list-item-title class="map-item-title">{{ item.title }}</v-list-item-title>
              <v-list-item-subtitle class="map-item-subtitle">{{ item.description }}</v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-select>
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
              <v-icon icon="mdi-pencil" />
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
            :items="modelOptions"
            :disabled="!modelOptions.length"
            :placeholder= "modelOptions.length ? 'Select Model' : 'No models available'"
            v-model="mapStore.modelType"
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
import osmThumb from '@/assets/map-osm.jpg'
import germanyThumb from '@/assets/map-germany.jpg'
import orthophotoThumb from '@/assets/map-orthophoto.jpg'

const mapStore = useMapStore()

const mapTypeOptions = [
  {
    title: 'OSM',
    value: 'osm',
    description: 'Open street map (no prediction)',
    thumbnail: osmThumb,
  },
  {
    title: 'Germany',
    value: 'germany',
    description: 'Coarse aerial imagery (10m)',
    thumbnail: germanyThumb,
  },
  {
    title: 'NRW',
    value: 'orthophoto',
    description: 'High-resolution aerial imagery (5m)',
    thumbnail: orthophotoThumb,
  },
]

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
    { title: 'TCD-Segformer', value: 'tree' },
    { title: 'DeepForest Boxes', value: 'tree_deepforest' },
  ],
  germany: [
    { title: 'Satlas', value: 'tree_satlas' },
    { title: 'UNet', value: 'tree_unet' },
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
    mapStore.selectedTask = availableTasks.value[0]?.value ?? null
  }
  onTaskChange()
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

.picker-title {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.picker-label {
  font-size: 11px;
  margin: 0;
}

.map-type-select {
  width: 100%;
}

.map-type-select :deep(.v-field) {
  color: white;
}

.map-type-select :deep(.v-field__outline) {
  --v-field-border-opacity: 0.3;
}

.map-select-item {
  padding-inline-start: 8px;
}

.map-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.map-item-title {
  font-size: 13px;
  font-weight: 500;
  margin-left: 8px;
}

.map-item-subtitle {
  font-size: 11px;
  opacity: 0.7;
  white-space: normal;
  margin-left: 8px;
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