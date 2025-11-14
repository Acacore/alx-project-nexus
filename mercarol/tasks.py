from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import *

@shared_task
def add_numbers(a, b):
    return a + b



@shared_task
def flag_suspicious_ips():
    print("Running flag_suspicious_ips task...")
    return True



@shared_task
def send_comment_notification(comment_id):
    try:
        comment = Comment.objects.get(id=comment_id)
        if not comment.is_deleted:
            watchers = Watchlist.objects.filter(auction=comment.auction).select_related("user")
            for watcher in watchers:
                user = watcher.user
                if user.email:
                    send_mail(
                        subject=f"New Comment on {comment.auction.product}",
                        message=f"A new comment was posted: '{comment.content[:50]}...'",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
    except Comment.DoesNotExist:
        pass  # Comment deleted or not found





@shared_task
def update_auction_statuses():
    now = timezone.now()
    auctions = AuctionItem.objects.filter(status='OPEN', end_time__lte=now)
    for auction in auctions:
        auction.status = 'ENDED'
        if auction.current_bid >= auction.reserve_price and auction.highest_bidder:
            auction.winner = auction.highest_bidder
            # Notify winner
            if auction.winner.email:
                send_mail(
                    subject=f"You Won Auction: {auction.product}",
                    message=f"Congratulations! You won {auction.product} for {auction.current_bid}.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[auction.winner.email],
                    fail_silently=True,
                )
        auction.save()


@shared_task
def send_bid_notification(bid_id):
    try:
        bid = Bid.objects.get(id=bid_id)
        auction = bid.auction
        watchers = Watchlist.objects.filter(auction=auction).select_related("user")
        for watcher in watchers:
            user = watcher.user
            if user.email and user != bid.user:
                send_mail(
                    subject=f"New Bid on {auction.product}",
                    message=f"A new bid of {bid.amount} was placed on {auction.product}.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
    except Bid.DoesNotExist:
        pass