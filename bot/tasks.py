# bot_analytics/tasks.py
# Contains background tasks for data aggregation and maintenance

from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q
from datetime import timedelta
from .models import TelegramUser, DownloadActivity, DailyStats

def generate_daily_stats(date=None):
    """
    Generate or update statistics for a specific day.
    If no date is provided, generate stats for yesterday.
    """
    if date is None:
        date = timezone.now().date() - timedelta(days=1)
    
    # Time range for the specific day
    start_datetime = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
    end_datetime = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.max.time()))
    
    # Count new users for that day
    new_users = TelegramUser.objects.filter(
        join_date__gte=start_datetime,
        join_date__lte=end_datetime
    ).count()
    
    # Count active users for that day
    active_users = TelegramUser.objects.filter(
        last_active__gte=start_datetime,
        last_active__lte=end_datetime
    ).count()
    
    # Get download stats
    downloads = DownloadActivity.objects.filter(
        started_at__gte=start_datetime,
        started_at__lte=end_datetime
    )
    
    total_downloads = downloads.count()
    video_downloads = downloads.filter(download_type=DownloadActivity.VIDEO).count()
    audio_downloads = downloads.filter(download_type=DownloadActivity.AUDIO).count()
    successful_downloads = downloads.filter(success=True).count()
    failed_downloads = downloads.filter(success=False).count()
    
    # Calculate average processing time and total download size
    completed_downloads = downloads.filter(
        success__isnull=False,
        processing_time__isnull=False
    )
    
    avg_processing_time = completed_downloads.aggregate(
        avg_time=Avg('processing_time')
    )['avg_time'] or 0
    
    total_download_size = downloads.filter(
        success=True,
        file_size__isnull=False
    ).aggregate(
        total_size=Sum('file_size')
    )['total_size'] or 0
    
    # Create or update the daily stats record
    stats, created = DailyStats.objects.update_or_create(
        date=date,
        defaults={
            'new_users': new_users,
            'active_users': active_users,
            'total_downloads': total_downloads,
            'video_downloads': video_downloads,
            'audio_downloads': audio_downloads,
            'successful_downloads': successful_downloads,
            'failed_downloads': failed_downloads,
            'total_download_size': total_download_size,
            'avg_processing_time': avg_processing_time
        }
    )
    
    return stats

def clean_incomplete_activities():
    """
    Clean up download activities that have been in 'in progress' state for too long.
    Mark them as failed after a certain period.
    """
    # Find activities started more than 1 hour ago that haven't completed
    cutoff_time = timezone.now() - timedelta(hours=1)
    
    stalled_activities = DownloadActivity.objects.filter(
        started_at__lt=cutoff_time,
        success__isnull=True
    )
    
    # Mark them as failed
    for activity in stalled_activities:
        activity.mark_complete(
            success=False,
            error_message="Timed out - download took too long to complete"
        )
    
    return len(stalled_activities)

def purge_old_raw_data(days=90):
    """
    Optional: Purge old raw download activity data after a certain period.
    Only delete raw data if you've already aggregated what you need in DailyStats.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Only delete activities that are successfully completed or failed
    old_activities = DownloadActivity.objects.filter(
        started_at__lt=cutoff_date,
        success__isnull=False  # Only purge completed records
    )
    
    count = old_activities.count()
    old_activities.delete()
    
    return count