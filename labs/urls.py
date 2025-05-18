from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views, views

router = DefaultRouter()
router.register(r'lab-profiles', api_views.LabProfileViewSet)
router.register(r'test-definitions', api_views.TestDefinitionViewSet)

app_name = 'labs'

urlpatterns = [
    # Include API router URLs
    path('api/', include(router.urls)),
    
    # Patient lab order endpoints
    path('api/patient/me/lab-orders/', api_views.PatientLabOrdersView.as_view(), name='patient-lab-orders'),
    path('api/lab-orders/<int:pk>/', api_views.LabOrderDetailView.as_view(), name='lab-order-detail'),
    path('api/lab-results/<int:pk>/', api_views.LabResultDetailView.as_view(), name='lab-result-detail'),
    
    # Lab booking and management
    path('api/lab-orders/book/', api_views.book_lab_test, name='book-lab-test'),
    path('api/lab-orders/<int:lab_order_id>/choose-lab/', api_views.choose_lab_for_order, name='choose-lab-for-order'),
    
    # Staff endpoints
    path('api/staff/dashboard/', api_views.StaffDashboardView.as_view(), name='staff-dashboard'),
    path('api/staff/lab-orders/pending/', api_views.PendingLabOrdersView.as_view(), name='pending-lab-orders'),
    path('api/staff/lab-orders/<int:lab_order_id>/update-status/', api_views.update_lab_order_status, name='update-lab-order-status'),
    path('api/staff/lab-orders/<int:lab_order_id>/upload-result/', api_views.upload_lab_result, name='upload-lab-result'),
    path('api/lab-results/upload/', api_views.LabResultUploadView.as_view(), name='lab-result-upload'),
    
    # Legacy view URLs
    path('register/', views.lab_registration, name='register'),
    path('registration-pending/', views.registration_pending, name='registration_pending'),
    path('approve/<int:lab_id>/', views.approve_lab, name='approve_lab'),
    path('dashboard/', views.admin_lab_dashboard, name='dashboard'),
    path('lab-dashboard/', views.lab_dashboard, name='lab_dashboard'),
	path('add-test/', views.add_test_offering, name='add_test_offering'),
    path('edit-test/<int:offering_id>/', views.edit_test_offering, name='edit_test_offering'),
    path('delete-test/<int:offering_id>/', views.delete_test_offering, name='delete_test_offering'),
    path('order-tests/', views.order_tests, name='order_tests'),
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
    path('api/labs/api_available_labs/', views.api_available_labs, name='api_available_labs'),
    path('bulk-upload-tests/', views.bulk_upload_tests, name='bulk_upload_tests'),
    path('download-template/', views.download_template, name='download_template'),
    path('edit-lab/', views.edit_lab, name='edit_lab'),
    path('edit-lab/<int:lab_id>/', views.edit_lab, name='edit_lab'),
    path('deactivate-lab/<int:lab_id>/', views.deactivate_lab, name='deactivate_lab'),
    path('process-request/<str:request_id>/<str:request_type>/', views.process_lab_request, name='process_lab_request'),
]   