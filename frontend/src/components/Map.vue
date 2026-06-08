<template>
  <div ref="mapContainer" class="map-container" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import OSM from 'ol/source/OSM'
import XYZ from 'ol/source/XYZ'
import VectorLayer from 'ol/layer/Vector.js'
import VectorSource from 'ol/source/Vector.js'
import Draw, { createBox } from 'ol/interaction/Draw.js'
import GeoJSON from 'ol/format/GeoJSON.js'
import { fromLonLat, toLonLat } from 'ol/proj'
import { useMapStore } from '@/stores/map'
import 'ol/ol.css'

const mapStore = useMapStore()
const mapContainer = ref(null)
let map = null

// --- map settings ---
const TITILER_URL = 'http://localhost:10000' // titiler URL, server must be running for the XYZ layers to work

const orthophotoSource = new XYZ({
  url:
    `${TITILER_URL}/mosaicjson/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    `?url=/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json` +
    `&tilesize=512`,
  tileSize: 512,
  minZoom: 8,
  maxZoom: 20,
})

const sentinelSource = new XYZ({
  url:
    `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    `?url=/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt` +
    `&bidx=3&bidx=2&bidx=1` +
    `&rescale=0,3000` +
    `&tilesize=512`,
  tileSize: 512,
  minZoom: 6,
  maxZoom: 22,
})

// The TileLayer per map type, keyed by the value the nav bar (buttons) sets
const mapLayers = {
  osm: new TileLayer({ source: new OSM() }),
  sentinel: new TileLayer({ source: sentinelSource }),
  orthophoto: new TileLayer({ source: orthophotoSource }),
}

// Show only the map layer matching `type` (set by the nav bar buttons)
function showMapLayer(type) {
  for (const [key, layer] of Object.entries(mapLayers)) {
    layer.setVisible(key === type)
  }
}

// --- Bounding box drawing ---
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

// --- OpenLayers map setup ---
onMounted(() => {
  map = new Map({
    target: mapContainer.value,
    layers: [
      ...Object.values(mapLayers), // all map layers
      vectorLayer, // bbox drawn on top
    ],
    view: new View({
      center: fromLonLat(mapStore.mapCenter),
      zoom: mapStore.mapZoom,
    }),
  })

  // Apply whatever the store (nav bar buttons) has set as map type
  showMapLayer(mapStore.mapType)

  map.on('moveend', () => {
    const view = map.getView()
    mapStore.mapCenter = toLonLat(view.getCenter())
    mapStore.mapZoom = view.getZoom()
  })
})

onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
})

// Nav bar changes mapType -> swap visible map layer
watch(() => mapStore.mapType, (type) => showMapLayer(type))

// Nav bar "Select Area" -> start drawing
watch(() => mapStore.startDrawingTrigger, () => startDrawing())
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
}
</style>