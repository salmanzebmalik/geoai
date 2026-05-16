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
import { fromLonLat } from 'ol/proj'
import 'ol/ol.css'
import Draw, { createBox } from 'ol/interaction/Draw.js'
import VectorLayer from 'ol/layer/Vector.js'
import VectorSource from 'ol/source/Vector.js'
import { useMapStore } from '@/stores/map'
import GeoJSON from 'ol/format/GeoJSON.js'

const mapStore = useMapStore()
const mapContainer = ref(null)
let map = null

const MUENSTER_COORDS = fromLonLat([7.6261, 51.9607])

// --- Sentinel Hub WMS config ---
const INSTANCE_ID = import.meta.env.VITE_SENTINELHUB_INSTANCE_ID

const sentinelSource = new TileWMS({
  url: `https://sh.dataspace.copernicus.eu/ogc/wms/${INSTANCE_ID}`,
  params: {
    LAYERS: 'TRUE-COLOR-S2L2A',   // layer name configured in your SH config
    FORMAT: 'image/png',
    TILED: true,
    MAXCC: 20,                    // max cloud cover %
    TIME: '2026-03-01/2026-04-30' // date range for mosaicking
  },
  serverType: 'geoserver',        // tells OL how to build tile requests
  transition: 0,
})

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

// Optional: expose a method to update the TIME param dynamically
function setDateRange(start, end) {
  sentinelSource.updateParams({ TIME: `${start}/${end}` })
}

onMounted(() => {
  map = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({ source: sentinelSource }),
      vectorLayer,
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

watch(() => mapStore.startDrawingTrigger, () => {
  startDrawing()
})

defineExpose({ setDateRange })
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
}
</style>