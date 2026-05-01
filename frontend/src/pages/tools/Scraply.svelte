<script lang="ts">
  import { onMount } from 'svelte';
  import AppLayout from '../../components/layout/AppLayout.svelte';
  import Button from '../../components/common/Button.svelte';
  import Alert from '../../components/common/Alert.svelte';
  import { apiClient } from '../../lib/api/client';
  import type { Job } from '../../lib/types';

  let jobs: Job[] = [];
  let loading = false;
  let error = '';
  let success = '';
  let uploadFile: File | null = null;
  let uploadLoading = false;

  onMount(() => {
    loadJobs();
  });

  async function loadJobs() {
    loading = true;
    error = '';
    try {
      const response = await apiClient.get('/scraply/jobs');
      jobs = response.data;
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to load jobs';
    } finally {
      loading = false;
    }
  }

  function handleFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      uploadFile = input.files[0];
    }
  }

  async function handleUpload() {
    if (!uploadFile) {
      error = 'Please select a CSV file';
      return;
    }

    uploadLoading = true;
    error = '';
    success = '';

    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      const response = await apiClient.post('/scraply/jobs', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      success = 'Job created successfully!';
      uploadFile = null;
      (document.getElementById('fileInput') as HTMLInputElement).value = '';
      await loadJobs();
    } catch (err: any) {
      error = err.response?.data?.detail || 'Failed to create job';
    } finally {
      uploadLoading = false;
    }
  }

  async function downloadResults(jobId: string, filename: string) {
    try {
      const response = await apiClient.get(`/scraply/jobs/${jobId}/download`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename || `job_${jobId}_results.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      error = 'Failed to download results';
    }
  }

  function getStatusColor(status: string): string {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }

  function formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleString();
  }
</script>

<AppLayout>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center mb-4">
        <div class="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mr-4">
          <svg class="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
          </svg>
        </div>
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Scraply Dashboard</h1>
          <p class="text-gray-600">Advanced web scraping with CSV import/export</p>
        </div>
      </div>
    </div>

    <!-- Upload Section -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Create New Job</h2>
      
      {#if error}
        <div class="mb-4">
          <Alert message={error} type="error" />
        </div>
      {/if}

      {#if success}
        <div class="mb-4">
          <Alert message={success} type="success" />
        </div>
      {/if}

      <div class="space-y-4">
        <div>
          <label for="fileInput" class="block text-sm font-medium text-gray-700 mb-2">
            Upload CSV File
          </label>
          <input
            id="fileInput"
            type="file"
            accept=".csv"
            on:change={handleFileChange}
            disabled={uploadLoading}
            class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 disabled:opacity-50"
          />
          <p class="text-xs text-gray-500 mt-1">CSV file with phone numbers to scrape</p>
        </div>

        <div class="flex items-center space-x-3">
          <Button on:click={handleUpload} loading={uploadLoading} disabled={!uploadFile || uploadLoading}>
            {uploadLoading ? 'Uploading...' : 'Create Job'}
          </Button>
          {#if uploadFile}
            <span class="text-sm text-gray-600">Selected: {uploadFile.name}</span>
          {/if}
        </div>
      </div>
    </div>

    <!-- Jobs List -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200">
      <div class="px-6 py-4 border-b border-gray-200">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold text-gray-900">Recent Jobs</h2>
          <Button variant="secondary" size="sm" on:click={loadJobs} disabled={loading}>
            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            Refresh
          </Button>
        </div>
      </div>

      {#if loading}
        <div class="px-6 py-12 text-center">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p class="text-gray-500 mt-2">Loading jobs...</p>
        </div>
      {:else if jobs.length === 0}
        <div class="px-6 py-12 text-center">
          <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          <p class="text-gray-500 mt-2">No jobs yet. Upload a CSV file to create your first job.</p>
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Job ID</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Progress</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              {#each jobs as job}
                <tr class="hover:bg-gray-50">
                  <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    #{job.id}
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {getStatusColor(job.status)}">
                      {job.status}
                    </span>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {#if job.total_items}
                      {job.processed_items || 0} / {job.total_items}
                    {:else}
                      -
                    {/if}
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(job.created_at)}
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm">
                    {#if job.status === 'completed'}
                      <button
                        on:click={() => downloadResults(job.id, job.result_file || '')}
                        class="text-primary-600 hover:text-primary-900 font-medium cursor-pointer"
                      >
                        Download
                      </button>
                    {:else if job.status === 'running'}
                      <span class="text-gray-400">In progress...</span>
                    {:else if job.status === 'failed'}
                      <span class="text-red-600">Failed</span>
                    {:else}
                      <span class="text-gray-400">Pending</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    <!-- Info Card -->
    <div class="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
      <div class="flex items-start">
        <svg class="w-6 h-6 text-blue-600 mr-3 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <div>
          <h3 class="text-sm font-medium text-blue-900 mb-1">How it works</h3>
          <ul class="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>Upload a CSV file with phone numbers</li>
            <li>The job will be processed in the background</li>
            <li>Download results when the job is completed</li>
            <li>Results include scraped data in CSV format</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</AppLayout>
