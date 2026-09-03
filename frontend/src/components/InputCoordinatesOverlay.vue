<template>
  <div v-if="mapStore.coordinateInputOpen" class="overlay-wrapper">
    <v-card class="overlay-card" color="white" elevation="8" rounded="lg">
      <v-card-text class="card-body">
        <div class="title-row">
          <v-icon size="20" class="mr-2">mdi-pencil</v-icon>
          Enter Bounding Box Coordinates 
        </div>

        <div class="coord-grid">
          <v-text-field
            v-model.number="north"
            label="North (lat)"
            type="number"
            step="any"
            density="compact"
            variant="outlined"
            hide-details
          />
          <v-text-field
            v-model.number="south"
            label="South (lat)"
            type="number"
            step="any"
            density="compact"
            variant="outlined"
            hide-details
          />
          <v-text-field
            v-model.number="east"
            label="East (lon)"
            type="number"
            step="any"
            density="compact"
            variant="outlined"
            hide-details
          />
          <v-text-field
            v-model.number="west"
            label="West (lon)"
            type="number"
            step="any"
            density="compact"
            variant="outlined"
            hide-details
          />
        </div>

        <div v-if="errorText" class="error-text">{{ errorText }}</div>
      </v-card-text>

      <v-card-actions class="card-actions">
        <v-btn variant="text" @click="cancel">Cancel</v-btn>
        <v-spacer />
        <v-btn color="success" variant="tonal" :disabled="!isValid" @click="apply">
          Apply
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

const north = ref(null)
const south = ref(null)
const east = ref(null)
const west = ref(null)

// Prefill fields with the current bbox whenever the overlay opens
watch(() => mapStore.coordinateInputOpen, (open) => {
  if (!open) return
  const bbox = mapStore.bbox
  north.value = bbox ? bbox.max_lat : null
  south.value = bbox ? bbox.min_lat : null
  east.value = bbox ? bbox.max_lon : null
  west.value = bbox ? bbox.min_lon : null
})

function isNumber(v) {
  return typeof v === 'number' && !Number.isNaN(v)
}

const errorText = computed(() => {
  if (![north.value, south.value, east.value, west.value].every(isNumber)) {
    return null // stay quiet until all four fields are filled
  }
  if (north.value <= south.value) return 'North must be greater than South.'
  if (east.value <= west.value) return 'East must be greater than West.'
  if (north.value > 90 || south.value < -90) return 'Latitude must be between -90 and 90.'
  if (east.value > 180 || west.value < -180) return 'Longitude must be between -180 and 180.'
  return null
})

const isValid = computed(() =>
  [north.value, south.value, east.value, west.value].every(isNumber) && !errorText.value
)

function cancel() {
  mapStore.coordinateInputOpen = false
}

function apply() {
  if (!isValid.value) return

  // Only N/S/E/W bounds are taken as input, so the box is always axis-aligned;
  // the remaining two corners (NE/SW) are derived, never entered directly.
  mapStore.bbox = {
    min_lon: west.value, max_lon: east.value,
    min_lat: south.value, max_lat: north.value,
  }

  // Map.vue owns the map/geometry logic - this just tells it to redraw + recompute area
  mapStore.triggerManualBboxUpdate()

  mapStore.coordinateInputOpen = false
}
</script>

<style scoped>
.overlay-wrapper {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 10;
}

.overlay-card {
  width: 420px;
  pointer-events: all;
}

.card-body {
  padding: 28px 28px 8px;
}

.title-row {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.87);
  margin-bottom: 20px;
}

.hint {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.6);
  margin-bottom: 16px;
}

.coord-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.error-text {
  margin-top: 12px;
  font-size: 13px;
  color: #c62828;
}

.card-actions {
  padding: 8px 28px 20px;
}
</style>
