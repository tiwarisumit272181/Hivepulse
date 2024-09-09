import time
import datetime
from django.core.management.base import BaseCommand
from google_play_scraper import Sort, reviews_all,reviews
from django.contrib.contenttypes.models import ContentType
from platforms.models import playstoreProduct, review

class Command(BaseCommand):
    help = 'Fetch Google Play Store reviews and save them to the database'
    def add_arguments(self, parser):
        parser.add_argument('--sessionId', type=str, help='The session ID')
        parser.add_argument('--username', type=str, help='The username')

    def handle(self, *args, **options):
        # Fetch AppIds with 'pending' status
        appid_list = playstoreProduct.objects.filter(Status='pending').values_list('AppId', flat=True).distinct()
        sessionId = options['sessionId']
        username = options['username']
        for AppId in appid_list:
            self.stdout.write(self.style.SUCCESS(f'Processing AppId: {AppId}'))
            
            try:
                # Fetch  reviews for the app
                self.stdout.write(self.style.SUCCESS(f'Fetching reviews for {AppId}...'))
                reviews_data,_ = reviews(
                    AppId,
                    # sleep_milliseconds=0,  # Adjust as necessary
                    lang='en',
                    country='in',
                    sort=Sort.NEWEST,
                    count=10
                )

                self.stdout.write(self.style.SUCCESS(f'Fetched {len(reviews_data)} reviews for {AppId}'))

                # Process and save the reviews
                for review_data in reviews_data:
                    review_content = review_data.get('content', 'No content provided')
                    review_date = review_data.get('at', datetime.date.min)  # Use the earliest representable date as a fallback
                    rating = review_data.get('score', 0)
                    
                    # Save each review as a separate entry in the database
                    playstore_product_instance = playstoreProduct.objects.filter(AppId=AppId, Status='pending', sessionId=sessionId, user=username).first()
                    if playstore_product_instance:
                        content_type = ContentType.objects.get_for_model(playstoreProduct)
                        review_instance = review.objects.create(
                            content_type=content_type,
                            object_id=playstore_product_instance.id,
                            reviewContent=review_content,
                            rating=rating,
                            created_at=review_date,
                            user=username,
                            sessionId=sessionId,
                        )
                        

                # Update product status
                playstoreProduct.objects.filter(AppId=AppId, sessionId=sessionId, user=username).update(Status='completed')
                self.stdout.write(self.style.SUCCESS(f'Status updated for {AppId}'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error fetching reviews for AppId {AppId}: {e}'))
                

        self.stdout.write(self.style.SUCCESS('Successfully fetched and saved Google Play Store reviews'))
