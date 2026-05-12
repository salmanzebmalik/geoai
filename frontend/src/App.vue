<template>
  <v-app>
    <v-app-bar>
      <div class="left-section">
        <img src="/geoai_icon_pin.svg" alt="GeoAI Icon" class="app-icon"/>
        <v-app-bar-title style="font-weight: bold;">
          GeoAI Monitor
        </v-app-bar-title>
        <v-btn variant="text" to="/">Dashboard</v-btn>
        <v-btn variant="text" to="/about">About</v-btn>
      </div>
    </v-app-bar>

    <v-main>
      <RouterView />
    </v-main>
    <NavigationbarLeft></NavigationbarLeft>
  </v-app>
</template>

<script setup>
import { RouterView } from 'vue-router'
import NavigationbarLeft from './components/NavigationbarLeft.vue'
</script>

<style>
.left-section {
  display: flex;
  align-items: center;
  margin-left: 20px;
}

.left-section .app-icon {
  width: 28px;
  height: 28px;
  margin-right: 10px;
}

.left-section .v-app-bar-title {
  margin-right: 20px;
}
</style>
