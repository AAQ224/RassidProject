from django.db import models
from passengers.models import PassengerFlight

class Notification(models.Model):
    passengerFlight = models.ForeignKey(PassengerFlight, on_delete=models.CASCADE)
    channel = models.CharField(max_length=10, default="email")   
    content = models.TextField()
    status = models.CharField(max_length=20)  
    errorMessage = models.TextField(null=True, blank=True)
    sentAt = models.DateTimeField(auto_now_add=True)

class EmailLog(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    
    STATUS_CHOICES = (
        ('Sent', 'Sent'),
        ('Failed', 'Failed'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Sent')
    
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} -> {self.recipient} ({self.status})"