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
import { Style, Fill, Stroke } from 'ol/style'
import { fromLonLat, toLonLat } from 'ol/proj'
import { useMapStore } from '@/stores/map'
import 'ol/ol.css'
import { getArea } from 'ol/sphere'

const mapStore = useMapStore()
const mapContainer = ref(null)
let map = null

// --- map settings ---
const TITILER_URL = 'http://localhost:8001' // titiler URL, server must be running for the XYZ layers to work

const orthophotoSource = new XYZ({
  url:
    `${TITILER_URL}/mosaicjson/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    `?url=/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json`
  // + `&tilesize=512`,
  // tileSize: 512,
  ,
  minZoom: 8,
  maxZoom: 20,
})

const germanySourceOld = new XYZ({
  url:
    `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    `?url=/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt` +
    `&bidx=3&bidx=2&bidx=1` +
    `&rescale=0,3000`,
  //+ `&tilesize=512`,
  // tileSize: 512,
  minZoom: 6,
  maxZoom: 22,
})

const germanySource = new XYZ({
  url:
    `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    `?url=/home/ubuntu/work/saved_data/collections/germany/2021_germany_cog.tif`,
  minZoom: 6,
  maxZoom: 22,
})

// The TileLayer per map type, keyed by the value the nav bar (buttons) sets
const mapLayers = {
  osm: new TileLayer({ source: new OSM() }),
  germany: new TileLayer({ source: germanySource }),
  'germany-slow': new TileLayer({ source: germanySourceOld }),
  orthophoto: new TileLayer({ source: orthophotoSource }),
}

// Show only the map layer matching `type` (set by the nav bar buttons)
function showMapLayer(type) {
  for (const [key, layer] of Object.entries(mapLayers)) {
    layer.setVisible(key === 'osm' || key === type)
  }
}

// --- Bounding box drawing ---
const vectorSource = new VectorSource({ wrapX: false })
const vectorLayer = new VectorLayer({
  source: vectorSource,
  style: new Style({
    stroke: new Stroke({ color: '#0077ff', width: 3 }),
  }),
})

// --- Prediction result overlay ---
const predictionSource = new VectorSource()
const predictionLayer = new VectorLayer({
  source: predictionSource,
  style: new Style({
    fill: new Fill({ color: 'rgba(0, 200, 100, 0.25)' }),
    stroke: new Stroke({ color: '#00c864', width: 1.5 }),
  }),
})
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
    const geometry = event.feature.getGeometry()

    const geoJSON = new GeoJSON().writeFeatureObject(event.feature, {
      featureProjection: 'EPSG:3857',
      dataProjection: 'EPSG:4326',
    })
    const coords = geoJSON.geometry.coordinates[0]
    const lons = coords.map(c => c[0])
    const lats = coords.map(c => c[1])

    mapStore.bbox = {
      min_lon: Math.min(...lons), max_lon: Math.max(...lons),
      min_lat: Math.min(...lats), max_lat: Math.max(...lats),
    }
    mapStore.areaSqm = getArea(geometry)

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
      predictionLayer,             // prediction polygons
      vectorLayer,                 // bbox drawn on top
    ],
    view: new View({
      center: fromLonLat(mapStore.mapCenter),
      zoom: mapStore.mapZoom,
    }),
  })

  const tileErrorHandler = () => mapStore.setError('Tile server could not be reached.')
  for (const source of [orthophotoSource, germanySourceOld, germanySource]) {
    source.on('tileloaderror', tileErrorHandler)
  }

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

// History drawer "view" click -> show that past prediction's polygons again
watch(() => mapStore.viewedPrediction, (geojson) => {
  if (!geojson) return

  predictionSource.clear()
  const features = new GeoJSON().readFeatures(geojson, {
    dataProjection: 'EPSG:4326',
    featureProjection: 'EPSG:3857',
  })
  predictionSource.addFeatures(features)

  const extent = predictionSource.getExtent()
  if (extent.every(Number.isFinite)) {
    map.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 19, duration: 500 })
  }
})

// Nav bar "Run" -> predict
watch(() => mapStore.runTrigger, async () => {
  if (!mapStore.bbox) return

  mapStore.isPredicting = true

  try {
    // Derive satSoruceType from the selected map type
    let satSourceType
    switch (mapStore.mapType) {
      case 'orthophoto':
        satSourceType = 'ortho'
        break
      case 'germany':
      case 'germany-slow':
        satSourceType = 'satellite'
        break
      default:
        console.warn('OSM is not a valid prediction source')
        mapStore.isPredicting = false
        return
    }



    const requestBody = {
      bbox: mapStore.bbox,
      model_type: mapStore.modelType || "tree",  // 'tree' or 'zeroshot'
      source_type: satSourceType,  // 'ortho' or 'satellite'
    }

    if (requestBody.model_type === 'zeroshot') {
      const keywords = mapStore.keyword
        .split(',')
        .map((term) => term.trim())
        .filter(Boolean)

      if (keywords.length === 1) {
        requestBody.keyword = keywords[0]
      } else {
        requestBody.keywords = keywords
      }
    }

    // Send bbox to backend for prediction
    let response
    try {
      response = await fetch('/api/segmentation/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })
    } catch {
      mapStore.setError('Backend server could not be reached.')
      return
    }

    console.log('Prediction request sent:', requestBody)

    const result = await response.json()
    console.log('Prediction result recieved:', result)

    if (!response.ok) {
      mapStore.setError('Prediction failed.')
      console.error('Prediction failed:', result.detail)
      return
    }

    mapStore.clearError()

    const resultUrl = result.prediction?.result_url

    if (!resultUrl) {
      mapStore.setError(
        'Prediction completed, but no result URL was returned.'
      )
      return
    }

    let geojsonResponse

    try {
      geojsonResponse = await fetch(resultUrl)
    } catch {
      mapStore.setError(
        'Prediction completed, but its result file could not be reached.'
      )
      return
    }

    if (!geojsonResponse.ok) {
      mapStore.setError(
        'Prediction completed, but its result file could not be loaded.'
      )
      return
    }

    let geojson

    try {
      geojson = await geojsonResponse.json()
    } catch {
      mapStore.setError(
        'The stored prediction is not valid GeoJSON.'
      )
      return
    }

    predictionSource.clear()

    const features = new GeoJSON().readFeatures(geojson, {
      dataProjection: 'EPSG:4326',
      featureProjection: 'EPSG:3857',
    })

    predictionSource.addFeatures(features)
    mapStore.setCurrentPrediction(result.query_id, geojson)
  } finally {
    mapStore.isPredicting = false
  }
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
}
</style>
