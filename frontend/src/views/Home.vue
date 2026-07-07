<template>
  <div class="home">
    <NavigationbarLeft />
    <div class="map-area">
      <MapView />
      <LoadingOverlay />
      <ErrorOverlay />
    </div>
  </div>
</template>

<script setup>
import MapView from '../components/Map.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'
import LoadingOverlay from '../components/LoadingOverlay.vue'
import ErrorOverlay from '../components/ErrorOverlay.vue'
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