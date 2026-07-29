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
import Feature from 'ol/Feature.js'
import Polygon from 'ol/geom/Polygon.js'
import Draw, { createBox } from 'ol/interaction/Draw.js'
import GeoJSON from 'ol/format/GeoJSON.js'
import { Style, Fill, Stroke } from 'ol/style'
import { fromLonLat, toLonLat } from 'ol/proj'
import { useMapStore } from '@/stores/map'
import 'ol/ol.css'
import { getArea } from 'ol/sphere'

const mapStore = useMapStore() // Pinia store
const mapContainer = ref(null)
let map = null

// titiler URL, server must be running for the XYZ layers to work
const TITILER_URL = import.meta.env.VITE_TITILER_URL || '/image-api'

// one titiler-pgstac collection per year (data: 2018-2024)
const SENTINEL_COLLECTIONS = [
  'sentinel-2-l2a-worldwide-2018',
  'sentinel-2-l2a-worldwide-2019',
  'sentinel-2-l2a-worldwide-2020',
  'sentinel-2-l2a-worldwide-2021',
  'sentinel-2-l2a-worldwide-2022',
  'sentinel-2-l2a-worldwide-2023',
  'sentinel-2-l2a-worldwide-2024',
]

// source for NRW orthophoto imagery
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

// source for germany satellite imagery
const germanySource = new XYZ({
  url:
    `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    `?url=/home/ubuntu/work/saved_data/collections/germany/2021_germany_cog.tif`,
  minZoom: 6,
  maxZoom: 22,
})

// source for Sentinel-2 imagery, filled in by refreshSentinelLayer() once a STAC search has been registered (no fixed file path like the sources above)
const sentinelSource = new XYZ({
  minZoom: 9,
  maxNativeZoom: 14,
  maxZoom: 19,
})

// TileLayer per map type
const mapLayers = {
  osm: new TileLayer({ source: new OSM() }),
  germany: new TileLayer({ source: germanySource }),
  orthophoto: new TileLayer({ source: orthophotoSource }),
  sentinel: new TileLayer({ source: sentinelSource }),
}

// Register a titiler-pgstac STAC search for the current date range / cloud cover filter, then point sentinelSource at the resulting tiles
// See image_pipeline/stac_viewer/stac_map.html for the two-step pattern this mirrors
async function refreshSentinelLayer() {
  const from = mapStore.sentinelDateFrom
  const to = mapStore.sentinelDateTo
  const maxCloudCover = mapStore.sentinelMaxCloudCover

  let response
  try {
    response = await fetch(`${TITILER_URL}/searches/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collections: SENTINEL_COLLECTIONS,
        datetime: `${from}T00:00:00Z/${to}T23:59:59Z`,
        query: {
          'eo:cloud_cover': { lte: maxCloudCover },
        },
      }),
    })
  } catch {
    mapStore.setError('Tile server could not be reached.')
    return
  }

  if (!response.ok) {
    mapStore.setError('Sentinel search failed: HTTP ' + response.status)
    return
  }

  const search = await response.json()
  sentinelSource.setUrl(
    `${TITILER_URL}/searches/${search.id}/tiles/WebMercatorQuad/{z}/{x}/{y}` +
    '?assets=B04&assets=B03&assets=B02' +
    '&rescale=0,3000' +
    '&nodata=0'
  )
}

// Switch which map layer is visible
function showMapLayer(type) {
  for (const [key, layer] of Object.entries(mapLayers)) {
    layer.setVisible(key === 'osm' || key === type) // OSM is always visible as base layer
  }
}

// Bounding box drawing layer
const vectorSource = new VectorSource({ wrapX: false }) //container for bbox vector features

const vectorLayer = new VectorLayer({
  source: vectorSource,
  style: new Style({
    stroke: new Stroke({ color: '#0077ff', width: 3 }),
  }),
})

// Prediction result overlay
const predictionSource = new VectorSource() // container for prediction polygons

const predictionLayer = new VectorLayer({
  source: predictionSource,
  style: new Style({
    fill: new Fill({ color: 'rgba(0, 200, 100, 0.25)' }),
    stroke: new Stroke({ color: '#00c864', width: 1.5 }),
  }),
})
predictionSource.on(['addfeature', 'clear'], () => {
  mapStore.hasPrediction = predictionSource.getFeatures().length > 0
})

let draw = null

// Display prediction result on the map and zoom
function displayPrediction(geojson) {
  predictionSource.clear()
  const features = new GeoJSON().readFeatures(geojson, {
    dataProjection: 'EPSG:4326',
    featureProjection: 'EPSG:3857',
  })
  predictionSource.addFeatures(features)

  // zoom in
  const extent = predictionSource.getExtent()
  if (extent.every(Number.isFinite)) {
    map.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 19, duration: 500 })
  }
}

