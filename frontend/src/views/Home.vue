<template>
  <div class="home">
    <MapView />
    <NavigationbarLeft />
    <PredictionHistoryDrawer />
    <LoadingOverlay />
  </div>
</template>

<script setup>
import MapView from '../components/Map.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'
import PredictionHistoryDrawer from '../components/PredictionHistoryDrawer.vue'
import LoadingOverlay from '../components/LoadingOverlay.vue'
</script>

<style scoped>
.home {
  height: 100%;
  position: relative;
}
</style>