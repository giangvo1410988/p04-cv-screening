import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_otp_email(sender_email, sender_password, receiver_email, otp):
    # Create the email content
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = 'Your OTP for Authentication'

    body = f'Your One-Time Password (OTP) is: {otp}'
    message.attach(MIMEText(body, 'plain'))

    # Create SMTP session
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()  # Enable security
        server.login(sender_email, sender_password)
        text = message.as_string()
        server.sendmail(sender_email, receiver_email, text)

# Usage example
sender_email = 'cv.screening.ai@gmail.com'
sender_password = 'vvso qmiv qnyv dmqw'  # Note: Use an App Password, not your regular password
receiver_email = 'giang.vo@aivision.vn'



otp = generate_otp()
send_otp_email(sender_email, sender_password, receiver_email, otp)
print(f"OTP sent to {receiver_email}")

