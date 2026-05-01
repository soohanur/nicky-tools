<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { jobsAPI } from '../../../lib/api';
  import type { Job } from '../../../lib/types';

  let jobs: Job[] = [];
  let filteredJobs: Job[] = [];
  let loading = true;
  let error = '';
  let searchQuery = '';
  let autoRefresh = true;
  let refreshInterval: any = null;

  onMount(() => {
    loadJobs();
    if (autoRefresh) {
      refreshInterval = setInterval(loadJobs, 5000);
    }
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });

  async function loadJobs() {
    try {
      // Load completed, cancelled, and failed jobs
      const allJobs: Job[] = [];
      
      const completedResponse = await jobsAPI.listJobs({ status_filter: 'completed' });
      if (completedResponse.jobs) allJobs.push(...completedResponse.jobs);
      
      const cancelledResponse = await jobsAPI.listJobs({ status_filter: 'cancelled' });
      if (cancelledResponse.jobs) allJobs.push(...cancelledResponse.jobs);
      
      const failedResponse = await jobsAPI.listJobs({ status_filter: 'failed' });
      if (failedResponse.jobs) allJobs.push(...failedResponse.jobs);
      
      // Sort by created_at descending
      allJobs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      
      jobs = allJobs;
      filteredJobs = allJobs;
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to load jobs';
      console.error('Error loading jobs:', err);
    } finally {
      loading = false;
    }
  }

  async function handleDownload(job: Job) {
    // Allow download if job has processed at least 1 row
    if (!job.output_file_path || (job.processed_rows || 0) === 0) {
      error = 'No data available to download';
      return;
    }
    
    try {
      const blob = await jobsAPI.downloadJobResult(job.job_uuid);
      const url = window.URL.createObjectURL(blob);
      
      // Create enriched filename from display_filename
      const originalName = job.display_filename || 'output.csv';
      const nameWithoutExt = originalName.replace(/\.[^/.]+$/, '');
      const filename = `${nameWithoutExt}_enriched.csv`;
      
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      error = '';
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to download file';
      console.error('Error downloading:', err);
    }
  }

  async function handleDelete(job: Job) {
    if (!confirm(`Are you sure you want to delete "${job.display_filename || 'this job'}"?`)) {
      return;
    }

    try {
      await jobsAPI.deleteJob(job.job_uuid);
      // Remove from local list
      jobs = jobs.filter(j => j.job_uuid !== job.job_uuid);
      filteredJobs = filteredJobs.filter(j => j.job_uuid !== job.job_uuid);
      error = '';
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to delete job';
      console.error('Error deleting:', err);
    }
  }

  function getStatusBadge(status: string): { class: string, text: string } {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return { class: 'bg-green-500 text-white', text: 'READY' };
      case 'FAILED':
        return { class: 'bg-red-500 text-white', text: 'FAILED' };
      case 'CANCELLED':
        return { class: 'bg-yellow-500 text-white', text: 'CANCELLED' };
      default:
        return { class: 'bg-gray-500 text-white', text: status.toUpperCase() };
    }
  }

  function formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString('nl-NL', { 
      timeZone: 'Europe/Amsterdam',
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    }) + ' at ' + date.toLocaleTimeString('nl-NL', { 
      timeZone: 'Europe/Amsterdam',
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  }

  function formatFileSize(bytes: number): string {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
  }

  function getOutputFilename(job: Job): string {
    const originalName = job.display_filename || 'output.csv';
    const nameWithoutExt = originalName.replace(/\.[^/.]+$/, '');
    return `${nameWithoutExt}_enriched.csv`;
  }

  function calculateFileSize(job: Job): number {
    // Estimate: ~100 bytes per row average
    return (job.processed_rows || 0) * 100;
  }

  $: {
    if (searchQuery.trim()) {
      filteredJobs = jobs.filter(job => 
        (job.display_filename?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
        (job.name?.toLowerCase() || '').includes(searchQuery.toLowerCase())
      );
    } else {
      filteredJobs = jobs;
    }
  }

  $: totalExtractions = jobs.length;
  $: successfulJobs = jobs.filter(j => j.status.toUpperCase() === 'COMPLETED').length;
  $: failedJobs = jobs.filter(j => j.status.toUpperCase() === 'FAILED' || j.status.toUpperCase() === 'CANCELLED').length;
</script>

<div class="p-6 bg-[#f5f5f5] min-h-screen">
  {#if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <span class="text-sm text-red-800">{error}</span>
      </div>
      <button on:click={() => error = ''} class="text-red-600 hover:text-red-800 cursor-pointer">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>
  {/if}

  <!-- Stats Cards -->
  <div class="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-6">
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
        </div>
        <div>
          <p class="text-xs text-gray-500">Total Extractions</p>
          <p class="text-2xl font-bold text-blue-600">{totalExtractions}</p>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
        </div>
        <div>
          <p class="text-xs text-gray-500">Successful</p>
          <p class="text-2xl font-bold text-green-600">{successfulJobs}</p>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
        </div>
        <div>
          <p class="text-xs text-gray-500">Failed</p>
          <p class="text-2xl font-bold text-red-600">{failedJobs}</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Search Bar -->
  <div class="mb-4">
    <div class="relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
      </svg>
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search extraction logs..."
        class="w-full pl-10 pr-4 py-2 text-sm bg-white rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
      />
    </div>
  </div>

  <!-- Jobs List -->
  {#if loading}
    <div class="text-center py-8">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-primary-500"></div>
      <p class="mt-3 text-sm text-gray-600">Loading extractions...</p>
    </div>
  {:else if filteredJobs.length === 0}
    <div class="bg-white rounded-lg shadow-sm p-8 text-center">
      <div class="w-14 h-14 bg-gray-100 rounded-lg flex items-center justify-center mx-auto mb-3">
        <svg class="w-7 h-7 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
        </svg>
      </div>
      <h3 class="text-base font-semibold text-gray-900 mb-1">No extraction logs found</h3>
      <p class="text-sm text-gray-500">{searchQuery ? 'Try a different search term' : 'Complete jobs will appear here'}</p>
    </div>
  {:else}
    <div class="bg-white rounded-lg shadow-sm">
      <!-- Header -->
      <div class="border-b border-gray-200 px-4 py-3">
        <h2 class="text-base font-semibold text-gray-900">Extraction Logs ({filteredJobs.length})</h2>
      </div>

      <!-- Jobs Table -->
      <div class="p-4">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Filename
                </th>
                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Rows
                </th>
                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Size
                </th>
                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th scope="col" class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              {#each filteredJobs as job}
                {@const statusBadge = getStatusBadge(job.status)}
                {@const canDownload = (job.processed_rows || 0) > 0}
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-3 whitespace-nowrap">
                    <div class="flex items-center">
                      <svg class="w-4 h-4 text-gray-400 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                      </svg>
                      <div>
                        <span class="text-sm font-medium text-gray-900">{getOutputFilename(job)}</span>
                        <p class="text-xs text-gray-500">From: {job.display_filename || 'Unknown'}</p>
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                    {(job.processed_rows || 0).toLocaleString()} / {(job.total_rows || 0).toLocaleString()}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {formatFileSize(calculateFileSize(job))}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(job.created_at)}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span class="inline-block px-2 py-0.5 text-[10px] font-semibold rounded {statusBadge.class}">
                      {statusBadge.text}
                    </span>
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-right text-sm font-medium">
                    <div class="flex items-center justify-end gap-2">
                      <button
                        on:click={() => handleDownload(job)}
                        disabled={!canDownload}
                        class="px-3 py-1.5 bg-blue-500 text-white text-xs font-medium rounded-lg hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 cursor-pointer"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                        </svg>
                        Download
                      </button>
                      <button
                        on:click={() => handleDelete(job)}
                        class="px-3 py-1.5 bg-red-500 text-white text-xs font-medium rounded-lg hover:bg-red-600 transition-colors flex items-center gap-1.5 cursor-pointer"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {/if}
</div>
