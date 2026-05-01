<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { notificationStore, notifications, type Notification } from '../../../lib/stores/notifications';
  import { push } from 'svelte-spa-router';
  
  const dispatch = createEventDispatcher();
  
  $: notificationList = $notifications;

  function markAsRead(id: string) {
    notificationStore.markAsRead(id);
  }

  function clearAll() {
    notificationStore.clearRead();
  }

  function markAllAsRead() {
    notificationStore.markAllAsRead();
  }

  function removeNotification(id: string) {
    notificationStore.remove(id);
  }

  function close() {
    dispatch('close');
  }

  function getTimeAgo(timestamp: Date): string {
    const now = new Date();
    const diff = now.getTime() - timestamp.getTime();
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (seconds < 60) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return timestamp.toLocaleDateString();
  }

  function handleNotificationClick(notification: Notification) {
    markAsRead(notification.id);
    
    // Navigate to job if it has a jobUuid
    if (notification.jobUuid) {
      close();
      // Could navigate to a job details page in the future
      // push(`/tools/scraply/job/${notification.jobUuid}`);
    }
  }

  // Play sound for notifications
  function playNotificationSound() {
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      
      // Resume if suspended (browser policy) 
      if (audioContext.state === 'suspended') {
        audioContext.resume();
      }
      
      const now = audioContext.currentTime;
      
      // Play 3 loud beeps
      for (let i = 0; i < 3; i++) {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = i % 2 === 0 ? 880 : 1047;
        oscillator.type = 'square';
        gainNode.gain.value = 1.0;
        
        const beepStart = now + (i * 0.25);
        oscillator.start(beepStart);
        oscillator.stop(beepStart + 0.15);
      }
      console.log('🔊 Notification sound played');
    } catch (err) {
      console.error('Failed to play sound:', err);
    }
  }

  // Demo function to test notifications
  function addTestNotification() {
    notificationStore.add({
      type: 'success',
      title: 'Test Notification',
      message: 'This is a test notification with sound!',
    });
    
    // Play sound with test notification
    playNotificationSound();
  }
</script>

<style>
  @keyframes slide-in-right {
    from {
      transform: translateX(100%);
    }
    to {
      transform: translateX(0);
    }
  }

  .animate-slide-in-right {
    animation: slide-in-right 0.3s ease-out;
  }
</style>

<div class="fixed inset-0 bg-black bg-opacity-30 z-50 flex justify-end transition-opacity" on:click={close}>
  <div
    class="w-96 bg-white h-full shadow-2xl overflow-hidden flex flex-col animate-slide-in-right"
    on:click|stopPropagation
  >
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-900">Activity & Alerts</h2>
      <button
        on:click={close}
        class="text-gray-400 hover:text-gray-600 transition-colors cursor-pointer"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>

    <!-- Actions -->
    <div class="px-6 py-3 bg-gray-50 border-b border-gray-200 flex gap-3">
      <button
        on:click={markAllAsRead}
        class="text-sm text-primary-600 font-medium hover:text-primary-700 cursor-pointer"
      >
        Mark all read
      </button>
      <button
        on:click={clearAll}
        class="text-sm text-gray-600 font-medium hover:text-gray-700 cursor-pointer"
      >
        Clear read
      </button>
    </div>

    <!-- Notifications List -->
    <div class="flex-1 overflow-y-auto">
      {#if notificationList.length === 0}
        <div class="flex flex-col items-center justify-center h-full text-gray-400">
          <svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>
          </svg>
          <p class="text-sm">No notifications</p>
        </div>
      {:else}
        <div class="divide-y divide-gray-200">
          {#each notificationList as notification (notification.id)}
            <div
              class="w-full px-6 py-4 hover:bg-gray-50 transition-colors relative group {!notification.read ? 'bg-primary-50' : ''}"
            >
              <button
                on:click={() => handleNotificationClick(notification)}
                class="w-full text-left"
              >
              <div class="flex items-start gap-3">
                <!-- Icon -->
                <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center {notification.type === 'success' ? 'bg-green-100' : notification.type === 'warning' ? 'bg-yellow-100' : notification.type === 'error' ? 'bg-red-100' : 'bg-blue-100'}">
                  {#if notification.type === 'success'}
                    <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  {:else if notification.type === 'warning'}
                    <svg class="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                  {:else if notification.type === 'error'}
                    <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  {:else}
                    <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  {/if}
                </div>

                <!-- Content -->
                <div class="flex-1 min-w-0 pr-8">
                  <div class="flex items-center justify-between mb-1">
                    <h3 class="text-sm font-semibold text-gray-900">
                      {notification.title}
                    </h3>
                    {#if !notification.read}
                      <span class="w-2 h-2 bg-primary-500 rounded-full"></span>
                    {/if}
                  </div>
                  <p class="text-sm text-gray-600 mb-2">
                    {notification.message}
                  </p>
                  <div class="flex items-center justify-between">
                    <p class="text-xs text-gray-500">
                      {getTimeAgo(notification.timestamp)}
                    </p>
                    {#if notification.jobUuid}
                      <span class="text-xs text-primary-600 font-mono">
                        {notification.jobUuid.slice(0, 8)}
                      </span>
                    {/if}
                  </div>
                </div>
              </div>
              </button>
              
              <!-- Delete button -->
              <button
                on:click={() => removeNotification(notification.id)}
                class="absolute right-2 top-4 opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-gray-200 rounded"
                title="Remove notification"
              >
                <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Test Button (for demo) -->
    <div class="border-t border-gray-200 p-4 space-y-2">
      <button
        on:click={addTestNotification}
        class="w-full px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 transition-colors cursor-pointer"
      >
        Test Notification (with sound)
      </button>
      <div class="text-xs text-center text-gray-500">
        {notificationList.length} total notifications
      </div>
    </div>
  </div>
</div>
