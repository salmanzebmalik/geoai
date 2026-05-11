<template>
  <v-app>
    <NavigationbarLeft />
    <v-main>
      <MapOpenLayers />
    </v-main>
  </v-app>
</template>

<script setup>
import MapOpenLayers from './components/MapOpenLayers.vue'
import NavigationbarLeft from './components/NavigationbarLeft.vue'
</script>
