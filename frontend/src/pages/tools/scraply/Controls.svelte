<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { jobsAPI, filesAPI } from '../../../lib/api';
  import { authStore } from '../../../lib/stores/auth';
  import { websocketService } from '../../../lib/services/websocket';
  import { notificationStore } from '../../../lib/stores/notifications';
  import { config } from '../../../lib/config/env';
  import CsvColumnMapperModal from '../../../components/common/CsvColumnMapperModal.svelte';

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
  let showCompletionPopup = false;
  let uploadedFiles: Array<{filename: string, uploaded_at: string}> = [];
  
  // CSV Column Mapping
  let showColumnMapper = false;
  let detectedMapping: { [key: string]: string } = {};
  let detectedSheet: string | null = null;
  let detectedHeaderRow = 1;
  let csvHeaders: string[] = [];
  let columnMappings: any = null;
  let tempUploadedFilename: string = '';
  let tempJobId: string = '';
  
  let ws: WebSocket | null = null;
  let pollInterval: any = null;
  
  // Audio notification for job completion
  let audioContext: AudioContext | null = null;
  let audioUnlocked = false;

  // Computed states
  $: isRunning = status === 'RUNNING';
  $: isPaused = status === 'PAUSED';
  $: canUpload = status === 'IDLE' || status === 'COMPLETED' || status === 'CANCELLED' || status === 'FAILED';
  $: canStart = (currentJobId && !isRunning && !uploading) || uploadedFile !== null;
  $: canPause = status === 'RUNNING';
  $: canResume = status === 'PAUSED';
  $: canRetry = status === 'FAILED' || status === 'CANCELLED';
  $: canCancel = status === 'RUNNING' || status === 'QUEUED';
  $: canExport = (status === 'RUNNING' || status === 'COMPLETED' || status === 'CANCELLED' || status === 'FAILED') && completed > 0;
  $: hasJobToShow = currentJobId !== null;

  onMount(() => {
    connectWebSocket();
    loadActiveJob();
    
    // Request notification permission on mount
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    
    // Initialize AudioContext (will be unlocked on first user interaction)
    try {
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    } catch (e) {
      console.warn('AudioContext not supported');
    }
    
    // Unlock audio on any user click (browser requirement)
    const unlockAudio = () => {
      if (audioContext && audioContext.state === 'suspended') {
        audioContext.resume().then(() => {
          audioUnlocked = true;
          console.log('🔊 Audio unlocked');
        });
      } else {
        audioUnlocked = true;
      }
      // Remove listener after first unlock
      document.removeEventListener('click', unlockAudio);
    };
    document.addEventListener('click', unlockAudio);
    
    // Listen to job updates from WebSocket service
    window.addEventListener('job-status-change', handleJobStatusChange);
    window.addEventListener('job-progress', handleJobProgress);
  });

  onDestroy(() => {
    if (ws) ws.close();
    if (pollInterval) clearInterval(pollInterval);
    if (currentJobId) {
      websocketService.unsubscribeFromJob(currentJobId);
    }
    window.removeEventListener('job-status-change', handleJobStatusChange);
    window.removeEventListener('job-progress', handleJobProgress);
  });

  function handleJobStatusChange(event: any) {
    const { jobUuid, status: newStatus, data } = event.detail;
    if (jobUuid === currentJobId) {
      status = newStatus.toUpperCase();
      if (data.progress !== undefined) progress = data.progress;
      
      // Show completion popup if job completed
      if (newStatus === 'completed' && !showCompletionPopup) {
        showCompletionPopup = true;
      }
    }
  }

  function handleJobProgress(event: any) {
    const { jobUuid, progress: newProgress } = event.detail;
    if (jobUuid === currentJobId) {
      progress = newProgress;
    }
  }

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
      console.log('Checking for active jobs on mount...');
      
      // Priority 1: Active running jobs - MUST show these first
      let response = await jobsAPI.listJobs({ status_filter: 'running' });
      if (response.jobs && response.jobs.length > 0) {
        console.log('Found running job:', response.jobs[0].job_uuid);
        currentJobId = response.jobs[0].job_uuid;
        await updateJobStatus();
        startPolling();
        return;
      }
      
      // Priority 2: Queued jobs - waiting to run
      response = await jobsAPI.listJobs({ status_filter: 'queued' });
      if (response.jobs && response.jobs.length > 0) {
        console.log('Found queued job:', response.jobs[0].job_uuid);
        currentJobId = response.jobs[0].job_uuid;
        await updateJobStatus();
        startPolling();
        return;
      }
      
      // Priority 3: Paused jobs - need attention
      response = await jobsAPI.listJobs({ status_filter: 'paused' });
      if (response.jobs && response.jobs.length > 0) {
        console.log('Found paused job:', response.jobs[0].job_uuid);
        currentJobId = response.jobs[0].job_uuid;
        await updateJobStatus();
        return;
      }
      
      // No active jobs - Get the MOST RECENT job of any status to display
      // This allows user to see their last job and export it
      const allStatuses = ['completed', 'cancelled', 'failed'];
      let mostRecentJob: any = null;
      let mostRecentDate = new Date(0);
      
      for (const statusFilter of allStatuses) {
        response = await jobsAPI.listJobs({ status_filter: statusFilter });
        if (response.jobs && response.jobs.length > 0) {
          const job = response.jobs[0];
          const jobDate = new Date(job.updated_at || job.created_at);
          if (jobDate > mostRecentDate) {
            mostRecentDate = jobDate;
            mostRecentJob = job;
          }
        }
      }
      
      if (mostRecentJob) {
        console.log('Found most recent job:', mostRecentJob.job_uuid, 'status:', mostRecentJob.status);
        currentJobId = mostRecentJob.job_uuid;
        status = mostRecentJob.status?.toUpperCase() || 'IDLE';
        await updateJobStatus();
        return;
      }
      
      // No jobs at all - start fresh
      console.log('No jobs found - ready for fresh upload');
      currentJobId = null;
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
    const newStatus = job.status?.toUpperCase() || 'IDLE';
    
    // If job was cancelled, keep it cancelled (don't let it go back to running)
    if (oldStatus === 'CANCELLED' && newStatus === 'RUNNING') {
      console.log('Ignoring status change from CANCELLED to RUNNING - keeping CANCELLED');
      return;
    }
    
    status = newStatus;
    console.log(`Status updated: ${oldStatus} → ${status}`);
    
    // Map job fields directly
    totalRows = job.total_rows || 0;
    completed = job.processed_rows || 0;
    const successful = job.successful_rows || 0;
    const failed = job.failed_rows || 0;
    
    progress = totalRows > 0 ? Math.round((completed / totalRows) * 100) : 0;
    pagesScanned = completed;
    pagesPending = totalRows - completed;
    
    // The backend tracks successful_rows (rows with phone OR email) and failed_rows (rows with neither)
    // We display these as:
    // - phoneNumbers = successful rows (rows that have contact info)
    // - missingNumbers = failed rows (rows missing contact info)
    // - emailStats = successful rows (since we find email along with phone)
    phoneNumbers = successful;
    missingNumbers = failed;
    emailStats = successful; // Same as phone numbers since backend finds both together
    successRate = totalRows > 0 ? Math.round((successful / totalRows) * 100 * 10) / 10 : 0;

    // ✅ SIMPLE: RUNNING → COMPLETED = notification
    if (oldStatus === 'RUNNING' && status === 'COMPLETED') {
      console.log('🎉 JOB COMPLETED! RUNNING → COMPLETED');
      showCompletionPopup = true;
      stopPolling();
      
      notificationStore.add({
        type: 'success',
        title: '🎉 Job Completed!',
        message: `Processed ${completed} of ${totalRows} rows. Success: ${successRate}%`,
        jobUuid: currentJobId || undefined
      });
      
      playCompletionSound();
      showBrowserNotification();
    }
    
    // Show error message when job fails
    if (oldStatus === 'RUNNING' && status === 'FAILED') {
      error = job.error_message || 'Job failed. Please check the logs.';
      stopPolling();
    }
    
    // Stop polling if job is done
    if (status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED') {
      stopPolling();
    }
    
    console.log('Job stats updated:', { oldStatus, status, totalRows, completed, progress });
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(updateJobStatus, 2000); // Poll every 2 seconds
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function playCompletionSound() {
    console.log('🔊 Attempting to play completion sound...');
    
    try {
      // Create new context if needed or resume existing
      if (!audioContext) {
        audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      
      // Resume if suspended (browser policy)
      if (audioContext.state === 'suspended') {
        audioContext.resume();
      }
      
      const ctx = audioContext;
      const now = ctx.currentTime;
      
      // Play 3 loud beeps for attention
      for (let i = 0; i < 3; i++) {
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        
        // Alternating frequencies for attention-grabbing sound
        oscillator.frequency.value = i % 2 === 0 ? 880 : 1047; // A5 and C6
        oscillator.type = 'square'; // Harsher, louder sound
        gainNode.gain.value = 1.0; // Maximum volume
        
        const beepStart = now + (i * 0.25);
        oscillator.start(beepStart);
        oscillator.stop(beepStart + 0.15);
      }
      
      console.log('✅ Completion sound played (3 beeps)');
    } catch (err) {
      console.error('❌ Failed to play completion sound:', err);
      
      // Fallback: try HTML5 Audio with a generated beep
      try {
        const audio = new Audio('data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU' + btoa(String.fromCharCode.apply(null, Array(8000).fill(0).map((_, i) => 128 + 127 * Math.sin(i * 0.1)))));
        audio.volume = 1.0;
        audio.play();
      } catch (e) {
        console.error('Fallback audio also failed:', e);
      }
    }
  }

  function showBrowserNotification() {
    try {
      if ('Notification' in window && Notification.permission === 'granted') {
        const notification = new Notification('🎉 Scraping Job Completed!', {
          body: `Successfully processed ${completed} of ${totalRows} rows.\nSuccess Rate: ${successRate}%`,
          icon: '/images/Favicon-BE-HkS4F.png',
          badge: '/images/Favicon-BE-HkS4F.png',
          tag: 'job-completion',
          requireInteraction: true, // Stays until user dismisses
          vibrate: [200, 100, 200], // Vibration pattern on mobile
        });
        
        notification.onclick = () => {
          window.focus();
          notification.close();
        };
        
        console.log('✅ Browser notification shown');
      } else if (Notification.permission === 'default') {
        // Request permission if not yet granted
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') {
            showBrowserNotification();
          }
        });
      }
    } catch (err) {
      console.error('Failed to show browser notification:', err);
    }
  }

  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      uploadedFile = input.files[0];
    }
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
      uploadedFile = event.dataTransfer.files[0];
    }
  }

  async function uploadFileAndCreateJob() {
    if (!uploadedFile) {
      error = 'Please select a CSV or Excel file';
      return null;
    }

    uploading = true;
    error = '';

    try {
      console.log('Creating new job for file:', uploadedFile.name);
      
      // Create job with empty config (will be updated after column mapping)
      const job = await jobsAPI.createJob({
        tool_type: 'scraply',
        name: `Scraply - ${uploadedFile.name}`,
        description: 'CompanyInfo scraping job',
        priority: 'normal',
        config: {}
      });

      console.log('Job created:', job.job_uuid);
      
      // Upload file with job UUID
      console.log('Uploading file for job:', job.job_uuid);
      const uploadResult = await filesAPI.uploadFile(uploadedFile, job.job_uuid);
      console.log('File uploaded successfully:', uploadResult);

      // Get CSV headers from uploaded file
      console.log('Getting CSV headers from:', uploadResult.filename);
      const info = await filesAPI.getCsvHeaders(uploadResult.filename);
      console.log('Header info:', info);

      // The backend suggests a mapping; the modal shows it pre-filled and the
      // user confirms or changes it before anything starts.
      const d = info.detected || {};
      detectedMapping = {
        col_company: d.company || '',
        col_street: d.street || '',
        col_house_number: d.house_number || '',
        col_city: d.city || ''
      };
      detectedSheet = info.sheet;
      detectedHeaderRow = info.header_row || 1;

      // Store temporary data for column mapping
      tempUploadedFilename = uploadResult.filename;
      tempJobId = job.job_uuid;
      csvHeaders = info.headers;
      
      // Show column mapper modal
      showColumnMapper = true;
      
      // Clear uploaded file state
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

  async function handleColumnMappingComplete(event: CustomEvent) {
    console.log('Column mapping complete:', event.detail);
    columnMappings = event.detail;
    
    // Update job config with column mappings
    if (tempJobId) {
      try {
        // Update the job with column mappings
        await jobsAPI.updateJob(tempJobId, {
          config: {
            ...columnMappings,
            sheet: detectedSheet,
            header_row: detectedHeaderRow
          }
        });
        
        currentJobId = tempJobId;
        const jobIdToStart = tempJobId;
        tempJobId = '';
        tempUploadedFilename = '';
        
        console.log('Job updated with column mappings');
        
        // Show success notification
        notificationStore.add({
          type: 'success',
          title: 'Column Mapping Complete',
          message: 'Starting job automatically...'
        });

        // Auto-start the job after mapping is complete
        console.log('Auto-starting job:', jobIdToStart);
        const startedJob = await jobsAPI.startJob(jobIdToStart);
        console.log('Job started successfully:', startedJob);
        status = 'RUNNING';
        startPolling();
        
        // Subscribe to WebSocket updates for this job
        websocketService.subscribeToJob(jobIdToStart);
        
        if (ws) {
          ws.send(JSON.stringify({ action: 'subscribe', job_uuid: jobIdToStart }));
        }
        
        // Show job started notification
        notificationStore.add({
          type: 'info',
          title: 'Job Started',
          message: `Job ${jobIdToStart.slice(0, 8)} is now running`,
          jobUuid: jobIdToStart
        });
      } catch (err: any) {
        error = err.response?.data?.detail || 'Failed to start job';
        console.error('Failed to start job:', err);
        
        notificationStore.add({
          type: 'error',
          title: 'Error',
          message: error
        });
      }
    }
  }

  function handleColumnMappingCancel() {
    console.log('Column mapping cancelled');
    // Clean up temporary data
    tempJobId = '';
    tempUploadedFilename = '';
    csvHeaders = [];
    columnMappings = null;
  }

  async function handleStart() {
    error = '';
    
    console.log('Start clicked - currentJobId:', currentJobId, 'uploadedFile:', uploadedFile?.name);
    
    // If we have an uploaded file, trigger the upload and mapping flow
    if (uploadedFile) {
      console.log('Triggering file upload and column mapping...');
      await uploadFileAndCreateJob();
      // uploadFileAndCreateJob will show the modal
      // The job will not start until user completes mapping and clicks Start again
      return;
    }

    // At this point, we need a currentJobId to start
    if (!currentJobId) {
      error = 'Please upload a CSV file first';
      return;
    }

    try {
      console.log('Starting job:', currentJobId);
      const startedJob = await jobsAPI.startJob(currentJobId);
      console.log('Job started successfully:', startedJob);
      status = 'RUNNING';
      startPolling();
      
      // Subscribe to WebSocket updates for this job
      websocketService.subscribeToJob(currentJobId);
      
      if (ws) {
        ws.send(JSON.stringify({ action: 'subscribe', job_uuid: currentJobId }));
      }
      
      // Show notification
      notificationStore.add({
        type: 'info',
        title: 'Job Started',
        message: `Job ${currentJobId.slice(0, 8)} has started`,
        jobUuid: currentJobId
      });
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to start job';
      console.error('Start error:', err);
      
      notificationStore.add({
        type: 'error',
        title: 'Failed to Start Job',
        message: error,
        jobUuid: currentJobId
      });
    }
  }

  async function handleCancel() {
    if (!currentJobId) return;
    
    try {
      // Stop polling immediately
      stopPolling();
      
      // Close WebSocket
      if (ws) {
        ws.close();
        ws = null;
      }
      
      // Cancel the job
      await jobsAPI.cancelJob(currentJobId);
      status = 'CANCELLED';
      
      // Force immediate reset for new job
      setTimeout(() => {
        currentJobId = null;
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
        error = '';
        
        // Reconnect WebSocket for future jobs
        connectWebSocket();
      }, 500);
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to cancel job';
      console.error('Cancel error:', err);
      status = 'IDLE';
      currentJobId = null;
    }
  }

  async function handlePause() {
    if (!currentJobId) return;
    
    try {
      error = '';
      await jobsAPI.pauseJob(currentJobId);
      status = 'PAUSED';
      await updateJobStatus();
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to pause job';
      console.error('Pause error:', err);
    }
  }

  async function handleResume() {
    if (!currentJobId) return;
    
    try {
      error = '';
      await jobsAPI.resumeJob(currentJobId);
      status = 'RUNNING';
      await updateJobStatus();
      startPolling();
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to resume job';
      console.error('Resume error:', err);
    }
  }

  async function handleRetry() {
    if (!currentJobId) return;
    
    try {
      error = '';
      const job = await jobsAPI.retryJob(currentJobId);
      currentJobId = job.job_uuid;
      status = 'QUEUED';
      await updateJobStatus();
      startPolling();
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to retry job';
      console.error('Retry error:', err);
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

    if (completed === 0) {
      error = 'No data to export yet. Please wait for processing to start.';
      return;
    }

    try {
      const blob = await jobsAPI.downloadJobResult(currentJobId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
      const statusLabel = status === 'COMPLETED' ? 'complete' : 'partial';
      // Results always come back as Excel, whatever was uploaded.
      const outExt = '.xlsx';
      link.setAttribute('download', `scraply_${statusLabel}_${completed}rows_${timestamp}${outExt}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      // Show success message
      error = '';
      console.log(`Exported ${completed} rows successfully`);
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to export. Output file may not exist yet.';
      console.error('Export error:', err);
    }
  }

  // Public API for Dashboard component
  export function getJobInfo() {
    return {
      hasJob: currentJobId !== null,
      canExport: canExport,
      canCancel: canCancel,
      status
    };
  }
  
  export { handleExport, handleCancel };
</script>

<div class="p-4 sm:p-8 bg-[#f5f5f5] min-h-screen">
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
  <div class="bg-white bg-opacity-80 rounded-lg p-4 sm:p-6 mb-4 sm:mb-6 shadow-sm backdrop-blur-sm">
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
      <span class="px-3 py-1 text-xs font-medium rounded-full {status === 'RUNNING' ? 'bg-green-100 text-green-800' : status === 'PAUSED' || status === 'CANCELLED' ? 'bg-yellow-100 text-yellow-800' : status === 'COMPLETED' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
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
        <span>{pagesScanned.toLocaleString()} row scanned</span>
        <span>{pagesPending.toLocaleString()} row pending</span>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-6">
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

    <!-- Stats Details -->
    <div class="grid grid-cols-3 gap-2 sm:gap-4">
      <div class="bg-blue-50 rounded-lg p-4 text-center">
        <p class="text-xs text-blue-600 font-medium mb-1">Numbers Found</p>
        <p class="text-2xl font-bold text-blue-600">{phoneNumbers.toLocaleString()}</p>
      </div>
      <div class="bg-orange-50 rounded-lg p-4 text-center">
        <p class="text-xs text-orange-600 font-medium mb-1">MISSING NUMBERS</p>
        <p class="text-2xl font-bold text-orange-600">{missingNumbers}</p>
      </div>
      <div class="bg-teal-50 rounded-lg p-4 text-center">
        <p class="text-xs text-teal-600 font-medium mb-1">EMAIL STATS</p>
        <p class="text-2xl font-bold text-teal-600">{emailStats.toLocaleString()}</p>
      </div>
    </div>
  </div>

  <!-- Upload Section and Controls -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
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
              ✓ {uploadedFile.name}
            </div>
          {/if}

          <input
            id="csv-upload"
            type="file"
            accept=".csv,.xlsx,.xls"
            class="hidden"
            on:change={handleFileUpload}
            disabled={!canUpload}
          />
          <label
            for="csv-upload"
            class="px-4 py-2 bg-white bg-opacity-80 border border-gray-300 text-sm font-medium text-gray-700 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
          >
            .csv / .xlsx
          </label>
        </div>
      </div>
    </div>

    <!-- Control Buttons -->
    <div class="bg-white bg-opacity-80 rounded-lg p-8 shadow-sm flex flex-col justify-center backdrop-blur-sm">
      <div class="space-y-3">
        <!-- Start Button -->
        <button
          on:click={handleStart}
          disabled={!canStart || isRunning || uploading}
          class="w-full flex items-center justify-center gap-2 px-6 py-3 text-sm font-medium rounded-lg transition-all cursor-pointer {!canStart || isRunning || uploading ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-blue-500 text-white hover:bg-blue-600 shadow-sm'}"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z"></path>
          </svg>
          <span>Start</span>
        </button>

        <!-- Pause/Resume Button -->
        {#if isPaused}
          <button
            on:click={handleResume}
            class="w-full flex items-center justify-center gap-2 px-6 py-3 bg-white text-gray-700 border border-gray-300 text-sm font-medium rounded-lg hover:bg-gray-50 transition-all shadow-sm cursor-pointer"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"></path>
            </svg>
            <span>Resume</span>
          </button>
        {:else}
          <button
            on:click={handlePause}
            disabled={!canPause}
            class="w-full flex items-center justify-center gap-2 px-6 py-3 text-sm font-medium rounded-lg transition-all cursor-pointer {!canPause ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 shadow-sm'}"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"></path>
            </svg>
            <span>Pause</span>
          </button>
        {/if}

        <!-- Retry Button -->
        <button
          on:click={handleRetry}
          disabled={!canRetry}
          class="w-full flex items-center justify-center gap-2 px-6 py-3 text-sm font-medium rounded-lg transition-all cursor-pointer {!canRetry ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 shadow-sm'}"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
          <span>Retry</span>
        </button>
        
        <!-- Test Sound Button -->
        <button
          on:click={playCompletionSound}
          class="w-full flex items-center justify-center gap-2 px-6 py-3 text-sm font-medium rounded-lg transition-all cursor-pointer bg-yellow-100 text-yellow-800 border border-yellow-300 hover:bg-yellow-200"
          title="Test if notification sound is working"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"></path>
          </svg>
          <span>Test Sound</span>
        </button>
      </div>
    </div>
  </div>
</div>

<!-- CSV Column Mapper Modal -->
<CsvColumnMapperModal
  bind:show={showColumnMapper}
  columns={csvHeaders}
  detected={detectedMapping}
  sheet={detectedSheet}
  headerRow={detectedHeaderRow}
  on:complete={handleColumnMappingComplete}
  on:cancel={handleColumnMappingCancel}
/>
