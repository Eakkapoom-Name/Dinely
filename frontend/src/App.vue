<script setup>
import { onMounted } from 'vue'

onMounted(() => {
  document.addEventListener('touchstart', function(){}, { passive: true })
})
</script>

<template>
    <router-view />
</template>
