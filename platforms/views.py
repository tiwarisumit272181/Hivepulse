from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse,response
from openpyxl import Workbook
from datetime import datetime
from openpyxl.styles import Protection
from .forms import ExcelUploadForm
from .models import amazonProduct, flipkartProduct, playstoreProduct
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken
import json
from django.contrib.auth import authenticate
from rest_framework.views import APIView
import openpyxl
from django.contrib.auth import logout
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.core.management import call_command
from django.core.mail import send_mail
from django.conf import settings

#use registartion code--------------------------------------------------------------------------------------------


# user registration end------------------------------------------------------------------------------------------------------------------

# user login -------------------------------------------------------------------------------------------
@csrf_exempt
def login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        user = authenticate(username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return JsonResponse({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            return JsonResponse({'error': 'Invalid credentials'}, status=400)
    elif request.method == 'GET':
        # You can choose to return a JsonResponse or render a login template
        return JsonResponse({'error': 'GET method is not allowed. Please use POST method to login.'}, status=405)

    # Handle any other HTTP method if needed
    return JsonResponse({'error': 'Method not allowed'}, status=405)

    
# user login end---------------------------------------------------------------------------------------------

# @csrf_exempt
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return JsonResponse({'message': 'Logged out successfully'})
    return JsonResponse({'error': 'Invalid method'}, status=405)

# common code-------------------------------------------------------------------------------


  # this is function way of writing django rst vie funcional   
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token(request):
    # If the request reaches this point, the token is valid
    return Response({'valid': True})

#common code end--------------------------------------------------------------------------------


# redirect code start-------------------------------------------------------


def loginPage(request):
    return render(request, 'platforms/login.html')

def home(request):
    return render (request,'platforms/home.html')

def amazonPage(request):
    return render (request, 'platforms/amazonForm.html')

def flipkartPage(request):
    return render (request, 'platforms/flipkartForm.html')

def playstorePage(request):
    return render (request, 'platforms/playstoreForm.html')


# redirect code end -------------------------------------------------------------------------------------



#  amazon start----------------------------------------------------------------------------------------
class DownloadAmazonExcelTemplateView(APIView):
    # permission_classes = [IsAuthenticated]
    def get(self,request):
    # Create a new workbook and select the active worksheet
        workbook = Workbook()
        worksheet = workbook.active
        # Define the column names
        column_names = ['Asin', 'Brand']
        # Write the column names to the first row 
        for column_index, column_name in enumerate(column_names, start=1):
            worksheet.cell(row=1, column=column_index, value=column_name)
        # Create the HttpResponse object with the appropriate headers
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=excel_template_amazon.xlsx'

        # Save the workbook to the response
        workbook.save(response)

        return response
    


class uploadAmazon(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]  these are alter nate because we alredy config thisin setting 
    def post(self,request):
        expected_columns = ['Asin', 'Brand']  # Define the expected column names
        if request.method == 'POST':
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                f = request.FILES['file']
                wb = openpyxl.load_workbook(f)
                ws = wb.active
                actual_columns = [cell.value for cell in ws[1]]
                if actual_columns != expected_columns:
                    return JsonResponse({'success': False, 'error': 'This file does not belong to this database downlaod Template and refill the data once again. Expected columns: ' + ', '.join(expected_columns)})
                data_rows = list(ws.iter_rows(min_row=2, values_only=True))
                
                if not data_rows:
                    return JsonResponse({'success': False, 'error': 'No data filled in your Excel file.'})
                # Get username of the logged-in user
                username = request.user.username
                # Generate session ID as a string representation of the current time
                session_id = datetime.now().strftime('%Y%m%d%H%M%S')  # e.g., '20230829103015'
                for row in ws.iter_rows(min_row=2, values_only=True):
                    Asin, Brand = row
                    if Asin and Brand:
                        amazonProduct.objects.create(
                            Asin=Asin,
                            Brand=Brand,
                            user=username,  # Set the user
                            sessionId=session_id  # Set the session ID
                        )
                      # Send email with session ID
                subject = 'Amazon Product Upload Session ID'
                message = f'Dear {username},\n\nYour session ID for the recent Amazon product upload is: {session_id}\n\nRegards,\nYour Team'
                recipient_list = ['tiwarisumit272181@gmail.com','harishkumar.c@hiveminds.in']
                send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list, fail_silently=False)
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Form is not valid'})
        else:
            form = ExcelUploadForm()
        return render(request, 'amazonForm.html', {'form': form})
    
# logic for getting review from amazon using the asin start------------------------------------------------------------------
 # Allows POST requests without CSRF token, use with caution
class runAmazonReviewScrappingScript(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self ,request):
        data = json.loads(request.body)
        sessionId=data.get('sessionId')
        username=request.user.username

        if request.method == 'POST':
            try:
                call_command('amazonScrapping' ,sessionId=sessionId,username=username)  # Ensure this matches your management command
                return JsonResponse({'status': 'success', 'message': ' Amazon Script executed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

## logic for getting review from amazon using the asin end---------------------------------------------------------------



# logic for getting sentiment of those reviews and saving to data running mechanism start ------------------------------------------------------
class runAmazonReviewSentimentScript(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def post(self,request):
        data = json.loads(request.body)#
        sessionId=data.get('sessionId')#
        username=request.user.username #
        if request.method == 'POST':
            try:
                call_command('amazonSentimentAnalysis',sessionId=sessionId,username=username)  # Ensure this matches your management command
                return JsonResponse({'status': 'success', 'message': ' Amazon sentiment analysis Script executed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    
# logic for getting sentiment of those reviews and saving to data running mechanism end----------------------------


#  amazon end ---------------------------------------------------------------------------------------------



#  flipkart start-------------------------------------------------------------------------------------------



class downloadFlipkartExcelTemplate(APIView):
    # permission_classes = [IsAuthenticated]
    def get(self,request):
 # Create a new workbook and select the active worksheet
        workbook = Workbook()
        worksheet = workbook.active
        # Define the column names
        column_names = ['Fsn', 'Brand']
        # Write the column names to the first row 
        for column_index, column_name in enumerate(column_names, start=1):
            cell = worksheet.cell(row=1, column=column_index, value=column_name)
        # Create the HttpResponse object with the appropriate headers
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=excel_template_flipkart.xlsx'

        # Save the workbook to the response
        workbook.save(response)

        return response



class uploadFlipkart(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self , request):
        expected_columns = ['Fsn', 'Brand']  # Define the expected column names
        if request.method == 'POST':
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                f = request.FILES['file']
                wb = openpyxl.load_workbook(f)
                ws = wb.active
                actual_columns = [cell.value for cell in ws[1]]
                if actual_columns != expected_columns:
                    return JsonResponse({'success': False, 'error': 'This file does not belong to this database. Expected columns: ' + ', '.join(expected_columns)})
                data_rows = list(ws.iter_rows(min_row=2, values_only=True))
                if not data_rows:
                    return JsonResponse({'success': False, 'error': 'No data filled in your Excel file.'})
                for row in ws.iter_rows(min_row=2, values_only=True):
                    Fsn, Brand = row
                    flipkartProduct.objects.create(Fsn=Fsn, Brand=Brand)
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Form is not valid'})
        else:
            form = ExcelUploadForm()
        return render(request, 'flipkartForm.html', {'form': form})



class runFlipkartReviewScrappingScript(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self,request):
        if request.method == 'POST':
            try:
                call_command('flipkartScrapping')  # Ensure this matches your management command
                return JsonResponse({'status': 'success', 'message': ' Flipkart Script executed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


class runFlipkartReviewSentimentScript(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self,request):
        if request.method == 'POST':
            try:
                call_command('flipkartSentimentAnalysis')  # Ensure this matches your management command
                return JsonResponse({'status': 'success', 'message': ' Flipkart sentiment analysis Script executed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

# flipkart end ----------------------------------------------------------------------------------------------



#  playstore start------------------------------------------------------------------------------------------


class downloadPlaystoreExcelTemplate(APIView):
    # permission_classes = [IsAuthenticated]
    def get(self,request):

    # Create a new workbook and select the active worksheet
        workbook = Workbook()
        worksheet = workbook.active
        # Define the column names
        column_names = ['AppId', 'Brand']
        # Write the column names to the first row 
        for column_index, column_name in enumerate(column_names, start=1):
            cell = worksheet.cell(row=1, column=column_index, value=column_name)
        # Create the HttpResponse object with the appropriate headers
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=excel_template_playstore.xlsx'

        # Save the workbook to the response
        workbook.save(response)

        return response


class uploadPlaystore(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self , request):
        expected_columns = ['AppId', 'Brand']  # Define the expected column names
        if request.method == 'POST':
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                f = request.FILES['file']
                wb = openpyxl.load_workbook(f)
                ws = wb.active
                actual_columns = [cell.value for cell in ws[1]]
                if actual_columns != expected_columns:
                    return JsonResponse({'success': False, 'error': 'This file does not belong to this database. Expected columns: ' + ', '.join(expected_columns)})
                data_rows = list(ws.iter_rows(min_row=2, values_only=True))
                if not data_rows:
                    return JsonResponse({'success': False, 'error': 'No data filled in your Excel file.'})
                for row in ws.iter_rows(min_row=2, values_only=True):
                    AppId, Brand = row
                    playstoreProduct.objects.create(AppId=AppId, Brand=Brand)
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Form is not valid'})
        else:
            form = ExcelUploadForm()
        return render(request, 'playstoreForm.html', {'form': form})
    

class runPlaystoreReviewScrappingScript(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self,request):
        if request.method == 'POST':
            try:
                call_command('playstoreScrapping')  # Ensure this matches your management command
                return JsonResponse({'status': 'success', 'message': ' playstore Script executed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



class runPlaystoreReviewSentimentScript(APIView):
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    def post(self,request):
        if request.method == 'POST':
            try:
                call_command('playstoreSentimentAnalysis')  # Ensure this matches your management command
                return JsonResponse({'status': 'success', 'message': ' Playstore sentiment analysis Script executed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
    # playstore end --------------------------------------------------------------------------------------------------------

# cross platform redirecting----------------------------------------------------------------------------------------------------------------

from django.shortcuts import render
from django.contrib.contenttypes.models import ContentType
from platforms.models import amazonProduct, flipkartProduct, playstoreProduct, review
def product_sentiment_view(request):
    results = []
    error = None

    if request.method == 'POST':
        platform = request.POST.get('platform')
        identifier = None

        # Determine which platform was selected and retrieve the corresponding identifier
        if platform == 'amazon':
            identifier = request.POST.get('Asin')
            model_class = amazonProduct
            identifier_field = 'Asin'
        elif platform == 'flipkart':
            identifier = request.POST.get('Fsn')
            model_class = flipkartProduct
            identifier_field = 'Fsn'
        elif platform == 'playstore':
            identifier = request.POST.get('AppId')
            model_class = playstoreProduct
            identifier_field = 'AppId'
        else:
            error = "Invalid platform selected."

        if identifier and not error:
            try:
                # Use filter to get all products that match the identifier and status
                products = model_class.objects.filter(**{identifier_field: identifier, 'Status': 'completed'})
                if not products.exists():
                    error = f"No completed product with the identifier {identifier} found in {platform.capitalize()}."
                else:
                    for product in products:
                        content_type = ContentType.objects.get_for_model(model_class)

                        # Get all reviews and their sentiment results for each product
                        reviews_queryset = review.objects.filter(content_type=content_type, object_id=product.id)
                        for rev in reviews_queryset:
                            sentiment_results = rev.sentimentresult_set.all()
                            for sentiment in sentiment_results:
                                results.append((rev.reviewContent, sentiment.estimatedResult))

                if not results:
                    error = "No comments or sentiment results found for the provided identifier."

            except model_class.DoesNotExist:
                error = f"Product with the provided identifier does not exist in the {platform.capitalize()} platform or is not yet completed."

    return render(request, 'platforms/product_sentiment.html', {'results': results, 'error': error})
