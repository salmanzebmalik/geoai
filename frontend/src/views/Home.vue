<template>
  <div class="home">
    <MapSentinel v-if="mapStore.mapType === 'sentinel'" />
    <MapOpenLayers v-else />
    <NavigationbarLeft></NavigationbarLeft>
  </div>
</template>

<script setup>
import { useMapStore } from '@/stores/map'
import MapOpenLayers from '../components/MapOpenLayers.vue'
import MapSentinel from '../components/MapSentinel.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'

const mapStore = useMapStore()
</script>

<style scoped>
.home {
  height: 100%;
}
</style>