from django.urls import path
from . import views
from .api_views import LabResultUploadView

app_name = 'labs'

urlpatterns = [
    path('register/', views.lab_registration, name='register'),
    path('registration-pending/', views.registration_pending, name='registration_pending'),
    path('approve/<int:lab_id>/', views.approve_lab, name='approve_lab'),
    path('dashboard/', views.admin_lab_dashboard, name='dashboard'),
    path('lab-dashboard/', views.lab_dashboard, name='lab_dashboard'),
    
    path('add-test/', views.add_test_offering, name='add_test_offering'),
    path('edit-test/<int:offering_id>/', views.edit_test_offering, name='edit_test_offering'),
    path('delete-test/<int:offering_id>/', views.delete_test_offering, name='delete_test_offering'),
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/confirm-payment/', views.confirm_payment, name='confirm_payment'),
    path('orders/<int:order_id>/update-sample/', views.update_sample_status, name='update_sample_status'),
    path('orders/<int:order_id>/upload-result_api/', views.upload_result_api, name='upload_result_api'),
    path('doctor-requests/', views.doctor_requests, name='doctor_requests'),
    path('manage-tests/', views.manage_tests, name='manage_tests'),
    path('api/upload-result/', views.upload_result_api, name='upload_result_api'),
    path('results/<int:result_id>/download/', views.download_lab_result, name='download_result'),
    path('api/labs/available/', views.available_labs, name='available_labs'),
    path('bulk-upload-tests/', views.bulk_upload_tests, name='bulk_upload_tests'),
    path('download-template/', views.download_template, name='download_template'),
    path('edit-lab/', views.edit_lab, name='edit_lab'),
    path('edit-lab/<int:lab_id>/', views.edit_lab, name='edit_lab'),
    path('deactivate-lab/<int:lab_id>/', views.deactivate_lab, name='deactivate_lab'),
]   