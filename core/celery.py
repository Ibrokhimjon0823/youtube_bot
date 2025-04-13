import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Create the Celery app
app = Celery('core')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure scheduled tasks
app.conf.beat_schedule = {
    'generate-daily-stats': {
        'task': 'bot_analytics.tasks.generate_daily_stats',
        # Run at midnight every day
        'schedule': crontab(minute=0, hour=0),
    },
    'clean-incomplete-activities': {
        'task': 'bot_analytics.tasks.clean_incomplete_activities',
        # Run every hour
        'schedule': crontab(minute=0, hour='*/1'),
    },
    'purge-old-raw-data': {
        'task': 'bot_analytics.tasks.purge_old_raw_data',
        # Run once a month (first day at 1:00 AM)
        'schedule': crontab(minute=0, hour=1, day_of_month=1),
        'kwargs': {'days': 90},  # Keep data for 90 days
    },
}