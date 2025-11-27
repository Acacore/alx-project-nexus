from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import *

@shared_task
def add_numbers(a, b):
    return a + b


@shared_task
def ping_celery():
    print("🔥 Celery is connected and working!")
    return "pong"


@shared_task
def flag_suspicious_ips(ip_address):
    print(f"Suspicious IP detected: {ip_address}")
    if settings.ADMINS:
        send_mail(
            subject=f"Suspicious IP Detected: {ip_address}",
            message=f"The IP {ip_address} was flagged as suspicious.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email for _, email in settings.ADMINS],
            fail_silently=True,
        )
    return f"IP {ip_address} flagged."




@shared_task
def send_comment_notification(comment_id):
    """
    Sends email notifications to the auction owner and all watchers
    when a new comment is posted on an auction.
    """
    try:
        comment = Comment.objects.get(id=comment_id)
        if comment.is_deleted:
            return f"Comment {comment_id} is deleted. No notifications sent."

        auction = comment.auction
        owner_email = auction.vendor.email

        # Prepare message
        subject = f"New comment on {auction.product}"
        message = f"{comment.user.username} commented: {comment.content}"

        # Notify auction owner
        if owner_email:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[owner_email],
                fail_silently=True,
            )

        # Notify all watchers (excluding auction owner)
        watchers = Watchlist.objects.filter(auction=auction).select_related("user")
        for watcher in watchers:
            user = watcher.user
            if user.email and user.email != owner_email:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )

        return f"Comment notification sent for comment {comment_id}"

    except Comment.DoesNotExist:
        return f"Comment {comment_id} does not exist."




@shared_task
def update_auction_statuses():
    """
    Updates auction statuses from 'OPEN'/'ongoing' to 'ENDED' if the end_time has passed.
    Notifies the winner if the reserve price is met.
    """
    now = timezone.now()
    # Get auctions that have ended but are still marked as ongoing/open
    ended_auctions = AuctionItem.objects.filter(end_time__lte=now, start__time=["ACTIVE", "Active"])

    for auction in ended_auctions:
        auction.status = 'ENDED'

        # Determine winner
        if auction.current_bid >= auction.reserve_price and auction.highest_bidder:
            auction.winner = auction.highest_bidder
            # Send notification to winner
            if auction.winner.email:
                send_mail(
                    subject=f"You Won Auction: {auction.product}",
                    message=f"Congratulations! You won {auction.product} for {auction.current_bid}.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[auction.winner.email],
                    fail_silently=True,
                )

        auction.save()

    return f"{ended_auctions.count()} auctions updated."


@shared_task
def send_bid_notification(bid_id):
    try:
        bid = Bid.objects.get(id=bid_id)
    except Bid.DoesNotExist:
        return f"Bid {bid_id} not found"

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
            )

    return f"Bid notification sent for bid {bid_id}"