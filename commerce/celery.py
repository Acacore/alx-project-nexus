import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commerce.settings')
broker_url = os.environ.get("CELERY_BROKER_URL")

app = Celery('commerce', broker=broker_url)

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
