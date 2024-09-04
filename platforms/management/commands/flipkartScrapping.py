import re
import time
import datetime
import numpy as np
from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from django.contrib.contenttypes.models import ContentType
from platforms.models import flipkartProduct, review



class Command(BaseCommand):
    help = 'Fetch Flipkart reviews and save them to the database'

    def handle(self, *args, **kwargs):
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
        chrome_options.add_argument("--no-sandbox")  # Required for running as root on some systems
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        # chrome_options.set_capability('goog:loggingPrefs', {'browser': 'OFF'})

        # Set up the WebDriver with the specified options
        browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        # Fetch FSNs with 'pending' status
        fsn_list = flipkartProduct.objects.filter(Status='pending').values_list('Fsn', flat=True).distinct()

        for fsn in fsn_list:
            self.stdout.write(self.style.SUCCESS(f'Processing FSN: {fsn}'))
            soup = None  # Initialize soup to ensure it exists
            try:
                url = f"https://www.flipkart.com/realme-c55-rainforest-128-gb/product-reviews/itm054283d14c56e?pid={fsn}&lid=LSTMOBGNBYJPF2DEADSUWHGW7&marketplace=FLIPKART&page=1"
                browser.get(url)
                time.sleep(2)

                html = browser.page_source
                soup = BeautifulSoup(html, "html.parser")
                total_reviews_text = soup.find_all('div', {'class': 'row j-aW8Z'})[1].text
                nu = total_reviews_text.replace(',', '')
                nu = [int(word) for word in nu.split() if word.isdigit()]
                total_reviews_number = int(nu[0])
                num_pages = 1 #int(np.ceil(total_reviews_number / 10))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error fetching reviews for FSN {fsn}: {e}'))
                continue

            if soup:  # Proceed only if soup is successfully created
                for page in range(1, num_pages + 1):
                    page_url = f"https://www.flipkart.com/realme-c55-rainforest-128-gb/product-reviews/itm054283d14c56e?pid={fsn}&lid=LSTMOBGNBYJPF2DEADSUWHGW7&marketplace=FLIPKART&page={page}"
                    browser.get(page_url)
                    time.sleep(2)

                    soup = BeautifulSoup(browser.page_source, 'html.parser')
                    reviews_containers = soup.find_all('div', {'class': 'col EPCmJX Ma1fCG'})

                    for container in reviews_containers:
                        try:
                            review_content = container.find('div', {'class': 'ZmyHeo'}).text.strip()
                        except:
                            review_content = 'No content provided'  # Default if not found

                        try:
                            rating_text = container.find('div', {'class': 'XQDdHH Ga3i8K'}).text.strip()
                            rating = int(rating_text.split('.')[0])  # Extract integer rating from string
                        except:
                            rating = 0  # Default if not found

                        try:
                            review_date_str = container.find('p', {'class': '_2NsDsF'}).text.strip()
                            review_date = datetime.datetime.strptime(review_date_str, "%d %b, %Y").date()
                        except:
                            review_date = datetime.date.min  # Default to the earliest representable date

                        # Save each review as a separate entry in the database
                        flipkart_product_instance = flipkartProduct.objects.filter(Fsn=fsn, Status='pending').first()
                        if flipkart_product_instance:
                            content_type = ContentType.objects.get_for_model(flipkartProduct)
                            review_instance = review.objects.create(
                                content_type=content_type,
                                object_id=flipkart_product_instance.id,
                                reviewContent=review_content,
                                rating=rating,
                                created_at=review_date,
                            )

            # Update product status
            flipkartProduct.objects.filter(Fsn=fsn).update(Status='completed')

        browser.quit()
        self.stdout.write(self.style.SUCCESS('Successfully fetched and saved Flipkart reviews'))
