<!-- THIS COMPONENT IS DEPRECATED  -->
<!-- All functionality is bundled in Map.vue now, this component will be deleted soon (probably) -->




<template>
  <div ref="mapContainer" class="map-container" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import OSM from 'ol/source/OSM'
import { fromLonLat, toLonLat } from 'ol/proj'
import 'ol/ol.css'

import Draw, { createBox } from 'ol/interaction/Draw.js'
import VectorLayer from 'ol/layer/Vector.js'
import VectorSource from 'ol/source/Vector.js'
import { useMapStore } from '@/stores/map'
import GeoJSON from 'ol/format/GeoJSON.js'

const mapStore = useMapStore()

const mapContainer = ref(null) // reactive container for the map div
let map = null // variable to hold the OpenLayers map instance

const vectorSource = new VectorSource({ wrapX: false })
const vectorLayer = new VectorLayer({ source: vectorSource })

let draw = null

function startDrawing() {
  vectorSource.clear()
  if (draw) map.removeInteraction(draw)

  draw = new Draw({
    source: vectorSource,
    type: 'Circle',
    geometryFunction: createBox(),
  })

  draw.on('drawend', (event) => {
    const geoJSON = new GeoJSON().writeFeatureObject(event.feature, {
      featureProjection: 'EPSG:3857',
      dataProjection: 'EPSG:4326',
    })
    console.log('GeoJSON:', geoJSON)
    map.removeInteraction(draw)
    draw = null
  })

  map.addInteraction(draw)
}

// Runs after Vue has rendered the template and the div actually exists in the DOM
// Create the OpenLayers map and attach it to the div
onMounted(() => {
  map = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({
        source: new OSM(),
      }),
      vectorLayer,
    ],
    view: new View({
      center: fromLonLat(mapStore.mapCenter),
      zoom: mapStore.mapZoom,
    }),
  })

  // save state to store whenever the user moves/zooms
  map.on('moveend', () => {
    const view = map.getView()
    mapStore.mapCenter = toLonLat(view.getCenter())
    mapStore.mapZoom = view.getZoom()
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

watch(() => mapStore.startDrawingTrigger, () => {
  startDrawing()
})

</script>

<!-- Size of the map container -->
<style scoped>
.map-container {
  width: 100%;
  height: 100%;
}
</style>