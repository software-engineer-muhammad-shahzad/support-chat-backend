from celery import shared_task


@shared_task
def test_celery():
    print("Celery task executed successfully!")
    return "Celery is working!"
