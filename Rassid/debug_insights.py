import os
import django
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rassid.settings')
django.setup()

from notifications.models import EmailLog

try:

    
    first_log = EmailLog.objects.first()
    if first_log:
        email = first_log.recipient
        print(f"Testing with email: {email}")
    else:
        email = "admin@example.com"
        print("No logs found, using generic email.")

    logs = EmailLog.objects.filter(recipient=email).order_by('-sent_at')[:50]
    print(f"Found {logs.count()} logs.")

    today = timezone.now().date()
    dates = []
    delivery_rates = []
    failed_counts = []
    
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        day_logs = EmailLog.objects.filter(
            recipient=email, 
            sent_at__date=date
        )
        total = day_logs.count()
        failed = day_logs.filter(status='Failed').count()
        sent = total - failed
        
        rate = int((sent / total) * 100) if total > 0 else 0
        
        dates.append(date.strftime("%b %d"))
        delivery_rates.append(rate)
        failed_counts.append(failed)
        
    print("Dates:", dates)
    print("Rates:", delivery_rates)
    print("Failed:", failed_counts)

except Exception as e:
    print(f"Error: {e}")
