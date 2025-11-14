from celery import shared_task

@shared_task
def add_numbers(a, b):
    return a + b



@shared_task
def flag_suspicious_ips():
    print("Running flag_suspicious_ips task...")
    return True
