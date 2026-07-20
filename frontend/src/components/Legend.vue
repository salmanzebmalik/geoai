<template>
  <div
    v-if="mapStore.hasPrediction"
    class="legend"
    :class="{ 'legend--shifted': mapStore.historyDrawerOpen }"
  >
    <span class="swatch" />
    <span class="label">Detected objects</span>
  </div>
</template>

<script setup>
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
</script>

<style scoped>
.legend {
  position: fixed;
  top: 84px;
  right: 76px;
  z-index: 1005;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 12px;
  background-color: #1b2e1be1;
  border-radius: 8px;
  font-size: 13px;
  color: #ffffff;
  white-space: nowrap;
  transition: right 0.2s ease;
}

.legend--shifted {
  right: 416px;
}

.swatch {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background-color: rgba(0, 200, 100, 0.35);
  border: 1.5px solid #00c864;
}
</style>
