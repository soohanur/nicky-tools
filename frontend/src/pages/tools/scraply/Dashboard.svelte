<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { push } from 'svelte-spa-router';
  import Controls from './Controls.svelte';
  import UploadedFiles from './UploadedFiles.svelte';
  import ExtractionLogs from './ExtractionLogs.svelte';
  import Settings from './Settings.svelte';
  import NotificationPanel from './NotificationPanel.svelte';
  import { unreadCount } from '../../../lib/stores/notifications';
  import { websocketService } from '../../../lib/services/websocket';

  let activeTab = 'controls';
  let showNotifications = false;
  let controlsComponent: Controls;

  // Reactive state for buttons
  let canExport = false;
  let canCancel = false;
  let updateInterval: any = null;
  
  // Update button states continuously
  function updateButtonStates() {
    if (controlsComponent && typeof controlsComponent.getJobInfo === 'function') {
      const jobInfo = controlsComponent.getJobInfo();
      canExport = jobInfo.canExport;
      canCancel = jobInfo.canCancel;
    }
  }

  onMount(() => {
    // Update button states every 500ms to keep them in sync
    updateInterval = setInterval(updateButtonStates, 500);

    // Initialize WebSocket connection for real-time notifications
    websocketService.connect();
  });

  onDestroy(() => {
    if (updateInterval) clearInterval(updateInterval);
    // Note: We don't disconnect WebSocket here as it should persist across page navigation
  });

  function handleBack() {
    push('/home');
  }

  function handleExport() {
    if (controlsComponent && typeof controlsComponent.handleExport === 'function') {
      controlsComponent.handleExport();
    }
  }

  function handleCancel() {
    if (controlsComponent && typeof controlsComponent.handleCancel === 'function') {
      controlsComponent.handleCancel();
    }
  }
</script>

<div class="min-h-screen flex flex-col lg:flex-row" style="background-color: #F2EFE7;">
  <!-- Sidebar -->
  <div class="w-full lg:w-64 bg-white flex-shrink-0 flex flex-col lg:min-h-screen">
    <!-- Back Button -->
    <button
      on:click={handleBack}
      class="flex items-center gap-2 px-4 lg:px-6 py-3 lg:py-4 text-sm text-gray-600 hover:text-gray-900 border-b border-gray-200 cursor-pointer"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
      </svg>
      <span>Back to Tools</span>
    </button>

    <!-- Logo Section -->
    <div class="hidden lg:block px-6 py-6 border-b border-gray-200">
      <div class="flex items-center gap-3">
        <div class="w-12 h-12 bg-primary-500 rounded-xl flex items-center justify-center">
          <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
          </svg>
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">Scrapely</h2>
          <p class="text-xs text-gray-500">v1.3</p>
        </div>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex flex-row lg:flex-col lg:flex-1 px-2 lg:px-4 py-2 lg:py-6 gap-1 lg:gap-0 overflow-x-auto">
      <button
        on:click={() => activeTab = 'controls'}
        class="flex-shrink-0 lg:w-full flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2 lg:py-3 text-sm rounded-lg lg:mb-2 transition-colors cursor-pointer whitespace-nowrap {activeTab === 'controls' ? 'bg-primary-50 text-primary-600 font-medium' : 'text-gray-700 hover:bg-gray-50'}"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path>
        </svg>
        <span>Controls</span>
      </button>

      <button
        on:click={() => activeTab = 'uploaded'}
        class="flex-shrink-0 lg:w-full flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2 lg:py-3 text-sm rounded-lg lg:mb-2 transition-colors cursor-pointer whitespace-nowrap {activeTab === 'uploaded' ? 'bg-primary-50 text-primary-600 font-medium' : 'text-gray-700 hover:bg-gray-50'}"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
        </svg>
        <span>Uploaded Files</span>
      </button>

      <button
        on:click={() => activeTab = 'logs'}
        class="flex-shrink-0 lg:w-full flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2 lg:py-3 text-sm rounded-lg lg:mb-2 transition-colors cursor-pointer whitespace-nowrap {activeTab === 'logs' ? 'bg-primary-50 text-primary-600 font-medium' : 'text-gray-700 hover:bg-gray-50'}"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
        </svg>
        <span>Extraction Logs</span>
      </button>

      <button
        on:click={() => activeTab = 'settings'}
        class="flex-shrink-0 lg:w-full flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2 lg:py-3 text-sm rounded-lg transition-colors cursor-pointer whitespace-nowrap {activeTab === 'settings' ? 'bg-primary-50 text-primary-600 font-medium' : 'text-gray-700 hover:bg-gray-50'}"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
        </svg>
        <span>Settings</span>
      </button>
    </nav>
  </div>

  <!-- Main Content -->
  <div class="flex-1 flex flex-col">
    <!-- Top Bar with Export and Notifications -->
    <div class="bg-white border-b border-gray-200 px-4 lg:px-6 py-3 lg:py-4 flex items-center justify-end gap-3 lg:gap-4">
      <button
        on:click={handleExport}
        disabled={!canExport}
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all {canExport ? 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 cursor-pointer' : 'text-gray-400 bg-gray-100 border border-gray-200 cursor-not-allowed opacity-50'}"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
        </svg>
        <span>Export</span>
      </button>

      <button
        on:click={handleCancel}
        disabled={!canCancel}
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all {canCancel ? 'text-white bg-red-500 hover:bg-red-600 cursor-pointer' : 'text-gray-400 bg-gray-100 border border-gray-200 cursor-not-allowed opacity-50'}"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
        <span>Cancel</span>
      </button>

      <button
        on:click={() => showNotifications = !showNotifications}
        class="relative p-2 text-gray-600 hover:text-gray-900 transition-colors cursor-pointer"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>
        </svg>
        {#if $unreadCount > 0}
          <span class="absolute -top-1 -right-1 w-5 h-5 bg-primary-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {$unreadCount > 99 ? '99+' : $unreadCount}
          </span>
        {/if}
      </button>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-auto">
      {#if activeTab === 'controls'}
        <Controls bind:this={controlsComponent} />
      {:else if activeTab === 'uploaded'}
        <UploadedFiles />
      {:else if activeTab === 'logs'}
        <ExtractionLogs />
      {:else if activeTab === 'settings'}
        <Settings />
      {/if}
    </div>
  </div>

  <!-- Notification Panel -->
  {#if showNotifications}
    <NotificationPanel on:close={() => showNotifications = false} />
  {/if}
</div>
