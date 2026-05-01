<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { jobsAPI, filesAPI } from '../../../lib/api';
  import { authStore } from '../../../lib/stores/auth';
  import { config } from '../../../lib/config/env';

  let targetDomain = 'company.info';
  let status = 'IDLE';
  let progress = 0;
  let pagesScanned = 0;
  let pagesPending = 0;
  let totalRows = 0;
  let completed = 0;
  let successRate = 0;
  let phoneNumbers = 0;
  let missingNumbers = 0;
  let emailStats = 0;
  let uploadedFile: File | null = null;
  let currentJobId: string | null = null;
  let error = '';
  let uploading = false;
  let estimatedTime = '';
  let showCompletionPopup = false;
  
  let ws: WebSocket | null = null;
  let pollInterval: any = null;

  // Computed states
  $: isRunning = status === 'RUNNING';
  $: canUpload = status === 'IDLE' || status === 'COMPLETED' || status === 'CANCELLED' || status === 'FAILED';
  $: canStart = (currentJobId && canUpload) || uploadedFile !== null;
  $: canCancel = status === 'RUNNING' || status === 'QUEUED';

  onMount(() => {
    connectWebSocket();
    loadActiveJob();
  });

  onDestroy(() => {
    if (ws) ws.close();
    if (pollInterval) clearInterval(pollInterval);
  });

  function connectWebSocket() {
    const token = $authStore.token;
    if (!token) return;

    // Use dynamic WebSocket URL from config
    const wsUrl = `${config.WS_BASE_URL}/api/v1/ws?token=${token}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      if (currentJobId) {
        ws?.send(JSON.stringify({ action: 'subscribe', job_uuid: currentJobId }));
      }
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'job_update' && message.job_uuid === currentJobId) {
        updateJobStats(message.data);
      }
    };

    ws.onerror = () => console.error('WebSocket error');
    ws.onclose = () => {
      console.log('WebSocket closed, reconnecting...');
      setTimeout(connectWebSocket, 3000);
    };
  }

  async function loadActiveJob() {
    try {
      // Only load if there's an active running or queued job
      let response = await jobsAPI.listJobs({ status_filter: 'running' });
      if (response.jobs && response.jobs.length > 0) {
        currentJobId = response.jobs[0].job_uuid;
        await updateJobStatus();
        startPolling();
        return;
      }
      
      response = await jobsAPI.listJobs({ status_filter: 'queued' });
      if (response.jobs && response.jobs.length > 0) {
        currentJobId = response.jobs[0].job_uuid;
        await updateJobStatus();
        startPolling();
        return;
      }
      
      // Otherwise start fresh
      status = 'IDLE';
    } catch (err) {
      console.error('Failed to load active job:', err);
    }
  }

  async function updateJobStatus() {
    if (!currentJobId) return;
    
    try {
      const job = await jobsAPI.getJob(currentJobId);
      updateJobStats(job);
    } catch (err) {
      console.error('Failed to update job status:', err);
    }
  }

  function updateJobStats(job: any) {
    const oldStatus = status;
    status = job.status?.toUpperCase() || 'IDLE';
    
    // Map job fields directly
    totalRows = job.total_rows || 0;
    completed = job.processed_rows || 0;
    const successful = job.successful_rows || 0;
    const failed = job.failed_rows || 0;
    
    progress = totalRows > 0 ? Math.round((completed / totalRows) * 100) : 0;
    pagesScanned = completed;
    pagesPending = totalRows - completed;
    
    // Calculate stats from job data or result
    const result = job.result || {};
    phoneNumbers = result.phone_numbers || result.total_phone_numbers || 0;
    missingNumbers = result.missing_numbers || failed || 0;
    emailStats = result.emails || result.total_emails || 0;
    successRate = totalRows > 0 ? Math.round((successful / totalRows) * 100 * 10) / 10 : 0;

    // Calculate estimated time
    if (pagesPending > 0 && completed > 0 && job.started_at) {
      const startTime = new Date(job.started_at).getTime();
      const now = Date.now();
      const elapsed = now - startTime;
      const avgTimePerRow = elapsed / completed;
      const remainingMs = avgTimePerRow * pagesPending;
      const minutes = Math.round(remainingMs / 60000);
      estimatedTime = minutes > 0 ? `${minutes}m` : '<1m';
    } else {
      estimatedTime = '';
    }

    // Show completion popup when job completes
    if (oldStatus === 'RUNNING' && (status === 'COMPLETED' || status === 'FAILED')) {
      showCompletionPopup = true;
      stopPolling();
    }
    
    // Stop polling if job is done
    if (status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED') {
      stopPolling();
    }
    
    console.log('Job stats updated:', { status, totalRows, completed, progress });
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(updateJobStatus, 2000);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      uploadedFile = input.files[0];
      error = '';
    }
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
      uploadedFile = event.dataTransfer.files[0];
      error = '';
    }
  }

  async function uploadFileAndCreateJob() {
    if (!uploadedFile) {
      error = 'Please select a CSV file';
      return null;
    }

    uploading = true;
    error = '';

    try {
      // Create job
      const job = await jobsAPI.createJob({
        tool_type: 'scraply',
        name: `Scraply - ${uploadedFile.name}`,
        description: 'CompanyInfo scraping job',
        priority: 'normal',
        config: {}
      });

      // Upload file with job UUID
      await filesAPI.uploadFile(uploadedFile, job.job_uuid);

      currentJobId = job.job_uuid;
      uploadedFile = null;
      const fileInput = document.getElementById('csv-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      
      return job.job_uuid;
    } catch (err: any) {
      error = err.response?.data?.detail || 'Upload failed';
      console.error('Upload error:', err);
      return null;
    } finally {
      uploading = false;
    }
  }

  async function handleStart() {
    error = '';
    
    // If we have an uploaded file but no job, create the job first
    if (!currentJobId && uploadedFile) {
      const jobId = await uploadFileAndCreateJob();
      if (!jobId) return;
    }

    if (!currentJobId) {
      error = 'Please upload a CSV file first';
      return;
    }

    try {
      await jobsAPI.startJob(currentJobId);
      status = 'RUNNING';
      startPolling();
      
      if (ws) {
        ws.send(JSON.stringify({ action: 'subscribe', job_uuid: currentJobId }));
      }
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to start job';
      console.error('Start error:', err);
    }
  }

  async function handleCancel() {
    if (!currentJobId) return;
    
    try {
      await jobsAPI.cancelJob(currentJobId);
      status = 'CANCELLED';
      stopPolling();
      
      // Reset to allow new job
      setTimeout(() => {
        currentJobId = null;
        status = 'IDLE';
        progress = 0;
        totalRows = 0;
        completed = 0;
      }, 1000);
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to cancel job';
      console.error('Cancel error:', err);
    }
  }

  function handleNewJob() {
    // Clear everything for a fresh start
    currentJobId = null;
    uploadedFile = null;
    status = 'IDLE';
    progress = 0;
    totalRows = 0;
    completed = 0;
    pagesScanned = 0;
    pagesPending = 0;
    phoneNumbers = 0;
    missingNumbers = 0;
    emailStats = 0;
    successRate = 0;
    showCompletionPopup = false;
    error = '';
    
    const fileInput = document.getElementById('csv-upload') as HTMLInputElement;
    if (fileInput) fileInput.value = '';
  }

  async function handleExport() {
    if (!currentJobId) {
      error = 'No job to export';
      return;
    }

    try {
      await jobsAPI.downloadJobResult(currentJobId);
      error = '';
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to export';
      console.error('Export error:', err);
    }
  }

  // Public API for Dashboard component
  export function getJobInfo() {
    return {
      hasJob: currentJobId !== null,
      canExport: status === 'COMPLETED',
      canCancel: status === 'RUNNING' || status === 'QUEUED',
      status
    };
  }
  
  export { handleExport, handleCancel };
</script>

<div class="p-8 bg-[#f5f5f5] min-h-screen">
  <!-- Completion Popup -->
  {#if showCompletionPopup}
    <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <div class="text-center">
          <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-gray-900 mb-2">Job Completed!</h3>
          <p class="text-gray-600 mb-6">Your scraping job has finished. Would you like to download the results?</p>
          <div class="flex gap-3">
            <button
              on:click={() => { showCompletionPopup = false; handleExport(); }}
              class="flex-1 px-4 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 cursor-pointer"
            >
              Download Results
            </button>
            <button
              on:click={() => { showCompletionPopup = false; handleNewJob(); }}
              class="flex-1 px-4 py-2 bg-gray-200 text-gray-700 font-medium rounded-lg hover:bg-gray-300 cursor-pointer"
            >
              Start New Job
            </button>
          </div>
          <button
            on:click={() => showCompletionPopup = false}
            class="mt-3 text-sm text-gray-500 hover:text-gray-700 cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Error Alert -->
  {#if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center justify-between">
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

  <!-- System Monitoring -->
  <div class="bg-white bg-opacity-80 rounded-lg p-6 mb-6 shadow-sm backdrop-blur-sm">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
          </svg>
        </div>
        <div>
          <h3 class="text-sm font-semibold text-gray-900">SYSTEM MONITORING</h3>
          <p class="text-xs text-gray-500">Target: {targetDomain}</p>
        </div>
      </div>
      <span class="px-3 py-1 text-xs font-medium rounded-full {status === 'RUNNING' ? 'bg-green-100 text-green-800' : status === 'CANCELLED' ? 'bg-yellow-100 text-yellow-800' : status === 'COMPLETED' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
        {status}
      </span>
    </div>

    <!-- Progress Bar -->
    <div class="mb-4">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-gray-700">Scraping Progress</span>
        <span class="text-2xl font-bold text-primary-600">{progress}%</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2.5">
        <div class="bg-primary-500 h-2.5 rounded-full transition-all duration-500" style="width: {progress}%"></div>
      </div>
      <div class="flex items-center justify-between mt-2 text-xs text-gray-600">
        <span>{pagesScanned.toLocaleString()} pages scanned</span>
        <span>{pagesPending.toLocaleString()} pending</span>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-3 gap-4 mb-6">
      <div class="bg-gray-50 rounded-lg p-4 text-center">
        <p class="text-xs text-gray-600 mb-1">Total Rows</p>
        <p class="text-2xl font-bold text-gray-900">{totalRows.toLocaleString()}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4 text-center">
        <p class="text-xs text-gray-600 mb-1">Completed</p>
        <p class="text-2xl font-bold text-gray-900">{completed.toLocaleString()}</p>
      </div>
      <div class="bg-gray-50 rounded-lg p-4 text-center">
        <p class="text-xs text-gray-600 mb-1">Success Rate</p>
        <p class="text-2xl font-bold text-gray-900">{successRate.toFixed(1)}%</p>
      </div>
    </div>

    <!-- Additional Stats -->
    <div class="grid grid-cols-3 gap-4">
      <div class="bg-blue-50 rounded-lg p-4 text-center">
        <p class="text-xs text-blue-600 font-medium mb-1">NUMBERS</p>
        <p class="text-2xl font-bold text-blue-600">{phoneNumbers.toLocaleString()}</p>
      </div>
      <div class="bg-orange-50 rounded-lg p-4 text-center">
        <p class="text-xs text-orange-600 font-medium mb-1">MISSING NUMBERS</p>
        <p class="text-2xl font-bold text-orange-600">{missingNumbers.toLocaleString()}</p>
      </div>
      <div class="bg-teal-50 rounded-lg p-4 text-center">
        <p class="text-xs text-teal-600 font-medium mb-1">EMAIL STATS</p>
        <p class="text-2xl font-bold text-teal-600">{emailStats.toLocaleString()}</p>
      </div>
    </div>
  </div>

  <!-- Upload Section and Controls -->
  <div class="grid grid-cols-2 gap-6">
    <!-- Upload CSV -->
    <div class="bg-white bg-opacity-80 rounded-lg p-8 shadow-sm backdrop-blur-sm {!canUpload ? 'opacity-50 pointer-events-none' : ''}">
      <div
        class="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-primary-400 transition-colors bg-white bg-opacity-50"
        on:dragover={handleDragOver}
        on:drop={handleDrop}
      >
        <div class="flex flex-col items-center">
          <div class="w-12 h-12 bg-gray-100 bg-opacity-80 rounded-lg flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Upload CSV</h3>
          <p class="text-sm text-gray-600 mb-4">Drag and drop your files here or click to browse.</p>
          
          {#if uploadedFile}
            <div class="mb-4 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg text-sm font-medium">
              {uploadedFile.name}
            </div>
          {/if}
          
          <label for="csv-upload" class="cursor-pointer px-6 py-3 bg-white border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors">
            Select File
          </label>
          <input
            id="csv-upload"
            type="file"
            accept=".csv"
            class="hidden"
            on:change={handleFileUpload}
            disabled={!canUpload}
          />
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="bg-white bg-opacity-80 rounded-lg p-8 shadow-sm backdrop-blur-sm">
      <h3 class="text-lg font-semibold text-gray-900 mb-6">Control Panel</h3>
      
      <!-- Control Button -->
      <button
        on:click={handleStart}
        disabled={!canStart || isRunning}
        class="w-full flex items-center justify-center gap-3 px-6 py-4 bg-primary-500 text-white text-base font-semibold rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg cursor-pointer"
      >
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M8 5v14l11-7z"></path>
        </svg>
        <span>Start Scraping</span>
      </button>
    </div>
  </div>
</div>
