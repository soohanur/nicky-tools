<script lang="ts">
  import { onMount } from 'svelte';
  import { systemAPI, type SystemStats, type HealthCheck } from '../../../lib/api';

  let health: HealthCheck | null = null;
  let stats: SystemStats | null = null;
  let loading = true;
  let error = '';
  let success = '';
  let autoRefresh = false;
  let refreshInterval: any = null;

  // Settings
  let maxWorkers = 1;
  let originalMaxWorkers = 1;
  let savingConfig = false;

  onMount(() => {
    loadSystemInfo();
    loadWorkerConfig();
  });

  async function loadSystemInfo() {
    loading = true;
    error = '';
    try {
      [health, stats] = await Promise.all([
        systemAPI.getHealth(),
        systemAPI.getStats()
      ]);
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to load system information';
      console.error('Error loading system info:', err);
    } finally {
      loading = false;
    }
  }

  async function loadWorkerConfig() {
    try {
      const config = await systemAPI.getWorkerConfig();
      maxWorkers = config.max_workers;
      originalMaxWorkers = config.max_workers;
    } catch (err: any) {
      console.error('Error loading worker config:', err);
    }
  }

  async function saveWorkerConfig() {
    console.log('saveWorkerConfig called', { maxWorkers, originalMaxWorkers });
    if (maxWorkers === originalMaxWorkers) {
      console.log('No changes detected, skipping save');
      return;
    }

    savingConfig = true;
    error = '';
    success = '';

    try {
      console.log('Calling API to update worker config to:', maxWorkers);
      const result = await systemAPI.updateWorkerConfig(maxWorkers);
      console.log('API response:', result);
      originalMaxWorkers = maxWorkers;
      success = result.message;
      
      // Reload system info to get updated worker count
      await loadSystemInfo();
      
      // Clear success message after 5 seconds
      setTimeout(() => {
        success = '';
      }, 5000);
    } catch (err: any) {
      console.error('Error updating worker config:', err);
      error = err.response?.data?.detail || err.message || 'Failed to update worker configuration';
      // Reset to original value on error
      maxWorkers = originalMaxWorkers;
    } finally {
      savingConfig = false;
    }
  }

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    if (autoRefresh) {
      refreshInterval = setInterval(loadSystemInfo, 5000);
    } else {
      if (refreshInterval) clearInterval(refreshInterval);
    }
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  }

  $: overallHealth = health?.status === 'healthy' && 
                     health?.database === 'healthy' && 
                     health?.redis === 'healthy' && 
                     health?.celery.includes('healthy');
</script>

<div class="p-8 bg-[#f5f5f5] min-h-screen">
  <div class="max-w-2xl mx-auto">
    <div class="bg-white rounded-lg shadow-sm p-12 text-center">
      <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
        </svg>
      </div>
      <h2 class="text-2xl font-bold text-gray-900 mb-3">Settings</h2>
      <p class="text-gray-600 mb-2">Configuration options coming soon</p>
      <p class="text-sm text-gray-500">Settings panel is currently under development</p>
    </div>
  </div>
</div>
