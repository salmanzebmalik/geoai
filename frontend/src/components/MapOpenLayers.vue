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

const mapContainer = ref(null)
let map = null

// Münster coordinates [longitude, latitude]
const MUENSTER_COORDS = fromLonLat([7.6261, 51.9607])

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

onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100vh;
}
</style>