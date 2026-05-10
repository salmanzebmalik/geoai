<template>
  <div ref="mapContainer" class="map-container" />
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import OSM from 'ol/source/OSM'
import { fromLonLat } from 'ol/proj'
import 'ol/ol.css'

const mapContainer = ref(null) // reactive container for the map div
let map = null // variable to hold the OpenLayers map instance

// Münster coordinates [longitude, latitude], converted to the map's projection
const MUENSTER_COORDS = fromLonLat([7.6261, 51.9607])

// Runs after Vue has rendered the template and the div actually exists in the DOM
// Create the OpenLayers map and attach it to the div
onMounted(() => {
  map = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({
        source: new OSM(),
      }),
    ],
    view: new View({
      center: MUENSTER_COORDS,
      zoom: 13.5,
    }),
  })
})

// Runs when the component is removed from the page 
// Skipping this could cause memory leaks if the map component gets mounted and unmounted multiple times during navigation
onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
})
</script>

<!-- Size of the map container -->
<style scoped>
.map-container {
  width: 100%;
  height: 100vh;
}
</style>