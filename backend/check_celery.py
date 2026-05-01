from app.core.celery_app import celery_app

print('\n╔════════════════════════════════════╗')
print('║    CELERY TASKS REGISTERED         ║')
print('╚════════════════════════════════════╝\n')

for task in sorted(celery_app.tasks.keys()):
    if not task.startswith('celery.'):
        print(f'  ✓ {task}')

print('\n')
