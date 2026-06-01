<template>
  <v-navigation-drawer permanent width="300" color="#1b2e1b">

      <div class="map-picker">
        <p class="picker-label">Map</p>
        <v-btn-toggle
          v-model="mapStore.mapType"
          mandatory
          color="success"
          variant="outlined"
          divided
          class="map-type-toggle"
        >
          <v-btn value="osm" style="flex: 1">
            <v-icon>mdi-map</v-icon>
            <span class="ml-1">OSM</span>
          </v-btn>
          <v-btn value="sentinel" style="flex: 1">
            <v-icon>mdi-satellite-variant</v-icon>
            <span class="ml-1">Sentinel</span>
          </v-btn>
        </v-btn-toggle>
      </div>

      <v-divider color="rgba(255,255,255,0.6)" class="mb-2"/>

    
      <v-list color="transparent">
          <v-list-item
            prepend-icon="mdi-numeric-1-circle"
            title="Select Area"
          ></v-list-item>
          <v-list-item
            prepend-icon="mdi-numeric-2-circle"
            title="Machine Learning Task"
          ></v-list-item>
          <v-list-item 
            prepend-icon="mdi-numeric-3-circle" 
            title="Start Analysis"
          ></v-list-item>
      </v-list>

      <v-btn @click="mapStore.triggerDrawing()" class="select-button">
        <v-icon left>mdi-select</v-icon>
        Select Area
      </v-btn>
        
  </v-navigation-drawer>
</template>

<script setup>
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
</script>

<style scoped>
.map-picker {
  padding: 16px 16px 12px;
}

.picker-label {
  color: rgba(255, 255, 255, 0.6);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 10px;
}

.map-type-toggle {
  width: 100%;
  background-color: white;
  color: #333;
}

.select-button {
  width: 90%;
  margin: 0 16px;
  background-color: white;
  color: #333;

  .v-icon {
    margin-right: 8px;
  }
}
</style>