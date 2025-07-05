from django.urls import path
from . import views

app_name = 'scheduling'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Appointments
    path('appointments/', views.AppointmentListView.as_view(), name='appointment_list'),
    path('appointments/<uuid:pk>/', views.AppointmentDetailView.as_view(), name='appointment_detail'),
    path('appointments/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('appointments/create-integrated/', views.integrated_appointment_create, name='integrated_appointment_create'),
    path('appointments/<uuid:pk>/update/', views.AppointmentUpdateView.as_view(), name='appointment_update'),
    path('appointments/<uuid:pk>/delete/', views.AppointmentDeleteView.as_view(), name='appointment_delete'),
    path('appointments/<uuid:pk>/status/', views.change_appointment_status, name='change_appointment_status'),
    
    # Calendar
    path('calendar/', views.appointment_calendar, name='appointment_calendar'),
    path('calendar/events/', views.get_calendar_appointments, name='get_calendar_appointments'),
    path('slots/', views.get_available_slots, name='get_available_slots'),
    
    # Admin - Schedules
    path('schedules/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/', views.ScheduleDetailView.as_view(), name='schedule_detail'),
    path('schedules/<int:pk>/update/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
    path('schedules/<int:pk>/delete/', views.ScheduleDeleteView.as_view(), name='schedule_delete'),
    
    # Admin - Doctors
    path('doctors/', views.DoctorListView.as_view(), name='doctor_list'),
    path('doctors/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor_detail'),
    path('doctors/<int:pk>/edit/', views.DoctorUpdateView.as_view(), name='doctor_edit'),
    
    # Admin - Holidays
    path('holidays/', views.HolidayListView.as_view(), name='holiday_list'),
    path('holidays/create/', views.HolidayCreateView.as_view(), name='holiday_create'),
    path('holidays/<int:pk>/', views.HolidayDetailView.as_view(), name='holiday_detail'),
    path('holidays/<int:pk>/update/', views.HolidayUpdateView.as_view(), name='holiday_update'),
    path('holidays/<int:pk>/delete/', views.HolidayDeleteView.as_view(), name='holiday_delete'),
    
    # Admin - Settings
    path('settings/', views.scheduling_settings, name='settings'),
    
    # Integration endpoints
    path('sync-appointments/', views.sync_with_existing_appointments, name='sync_appointments'),
    path('generate-slots/', views.generate_slots_from_existing_availability, name='generate_slots'),
    
    # Appointment Types (if django-appointment is installed)
    path('appointment-types/', views.AppointmentTypeListView.as_view(), name='appointment_type_list'),
    path('appointment-types/create/', views.AppointmentTypeCreateView.as_view(), name='appointment_type_create'),
    path('appointment-types/<int:pk>/update/', views.AppointmentTypeUpdateView.as_view(), name='appointment_type_update'),
    path('appointment-types/<int:pk>/delete/', views.AppointmentTypeDeleteView.as_view(), name='appointment_type_delete'),
] 