function startDrawing() {
  vectorSource.clear()
  if (draw) map.removeInteraction(draw)

  draw = new Draw({
    source: vectorSource,
    type: 'Circle',
    geometryFunction: createBox(),
  })

  // when drawing is finished
  draw.on('drawend', (event) => {
    const geometry = event.feature.getGeometry() // polygon

    // Convert to GeoJSON and extract coordinates
    const geoJSON = new GeoJSON().writeFeatureObject(event.feature, {
      featureProjection: 'EPSG:3857',
      dataProjection: 'EPSG:4326',
    })
    const coords = geoJSON.geometry.coordinates[0] // outer ring of polygon
    const lons = coords.map(c => c[0])
    const lats = coords.map(c => c[1])

    // get bbox corners
    mapStore.bbox = {
      min_lon: Math.min(...lons), max_lon: Math.max(...lons),
      min_lat: Math.min(...lats), max_lat: Math.max(...lats),
    }
    mapStore.areaSqm = getArea(geometry) // projection-corrected area in square meters

    map.removeInteraction(draw)
    draw = null
  })

  map.addInteraction(draw) // activate drawing interaction
}

// Draw the box for a manually-entered bbox (mapStore.bbox already holds min/max lon/lat)
function drawManualBbox() {
  const bbox = mapStore.bbox
  if (!bbox) return

  if (draw) {
    map.removeInteraction(draw) // cancel an in-progress hand-draw, if any
    draw = null
  }
  vectorSource.clear()

  const ring = [
    [bbox.min_lon, bbox.min_lat],
    [bbox.max_lon, bbox.min_lat],
    [bbox.max_lon, bbox.max_lat],
    [bbox.min_lon, bbox.max_lat],
    [bbox.min_lon, bbox.min_lat],
  ].map((coord) => fromLonLat(coord))
  const geometry = new Polygon([ring])
  vectorSource.addFeature(new Feature(geometry))

  mapStore.areaSqm = getArea(geometry) // same spherical calculation as the draw tool

  // Manual coordinates can be far from the current view, so bring them into frame
  map.getView().fit(geometry.getExtent(), { padding: [50, 50, 50, 50], maxZoom: 19, duration: 500 })
}

// OpenLayers map setup
onMounted(() => {
  map = new Map({
    target: mapContainer.value,
    layers: [
      ...Object.values(mapLayers), // all map layers
      predictionLayer,             // prediction polygons
      vectorLayer,                 // bbox drawn on top
    ],
    view: new View({    // initial center/zoom
      center: fromLonLat(mapStore.mapCenter),
      zoom: mapStore.mapZoom,
    }),
  })

  // Apply selected map type
  showMapLayer(mapStore.mapType)
  if (mapStore.mapType === 'sentinel') refreshSentinelLayer()

  // Update store with new center/zoom when map is moved
  map.on('moveend', () => {
    const view = map.getView()
    mapStore.mapCenter = toLonLat(view.getCenter())
    mapStore.mapZoom = view.getZoom()
  })
})

// Clean up map on unmount
onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
})

// Nav bar changes mapType -> swap visible map layer
watch(() => mapStore.mapType, (type) => {
  showMapLayer(type)
  if (type === 'sentinel') refreshSentinelLayer() // (re-)register the STAC search for the current filters
})

// Nav bar date range / cloud cover filter changed -> re-register the STAC search
watch(() => mapStore.sentinelRefreshTrigger, () => {
  if (mapStore.mapType === 'sentinel') refreshSentinelLayer()
})

// Nav bar "Select Area" -> start drawing
watch(() => mapStore.startDrawingTrigger, () => startDrawing())

// Manual coordinate input -> redraw box + recompute area from mapStore.bbox
watch(() => mapStore.manualBboxTrigger, () => drawManualBbox())

// History drawer click -> show past prediction's polygons
watch(() => mapStore.viewedPrediction, (geojson) => {
  if (!geojson) return
  displayPrediction(geojson)
})

// Click on Run -> predict
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
        satSourceType = 'satellite'
        break
      default:
        console.warn('OSM is not a valid prediction source')
        mapStore.isPredicting = false
        return
    }

    // assembles POST request body for prediction
    const requestBody = {
      bbox: mapStore.bbox,
      model_type: mapStore.modelType || "tree",  // tree if not set
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

    // Send prediction request to backend
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

    // prediction result
    const result = await response.json()
    console.log('Prediction result recieved:', result)

    if (!response.ok) {
      mapStore.setError('Prediction failed.')
      console.error('Prediction failed:', result.detail)
      return
    }

    mapStore.clearError()

    // Get the result URL from the prediction response
    const resultUrl = result.prediction?.result_url

    if (!resultUrl) {
      mapStore.setError(
        'Prediction completed, but no result URL was returned.'
      )
      return
    }


    // Fetch the GeoJSON result from the result URL
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

    // get the GeoJSON from the response
    let geojson

    try {
      geojson = await geojsonResponse.json()
    } catch {
      mapStore.setError(
        'The stored prediction is not valid GeoJSON.'
      )
      return
    }

    displayPrediction(geojson)
    mapStore.setCurrentPrediction(result.query_id, geojson, result.prediction)
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
