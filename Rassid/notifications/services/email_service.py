from django.core.mail import send_mail

def send_email_notification(to, subject, body):
    send_mail(
        subject,
        body,
        None,
        [to],
    )
