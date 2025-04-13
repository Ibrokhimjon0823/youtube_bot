from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg

from bot.models import User, Download


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'telegram_id', 
        'username', 
        'first_name', 
        'last_name', 
        'language_code', 
        'downloads_count',
        'created_at', 
        'last_active',
        'active_days'
    )
    list_filter = ('created_at', 'last_active', 'language_code')
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'last_active', 'downloads_info')
    
    def downloads_count(self, obj):
        return obj.downloads.count()
    downloads_count.short_description = 'Downloads'
    
    def active_days(self, obj):
        if not obj.created_at:
            return 0
        return (obj.last_active.date() - obj.created_at.date()).days + 1
    active_days.short_description = 'Days Active'
    
    def downloads_info(self, obj):
        total = obj.downloads.count()
        if total == 0:
            return "No downloads yet"
            
        successful = obj.downloads.filter(success=True).count()
        videos = obj.downloads.filter(download_type='VIDEO', success=True).count()
        audios = obj.downloads.filter(download_type='AUDIO', success=True).count()
        success_rate = (successful / total) * 100 if total > 0 else 0
        
        return format_html(
            '<div style="line-height: 1.5;">'
            '<b>Total Downloads:</b> {}<br>'
            '<b>Successful:</b> {} ({:.1f}%)<br>'
            '<b>Videos:</b> {}<br>'
            '<b>Audio:</b> {}'
            '</div>',
            total, successful, success_rate, videos, audios
        )
    downloads_info.short_description = 'Download Statistics'
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            downloads_count=Count('downloads')
        )


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user_info',
        'video_title',
        'download_type',
        'download_status',
        'file_size_mb',
        'started_at', 
        'duration'
    )
    list_filter = ('success', 'download_type', 'started_at')
    search_fields = ('video_title', 'youtube_url', 'user__username', 'user__first_name')
    raw_id_fields = ('user',)
    readonly_fields = ('started_at', 'completed_at', 'youtube_url_link')
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Download Details', {
            'fields': ('youtube_url_link', 'video_title', 'download_type')
        }),
        ('Status', {
            'fields': ('success', 'file_size', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at')
        }),
    )
    
    def youtube_url_link(self, obj):
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.youtube_url)
    youtube_url_link.short_description = 'YouTube URL'
    
    def user_info(self, obj):
        return f"{obj.user.first_name} (@{obj.user.username or 'no_username'})"
    user_info.short_description = 'User'
    
    def download_status(self, obj):
        if obj.success:
            return format_html(
                '<span style="color: green; font-weight: bold">✓ Success</span>'
            )
        elif obj.error_message:
            return format_html(
                '<span style="color: red; font-weight: bold">✗ Failed</span><br>'
                '<span style="font-size: 0.8em">{}</span>',
                obj.error_message[:50] + ('...' if len(obj.error_message) > 50 else '')
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold">⋯ Processing</span>'
            )
    download_status.short_description = 'Status'
    
    def file_size_mb(self, obj):
        if obj.file_size > 0:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
        return "-"
    file_size_mb.short_description = 'File Size'
    
    def duration(self, obj):
        if obj.completed_at and obj.started_at:
            duration = obj.completed_at - obj.started_at
            return f"{duration.total_seconds():.1f}s"
        return "-"
    duration.short_description = 'Duration'


class DownloadInline(admin.TabularInline):
    model = Download
    extra = 0
    fields = ('video_title', 'download_type', 'success', 'started_at')
    readonly_fields = ('video_title', 'download_type', 'success', 'started_at')
    can_delete = False
    max_num = 5
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


# Override the default admin site header and title
admin.site.site_header = 'YouTube Downloader Bot Admin'
admin.site.site_title = 'YouTube Bot Admin'
admin.site.index_title = 'Bot Management'