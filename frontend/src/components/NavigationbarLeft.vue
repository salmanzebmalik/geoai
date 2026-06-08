<template>
  <v-navigation-drawer permanent width="300" color="#1b2e1b">
      <div class="map-picker">
        <p class="picker-label">Map</p>
        <v-btn-toggle
          v-model="mapStore.mapType"
          rounded
          divided
          color="success"
          class="map-type-toggle"
        >
          <v-btn value="osm" prepend-icon="mdi-map">
            OSM
          </v-btn>
          <v-btn value="sentinel" prepend-icon="mdi-satellite-variant">
            Sentinel
          </v-btn>
          <v-btn value="orthophoto" prepend-icon="mdi-magnify">
            Ortho
          </v-btn>
        </v-btn-toggle>
      </div>

      <v-divider/>
    
      <v-list class="procedure" lines="one">
          <v-list-item
            prepend-icon="mdi-numeric-1-circle"
            title="Select Area"
          ></v-list-item>
          <v-btn
            @click="mapStore.triggerDrawing()"
            class="select-button"
            prepend-icon="mdi-select"
            variant="tonal"
          >Select Area</v-btn>

          <v-card class="bbox-info" variant="tonal" v-if="mapStore.bbox">
            <span>N {{ mapStore.bbox.max_lat.toFixed(5) }}</span>
            <span>S {{ mapStore.bbox.min_lat.toFixed(5) }}</span>
            <span>E {{ mapStore.bbox.max_lon.toFixed(5) }}</span>
            <span>W {{ mapStore.bbox.min_lon.toFixed(5) }}</span>
          </v-card>

          <v-list-item
            prepend-icon="mdi-numeric-2-circle"
            title="Task"
          ></v-list-item>
          <v-select
            :items="['Tree Quality', 'Pavement Quality', 'Construction Site Detection']"
            placeholder="Select Task"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
          ></v-select>
          <v-list-item
            prepend-icon="mdi-numeric-3-circle"
            title="Model"
          ></v-list-item>
          <v-select
            :items="['Model A', 'Model B', 'Model C']"
            placeholder="Select Model"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
          ></v-select>
          <v-list-item
            prepend-icon="mdi-numeric-3-circle"
            title="Run"
          ></v-list-item>
          <v-btn @click="mapStore.triggerRun()" prepend-icon="mdi-rocket-launch" class="run-btn" color="success">Run</v-btn>
      </v-list>

      
        
  </v-navigation-drawer>
</template>

<script setup>
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
</script>

<style scoped>
.map-picker {
  padding: 16px 16px 12px;

  .v-btn {
    flex: 1;
  }
}

.picker-label {
  color: "white";
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 10px;
}

.map-type-toggle {
  width: 100%;
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

.bbox-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  width: 90%;
  margin: 8px 16px;
  padding: 8px;
  font-size: 12px;
  text-align: center;
}
</style>