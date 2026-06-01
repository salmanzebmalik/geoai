<!-- MapSentinel.vue -->
<template>
  <div ref="mapContainer" class="map-container" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import TileWMS from 'ol/source/TileWMS'
import { fromLonLat, toLonLat } from 'ol/proj'
import 'ol/ol.css'
import Draw, { createBox } from 'ol/interaction/Draw.js'
import VectorLayer from 'ol/layer/Vector.js'
import VectorSource from 'ol/source/Vector.js'
import { useMapStore } from '@/stores/map'
import GeoJSON from 'ol/format/GeoJSON.js'

const mapStore = useMapStore()
const mapContainer = ref(null)
let map = null

// Sentinel Hub WMS configuratioon
const INSTANCE_ID = import.meta.env.VITE_SENTINELHUB_INSTANCE_ID

function getLastXDaysRange(range=60) {
  const today = new Date()
  const xDaysAgo = new Date()
  xDaysAgo.setDate(today.getDate() - range)
  
  const format = (date) => date.toISOString().split('T')[0] // = 'YYYY-MM-DD'
  
  return `${format(xDaysAgo)}/${format(today)}`
}

const sentinelSource = new TileWMS({
  url: `https://sh.dataspace.copernicus.eu/ogc/wms/${INSTANCE_ID}`,
  params: {
    LAYERS: 'TRUE-COLOR-S2L2A', // same layer name as in the SH config (copernicus dashboard)
    FORMAT: 'image/png',
    TILED: true,
    MAXCC: 20, // max cloud cover percentage
    TIME: getLastXDaysRange() // date range for mosaicking
  },
  serverType: 'geoserver',
  transition: 0,
})

// Bounding Box (draw) functionality
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
// Create the map and attach it to the div
onMounted(() => {
  map = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({ source: sentinelSource }),
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

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
}
</style>