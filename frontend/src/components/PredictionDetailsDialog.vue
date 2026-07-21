<template>
  <v-dialog v-model="open" max-width="480">
    <v-card v-if="item">
      <v-card-title>Prediction details</v-card-title>
      <v-card-subtitle>{{ item.query_id }}</v-card-subtitle>

      <v-card-text>
        <div class="detail-row">
          <span class="detail-label">Task</span>
          <span>{{ formatLabel(item) }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Model</span>
          <span>{{ item.model_name || 'Unknown' }}</span>
        </div>
        <div v-if="isZeroShot(item)" class="detail-row">
          <span class="detail-label">Keyword</span>
          <span>{{ resolveKeyword(item) || 'Unknown' }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Coordinates</span>
          <div class="bbox-coords">
            <span>N {{ item.bbox.max_lat.toFixed(5) }}</span>
            <span>S {{ item.bbox.min_lat.toFixed(5) }}</span>
            <span>E {{ item.bbox.max_lon.toFixed(5) }}</span>
            <span>W {{ item.bbox.min_lon.toFixed(5) }}</span>
          </div>
        </div>
        <div class="detail-row">
          <span class="detail-label">Area</span>
          <span>{{ formatArea(bboxAreaSqm) }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Date created</span>
          <span>{{ formatDate(item.created_at) }}</span>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Polygon } from 'ol/geom'
import { getArea } from 'ol/sphere'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
const open = ref(false)

const item = computed(() => mapStore.currentDetailsItem)

watch(() => mapStore.detailsDialogTrigger, () => {
  open.value = true
})

const bboxAreaSqm = computed(() => {
  const bbox = item.value?.bbox
  if (!bbox) return null

  const ring = [
    [bbox.min_lon, bbox.min_lat],
    [bbox.max_lon, bbox.min_lat],
    [bbox.max_lon, bbox.max_lat],
    [bbox.min_lon, bbox.max_lat],
    [bbox.min_lon, bbox.min_lat],
  ]

  const polygon = new Polygon([ring])
  return getArea(polygon, { projection: 'EPSG:4326' })
})

// Format task label
function formatLabel(item) {
  if (!item.prediction_type) return 'Prediction'
  return item.prediction_type
    .replace(/_/g, ' ') // replace underscores with spaces
    .replace(/\b\w/g, (char) => char.toUpperCase()) // capitalize first letter of each word
}

function isZeroShot(item) {
  return Boolean(item.prediction_type?.toLowerCase().includes('zero_shot'))
}

// Older predictions didn't persist `keywords`; fall back to the summary
// text, which already embeds the keyword (e.g. "Found 113 house polygons/clusters").
function resolveKeyword(item) {
  if (item.keywords && item.keywords.length) return item.keywords.join(', ')
  if (!item.summary) return null

  const forMatch = item.summary.match(/\bfor\s+(.+)$/i)
  if (forMatch) return forMatch[1]

  const countMatch = item.summary.match(/^Found\s+\d+\s+(.+?)\s+polygons\/clusters/i)
  if (countMatch) return countMatch[1]

  return null
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleString()
}

function formatArea(sqm) {
  if (sqm == null) return ''
  return sqm > 1_000_000
    ? `${(sqm / 1_000_000).toFixed(2)} km²`
    : `${Math.round(sqm)} m²`
}
</script>

<style scoped>
.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.detail-label {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.6);
}

.bbox-coords {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 0.85rem;
}
</style>
