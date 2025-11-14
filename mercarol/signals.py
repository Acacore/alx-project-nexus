from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Comment, Watchlist

@receiver(post_save, sender=Comment)
def notify_watchers(sender, instance, created, **kwargs):
    if created and not instance.is_deleted:
        watchers = Watchlist.objects.filter(auction=instance.auction).select_related("user")
        for watcher in watchers:
            user = watcher.user
            if user.email:
                send_mail(
                    subject=f"New Comment on {instance.auction.product}",
                    message=f"A new comment was posted: '{instance.content[:50]}...'",
                    from_email="noreply@yourdomain.com",
                    recipient_list=[user.email],
                    fail_silently=True,
                )