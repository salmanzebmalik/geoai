<template>
  <div class="home">
    <NavigationbarLeft />
    <div class="map-area">
      <MapView />
      <LoadingOverlay />
      <ErrorOverlay />
      <InputCoordinatesOverlay />
      <Legend />
    </div>
    <PredictionHistoryDrawer />
  </div>
</template>

<script setup>
import MapView from '../components/Map.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'
import PredictionHistoryDrawer from '../components/PredictionHistoryDrawer.vue'
import LoadingOverlay from '../components/LoadingOverlay.vue'
import ErrorOverlay from '../components/ErrorOverlay.vue'
import InputCoordinatesOverlay from '../components/InputCoordinatesOverlay.vue'
import Legend from '../components/Legend.vue'
</script>

<style scoped>
.home {
  height: 100%;
  display: flex;
}

.map-area {
  flex: 1;
  position: relative;
}
</style>