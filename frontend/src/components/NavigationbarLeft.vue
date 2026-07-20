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
          
          <v-btn
            @click="mapStore.triggerDrawing()"
            class="select-button"
            prepend-icon="mdi-select"
          >Select Area</v-btn>
          
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
            :items="['Tree Detection', 'Zero-Shot']"
            placeholder="Select Task"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
            v-model="mapStore.selectedTask" 
            @update:model-value="onTaskChange"
          ></v-select>

          <template v-if="mapStore.selectedTask === 'Zero-Shot'">
          <v-list-item prepend-icon="mdi-plus" title="Keyword" />
          <v-text-field
            v-model="mapStore.keyword"
            placeholder="e.g., buildings, swimming pools, trees"
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
            :items="[mapStore.selectedTask === 'Zero-Shot' ? 'LangSAM' : 'TCD-Segformer-MIT-B5']"
            :model-value="mapStore.selectedTask === 'Zero-Shot' ? 'LangSAM' : 'TCD-Segformer-MIT-B5'"
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
            :disabled="mapStore.mapType === 'osm' || !mapStore.bbox || !mapStore.selectedTask || (mapStore.selectedTask === 'Zero-Shot' && !mapStore.keyword)"
          >Run</v-btn>
      </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

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
  } else {
    mapStore.modelType = 'tree'
    mapStore.keyword = ''   // clear keyword for non zero shot
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

.select-button {
  width: 90%;
  margin: 0 16px;
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