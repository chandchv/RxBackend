from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth import get_user_model
from .forms import LabOrderForm, LabRegistrationForm, LabTestOfferingForm, ExternalLabTestOfferingForm
from .models import (
    ExternalLabTestOffering, LabProfile, LabTestOffering, LabUser, TestDefinition, 
    LabOrder, LabOrderTest, LabResult, CommissionLedger,
    # New models for enhanced dashboard
    SpecimenContainer, Specimen, SpecimenProcessing,
    QualityControlTest, QCResult,
    LabReport, TestResult,
    ReportDelivery, CommunicationLog,
    B2BPartner, B2BInvoice, B2BInvoiceItem,
    LabAnalytics
)
from users.models import Appointment, Doctor, Patient, Lab, LabTest, LabTestPrescription
from django.db.models import Q, Sum, Count
import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
import csv
import io
import logging
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.models import Group
from notifications.models import Notification
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal

User = get_user_model()
logger = logging.getLogger(__name__)

# Create your views here.

def get_lab_profile_for_user(user):
    """
    Helper function to get lab profile for a user, handling both direct ownership and lab user associations.
    Returns the lab profile or raises LabProfile.DoesNotExist if not found.
    """
    try:
        # First check if user has a direct lab profile
        return LabProfile.objects.get(user=user)
    except LabProfile.DoesNotExist:
        # Check if user is a lab staff member
        try:
            lab_user = LabUser.objects.get(user=user, is_active=True)
            return lab_user.lab_profile
        except LabUser.DoesNotExist:
            raise LabProfile.DoesNotExist("User is not associated with any lab")

def lab_registration(request):
    if request.method == 'POST':
        form = LabRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Create the user first
                user = form.save(commit=False)
                user.email = form.cleaned_data['email']
                user.user_type = 'LAB'  # Set user type to LAB
                user.set_password(form.cleaned_data['password1'])
                user.save()
                
                # Get or create the lab group
                lab_group, created = Group.objects.get_or_create(name='lab')
                
                # Add user to lab group
                user.groups.add(lab_group)
                
                # Create the lab profile and associate it with the user
                lab_profile = LabProfile.objects.create(
                    user=user,
                    name=form.cleaned_data['name'],
                    registration_number=form.cleaned_data['registration_number'],
                    contact_person=form.cleaned_data['contact_person'],
                    contact_person_designation=form.cleaned_data['contact_person_designation'],
                    address=form.cleaned_data['address'],
                    phone_number=form.cleaned_data['phone_number'],
                    email=form.cleaned_data['email'],
                    certifications=form.cleaned_data['certifications'],
                    is_approved=False  # Set initial approval status to False
                )
                
                # Send email to admin for approval
                admin_users = User.objects.filter(is_superuser=True)
                for admin in admin_users:
                    send_mail(
                        'New Lab Registration Pending Approval',
                        f'A new lab has registered and is waiting for approval:\n\n'
                        f'Lab Name: {lab_profile.name}\n'
                        f'Registration Number: {lab_profile.registration_number}\n'
                        f'Contact Person: {lab_profile.contact_person}\n'
                        f'Email: {lab_profile.email}\n\n'
                        f'Please review and approve the registration.',
                        'noreply@rxdoctor.com',
                        [admin.email],
                        fail_silently=False,
                    )
                
                # Send confirmation email to lab
                send_mail(
                    'Lab Registration Received',
                    f'Thank you for registering with RxDoctor!\n\n'
                    f'Your registration details:\n'
                    f'Lab Name: {lab_profile.name}\n'
                    f'Registration Number: {lab_profile.registration_number}\n\n'
                    f'Your registration is pending approval. You will receive an email once your account is approved.',
                    'noreply@rxdoctor.com',
                    [lab_profile.email],
                    fail_silently=False,
                )
                
                # Authenticate and log in the user
                user = authenticate(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password1']
                )
                if user is not None:
                    login(request, user)
                
                messages.success(request, 'Registration successful! Your account is pending approval.')
                return redirect('labs:registration_pending')
            except Exception as e:
                messages.error(request, f'Error during registration: {str(e)}')
                return render(request, 'labs/registration.html', {'form': form})
    else:
        form = LabRegistrationForm()
    
    return render(request, 'labs/registration.html', {'form': form})

def registration_pending(request):
    return render(request, 'labs/registration_pending.html')

@login_required
def approve_lab(request, lab_id):
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can approve labs.")
    
    lab = get_object_or_404(LabProfile, id=lab_id)
    lab.is_approved = True
    lab.save()
    
    messages.success(request, f'Lab {lab.name} has been approved.')
    return redirect('labs:dashboard')

@login_required
def admin_lab_dashboard(request):
    # For superusers, show admin dashboard
    if request.user.is_superuser:
        labs = LabProfile.objects.all().order_by('-created_at')
        approved_labs_count = LabProfile.objects.filter(is_approved=True).count()
        pending_labs_count = LabProfile.objects.filter(is_approved=False).count()
        return render(request, 'labs/dashboard.html', {
            'labs': labs,
            'approved_labs_count': approved_labs_count,
            'pending_labs_count': pending_labs_count,
            'is_superuser': True
        })
    
    # For regular lab users
    try:
        lab_profile = get_lab_profile_for_user(request.user)
        if not lab_profile.is_approved:
            messages.error(request, 'Your lab account is not yet approved.')
            return redirect('labs:registration_pending')
            
        # Get statistics
        stats = {
            'total_tests': ExternalLabTestOffering.objects.filter(lab_profile=lab_profile).count(),
            'pending_orders': LabOrder.objects.filter(
                chosen_lab=lab_profile,
                status='PENDING'
            ).count(),
            'completed_orders': LabOrder.objects.filter(
                chosen_lab=lab_profile,
                status='COMPLETED'
            ).count(),
            'total_revenue': LabOrder.objects.filter(
                chosen_lab=lab_profile,
                status='COMPLETED'
            ).aggregate(total=Sum('total_price'))['total'] or 0
        }
        
        # Get recent orders
        recent_orders = LabOrder.objects.filter(
            chosen_lab=lab_profile
        ).order_by('-order_date')[:5]
        
        # Get available tests
        available_tests = ExternalLabTestOffering.objects.filter(
            lab_profile=lab_profile,
            is_active=True
        ).order_by('test__name')[:5]
        
        # Get doctor requests
        doctor_requests = LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='PENDING'
        ).select_related('doctor', 'patient')[:5]
        
        # Get payment statistics
        payment_stats = {
            'pending': LabOrder.objects.filter(
                chosen_lab=lab_profile,
                status='PENDING'
            ).aggregate(total=Sum('total_price'))['total'] or 0,
            'completed': LabOrder.objects.filter(
                chosen_lab=lab_profile,
                status='COMPLETED'
            ).aggregate(total=Sum('total_price'))['total'] or 0,
            'total': LabOrder.objects.filter(
                chosen_lab=lab_profile
            ).aggregate(total=Sum('total_price'))['total'] or 0
        }
        
        context = {
            'lab_profile': lab_profile,
            'stats': stats,
            'recent_orders': recent_orders,
            'available_tests': available_tests,
            'doctor_requests': doctor_requests,
            'payment_stats': payment_stats,
            'is_superuser': request.user.is_superuser,
        }
        
        return render(request, 'labs/lab_dashboard.html', context)
    except LabProfile.DoesNotExist:
        messages.error(request, 'Lab profile not found. Please complete your lab registration.')
        return redirect('labs:register')
    except Exception as e:
        messages.error(request, f'Error accessing dashboard: {str(e)}')
        return redirect('labs:dashboard')

@login_required
def lab_dashboard(request):
    """Enhanced lab dashboard with comprehensive management features"""
    # Get the lab profile for the logged-in user
    # First check if user has a direct lab profile
    try:
        lab_profile = LabProfile.objects.get(user=request.user)
    except LabProfile.DoesNotExist:
        # Check if user is a lab staff member
        try:
            lab_user = LabUser.objects.get(user=request.user, is_active=True)
            lab_profile = lab_user.lab_profile
        except LabUser.DoesNotExist:
            messages.error(request, 'Lab profile not found. Please contact your administrator.')
            return redirect('users:login')
    
    # Get comprehensive statistics
    stats = {
        'total_tests': ExternalLabTestOffering.objects.filter(lab_profile=lab_profile).count(),
        'pending_orders': LabOrder.objects.filter(chosen_lab=lab_profile, status='PENDING').count(),
        'completed_orders': LabOrder.objects.filter(chosen_lab=lab_profile, status='COMPLETED').count(),
        'total_revenue': LabOrder.objects.filter(
            chosen_lab=lab_profile, 
            status='COMPLETED'
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'specimens_pending': Specimen.objects.filter(
            lab_order__chosen_lab=lab_profile,
            processing__processing_completed__isnull=True
        ).count(),
        'qc_tests_today': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            run_date__date=timezone.now().date()
        ).count(),
        'reports_pending_approval': LabReport.objects.filter(
            lab_order__chosen_lab=lab_profile,
            status='PENDING_REVIEW'
        ).count(),
        'critical_values_today': TestResult.objects.filter(
            report__lab_order__chosen_lab=lab_profile,
            abnormality_type__in=['CRITICAL_HIGH', 'CRITICAL_LOW'],
            performed_at__date=timezone.now().date()
        ).count(),
    }
    
    # Get recent orders with specimens
    recent_orders = LabOrder.objects.filter(
        chosen_lab=lab_profile
    ).select_related('patient', 'doctor').prefetch_related('specimens').order_by('-order_date')[:5]
    
    # Get available tests
    available_tests = ExternalLabTestOffering.objects.filter(lab_profile=lab_profile, is_active=True).order_by('test__name')[:5]
    
    # Get recent doctor requests (combine both LabTest and LabOrder)
    lab_tests = LabTest.objects.filter(
        prescription__external_lab=lab_profile,
        status__in=['REQUESTED', 'ASSIGNED']
    ).select_related(
        'prescription__patient',
        'prescription__doctor',
        'test_definition'
    ).order_by('-created_at')[:5]
    
    # Format lab tests
    doctor_requests = []
    for test in lab_tests:
        doctor_requests.append({
            'id': f'test_{test.id}',
            'type': 'test',
            'test_name': test.test_definition.name if test.test_definition else 'Unknown Test',
            'patient_name': test.prescription.patient.get_full_name() if getattr(test.prescription, 'patient', None) and hasattr(test.prescription.patient, 'get_full_name') else (test.prescription.patient.get_full_name() if getattr(test.prescription, 'patient', None) else str(test.prescription.patient)),
            'doctor_name': f"Dr. {test.prescription.doctor.name}" if getattr(test.prescription, 'doctor', None) and hasattr(test.prescription.doctor, 'name') else (test.prescription.doctor.get_full_name() if getattr(test.prescription, 'doctor', None) else str(test.prescription.doctor)),
            'date': test.created_at,
            'status': test.status,
        })
    
    # Get recent lab orders
    recent_lab_orders = LabOrder.objects.filter(
        chosen_lab=lab_profile,
        status='PENDING'
    ).select_related('doctor', 'patient').order_by('-order_date')[:5]
    
    # Add lab orders to doctor requests
    for order in recent_lab_orders:
        doctor_requests.append({
            'id': f'order_{order.id}',
            'type': 'order',
            'test_name': ', '.join([test.name for test in order.tests.all()]),
            'patient_name': order.patient.get_full_name() if getattr(order, 'patient', None) and hasattr(order.patient, 'get_full_name') else (order.patient.get_full_name() if getattr(order, 'patient', None) else str(order.patient)),
            'doctor_name': f"Dr. {order.doctor.name}" if getattr(order, 'doctor', None) and hasattr(order.doctor, 'name') else (order.doctor.get_full_name() if getattr(order, 'doctor', None) else str(order.doctor)),
            'date': order.order_date,
            'status': order.status,
        })
    
    # Sort combined requests by date
    doctor_requests.sort(key=lambda x: x['date'], reverse=True)
    
    # Get payment statistics
    payment_stats = {
        'pending': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='PENDING'
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'completed': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='COMPLETED'
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'total': LabOrder.objects.filter(
            chosen_lab=lab_profile
        ).aggregate(total=Sum('total_price'))['total'] or 0
    }
    
    # Get specimen management data
    specimen_stats = {
        'pending_collection': Specimen.objects.filter(
            lab_order__chosen_lab=lab_profile,
            collection_date__isnull=True
        ).count(),
        'in_processing': Specimen.objects.filter(
            lab_order__chosen_lab=lab_profile,
            processing__processing_started__isnull=False,
            processing__processing_completed__isnull=True
        ).count(),
        'completed_today': Specimen.objects.filter(
            lab_order__chosen_lab=lab_profile,
            processing__processing_completed__date=timezone.now().date()
        ).count(),
        'containers_available': SpecimenContainer.objects.filter(
            lab_profile=lab_profile,
            is_available=True
        ).count(),
    }
    
    # Get quality control data
    qc_stats = {
        'tests_today': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            run_date__date=timezone.now().date()
        ).count(),
        'in_control': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            run_date__date=timezone.now().date(),
            is_in_control=True
        ).count(),
        'out_of_control': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            run_date__date=timezone.now().date(),
            is_in_control=False
        ).count(),
        'pending_review': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            reviewed_by__isnull=True
        ).count(),
    }
    
    # Get report management data
    report_stats = {
        'draft_reports': LabReport.objects.filter(
            lab_order__chosen_lab=lab_profile,
            status='DRAFT'
        ).count(),
        'pending_review': LabReport.objects.filter(
            lab_order__chosen_lab=lab_profile,
            status='PENDING_REVIEW'
        ).count(),
        'approved_today': LabReport.objects.filter(
            lab_order__chosen_lab=lab_profile,
            status='APPROVED',
            approved_at__date=timezone.now().date()
        ).count(),
        'released_today': LabReport.objects.filter(
            lab_order__chosen_lab=lab_profile,
            status='RELEASED',
            released_at__date=timezone.now().date()
        ).count(),
    }
    
    # Get B2B partner data
    b2b_stats = {
        'active_partners': B2BPartner.objects.filter(is_active=True).count(),
        'pending_invoices': B2BInvoice.objects.filter(
            lab_profile=lab_profile,
            status='SENT'
        ).count(),
        'overdue_invoices': B2BInvoice.objects.filter(
            lab_profile=lab_profile,
            status='OVERDUE'
        ).count(),
        'total_b2b_revenue': B2BInvoice.objects.filter(
            lab_profile=lab_profile,
            status='PAID'
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
    }
    
    # Get recent specimens
    recent_specimens = Specimen.objects.filter(
        lab_order__chosen_lab=lab_profile
    ).select_related('container', 'lab_order__patient').order_by('-created_at')[:5]
    
    # Get recent QC results
    recent_qc_results = QCResult.objects.filter(
        qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile
    ).select_related('qc_test', 'qc_test__test_definition').order_by('-run_date')[:5]
    
    # Get recent reports
    recent_reports = LabReport.objects.filter(
        lab_order__chosen_lab=lab_profile
    ).select_related('lab_order__patient').order_by('-created_at')[:5]
    
    # Get recent communications
    recent_communications = CommunicationLog.objects.filter(
        lab_profile=lab_profile
    ).select_related('recipient').order_by('-sent_at')[:5]
    
    # Get analytics data for charts
    analytics_data = LabAnalytics.objects.filter(
        lab_profile=lab_profile,
        date__gte=timezone.now().date() - timezone.timedelta(days=30)
    ).order_by('date')
    
    context = {
        'lab_profile': lab_profile,
        'stats': stats,
        'recent_orders': recent_orders,
        'available_tests': available_tests,
        'doctor_requests': doctor_requests,
        'payment_stats': payment_stats,
        'specimen_stats': specimen_stats,
        'qc_stats': qc_stats,
        'report_stats': report_stats,
        'b2b_stats': b2b_stats,
        'recent_specimens': recent_specimens,
        'recent_qc_results': recent_qc_results,
        'recent_reports': recent_reports,
        'recent_communications': recent_communications,
        'analytics_data': analytics_data,
        'is_superuser': request.user.is_superuser,
    }
    
    return render(request, 'labs/lab_dashboard.html', context)

@login_required
def add_test_offering(request):
    # Allow both superusers and lab users to add test offerings
    if not request.user.is_superuser:
        try:
            lab_profile = get_lab_profile_for_user(request.user)
            if not lab_profile.is_approved:
                messages.error(request, 'Your lab account is not yet approved.')
                return redirect('labs:registration_pending')
        except LabProfile.DoesNotExist:
            messages.error(request, 'You must be a lab user to add test offerings.')
            return redirect('labs:lab_dashboard')
    
    if request.method == 'POST':
        form = ExternalLabTestOfferingForm(request.POST)
        if form.is_valid():
            try:
                # Get the lab profile
                if request.user.is_superuser:
                    lab_profile = form.cleaned_data.get('lab_profile')
                    if not lab_profile:
                        messages.error(request, 'Please select a lab.')
                        return render(request, 'labs/add_test_offering.html', {'form': form})
                else:
                    lab_profile = get_lab_profile_for_user(request.user)
                
                # Create the test offering
                offering = ExternalLabTestOffering(
                    test=form.cleaned_data['test'],
                    price=form.cleaned_data['price'],
                    turnaround_time_hours=form.cleaned_data['turnaround_time_hours'],
                    offers_home_collection=form.cleaned_data['offers_home_collection'],
                    specific_instructions=form.cleaned_data['specific_instructions'],
                    lab_profile=lab_profile,
                    is_active=True
                )
                
                # Check if this is a custom test
                if ('is_custom_test' in request.POST and request.POST.get('is_custom_test') == 'true') or ('custom_test_name' in request.POST and request.POST.get('custom_test_name').strip()):
                    custom_test_name = request.POST.get('custom_test_name', '').strip()
                    if custom_test_name:
                        from labs.models import TestDefinition
                        test, created = TestDefinition.objects.get_or_create(name=custom_test_name)
                        offering.test = test
                
                # Now save the offering
                offering.save()
                
                messages.success(request, 'Test offering added successfully!')
                return redirect('labs:lab_dashboard')
            except Exception as e:
                messages.error(request, f'Error adding test offering: {str(e)}')
                return render(request, 'labs/add_test_offering.html', {'form': form})
    else:
        form = ExternalLabTestOfferingForm()
        if not request.user.is_superuser:
            # For regular lab users, don't show the lab selection field
            form.fields.pop('lab_profile', None)
    
    return render(request, 'labs/add_test_offering.html', {
        'form': form,
        'is_superuser': request.user.is_superuser
    })

@login_required
def edit_test_offering(request, offering_id):
    try:
        lab_profile = get_lab_profile_for_user(request.user)
        if not lab_profile.is_approved:
            raise PermissionDenied("Your lab account is not yet approved.")
        
        offering = get_object_or_404(ExternalLabTestOffering, id=offering_id, lab_profile=lab_profile)
        
        if request.method == 'POST':
            form = LabTestOfferingForm(request.POST, instance=offering)
            if form.is_valid():
                # Don't save the form yet
                test_offering = form.save(commit=False)
                
                # Check if this is a custom test
                if ('is_custom_test' in request.POST and request.POST.get('is_custom_test') == 'true') or ('custom_test_name' in request.POST and request.POST.get('custom_test_name').strip()):
                    custom_test_name = request.POST.get('custom_test_name', '').strip()
                    if custom_test_name:
                        # Import at the module level instead
                        from labs.models import TestDefinition
                        test, created = TestDefinition.objects.get_or_create(name=custom_test_name)
                        test_offering.test = test
                
                # Now save the offering
                test_offering.save()
                
                messages.success(request, f'Test {offering.test.name} updated successfully.')
                return redirect('labs:lab_dashboard')
        else:
            form = LabTestOfferingForm(instance=offering)
        
        return render(request, 'labs/add_edit_offering.html', {
            'form': form,
            'title': 'Edit Test Offering',
            'offering': offering
        })
    except LabProfile.DoesNotExist:
        raise PermissionDenied("You are not authorized to access this page.")

@login_required
def delete_test_offering(request, offering_id):
    try:
        lab_profile = get_lab_profile_for_user(request.user)
        if not lab_profile.is_approved:
            raise PermissionDenied("Your lab account is not yet approved.")
        
        offering = get_object_or_404(ExternalLabTestOffering, id=offering_id, lab_profile=lab_profile)
        
        if request.method == 'POST':
            offering.is_active = False
            offering.save()
            messages.success(request, f'Test {offering.test.name} removed successfully.')
            return redirect('labs:lab_dashboard')
        
        return render(request, 'labs/confirm_delete.html', {
            'offering': offering
        })
    except LabProfile.DoesNotExist:
        raise PermissionDenied("You are not authorized to access this page.")

@login_required
def order_tests(request):
    lab_profile = None
    # Initialize variables to avoid scope issues
    form = None
    available_tests = None
    limited_tests = []
    total_available = 0
    test_prices = {}
    from collections import defaultdict
    tests_by_category = defaultdict(list)
    categorized_tests = []
    
    try:
        # Check if the user is associated with a lab
        lab_profile = get_lab_profile_for_user(request.user)
        
        if not lab_profile.is_approved:
            messages.error(request, 'Your lab must be approved to order tests.')
            return redirect('labs:lab_dashboard')

        if request.method == 'POST':
            # Get default clinic (first clinic or create one if none exists)
            from users.models import Clinic
            clinic = Clinic.objects.first()
            if not clinic:
                clinic = Clinic.objects.create(name="Default Clinic", address="Default Address")
            
            form = LabOrderForm(request.POST, clinic=clinic)
            if form.is_valid():
                # Save the order without committing to get the patient
                lab_order = form.save(commit=False)
                lab_order.chosen_lab = lab_profile
                lab_order.status = 'PENDING_PAYMENT'
                
                # Set the clinic for the patient if it was created
                if hasattr(lab_order, 'patient') and lab_order.patient:
                    # Try to get clinic from lab profile or use a default
                    try:
                        # If lab has an associated clinic, use it
                        clinic = lab_profile.user.userprofile.clinic if hasattr(lab_profile.user, 'userprofile') else None
                        if clinic:
                            lab_order.patient.clinic = clinic
                            lab_order.patient.save()
                    except:
                        pass  # Use default clinic
                        
                lab_order.save()  # Save to generate ID
                
                # Calculate total price and add selected tests
                total_price = 0
                for test in form.cleaned_data['tests']:
                    try:
                        # Get the lab's price for this test
                        test_offering = ExternalLabTestOffering.objects.get(
                            lab_profile=lab_profile,
                            test=test,
                            is_active=True
                        )
                        total_price += test_offering.price
                        lab_order.tests.add(test)
                    except ExternalLabTestOffering.DoesNotExist:
                        continue

                # Update the total price
                lab_order.total_price = total_price
                lab_order.save()
                
                messages.success(request, 'Lab tests ordered successfully.')
                return redirect('labs:lab_dashboard')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            # Get default clinic for GET request
            from users.models import Clinic
            clinic = Clinic.objects.first()
            if not clinic:
                clinic = Clinic.objects.create(name="Default Clinic", address="Default Address")
            
            form = LabOrderForm(clinic=clinic)
            
            # Only show tests that this lab offers
            available_tests = TestDefinition.objects.filter(
                offered_by_external_labs__lab_profile=lab_profile,
                offered_by_external_labs__is_active=True
            ).distinct().order_by('category', 'name')
            
            if not available_tests.exists():
                messages.warning(request, 'Please add some test offerings before creating orders.')
                return redirect('labs:manage_tests')
                
            form.fields['tests'].queryset = available_tests
            
            # Get all test offerings for this lab in one query to avoid N+1 problem
            test_offerings = ExternalLabTestOffering.objects.filter(
                lab_profile=lab_profile,
                is_active=True,
                test__in=available_tests
            ).select_related('test')
            
            # Create price lookup dictionary
            test_prices = {}
            for offering in test_offerings:
                test_prices[offering.test.id] = {
                    'price': offering.price,
                    'turnaround_time': offering.turnaround_time_hours,
                    'home_collection': offering.offers_home_collection
                }
            
            # Group tests by category for better display
            # tests_by_category is already initialized above
            
            # Get search and filter parameters
            search_query = request.GET.get('search', '').strip()
            category_filter = request.GET.get('category', '').strip()
            
            # Apply search and filters
            filtered_tests = available_tests
            
            if search_query:
                filtered_tests = filtered_tests.filter(
                    Q(name__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(short_code__icontains=search_query)
                )
            
            if category_filter:
                if category_filter == 'Uncategorized':
                    filtered_tests = filtered_tests.filter(Q(category__isnull=True) | Q(category=''))
                else:
                    filtered_tests = filtered_tests.filter(category=category_filter)
            
            # For display, limit to reasonable number but allow pagination-like behavior
            # If searching or filtering, show more results
            if search_query or category_filter:
                limited_tests = list(filtered_tests[:100])  # Show up to 100 when searching
            else:
                # Default view: show sample from each category but more tests
                if filtered_tests.count() > 100:
                    # Get all unique categories from available tests
                    all_categories = set()
                    for test in filtered_tests[:300]:  # Sample more tests to find categories
                        category = test.category or 'Uncategorized'
                        all_categories.add(category)
                    
                    limited_tests = []
                    # Get more tests from each category for better variety
                    for category in sorted(all_categories):
                        if category == 'Uncategorized':
                            cat_tests = list(filtered_tests.filter(category__isnull=True)[:8]) + \
                                       list(filtered_tests.filter(category='')[:8])
                        else:
                            cat_tests = list(filtered_tests.filter(category=category)[:8])
                        
                        limited_tests.extend(cat_tests)
                        
                        # Show more tests - up to 120 total
                        if len(limited_tests) >= 120:
                            break
                    
                    limited_tests = limited_tests[:120]
                else:
                    limited_tests = list(filtered_tests[:100])
            
            total_available = filtered_tests.count()
            
            # Now organize the limited tests by category for display
            for test in limited_tests:
                category = test.category or 'Uncategorized'
                tests_by_category[category].append(test)
                
                # Set default values if not found in offerings
                if test.id not in test_prices:
                    test_prices[test.id] = {
                        'price': 0,
                        'turnaround_time': 24,
                        'home_collection': False
                    }
        
        # Convert defaultdict to list of tuples for template compatibility
        categorized_tests = sorted(tests_by_category.items())
        
        # Create categories list from categorized_tests
        categories = [cat for cat, tests in categorized_tests]
        
        return render(request, 'labs/order_lab_tests.html', {
            'form': form,
            'lab_profile': lab_profile,
            'available_tests': limited_tests,
            'total_available_tests': total_available,
            'categorized_tests': categorized_tests,
            'test_prices': test_prices,
            'categories': categories
        })
        
    except LabProfile.DoesNotExist:
        messages.error(request, 'You must be associated with a lab to access this page.')
        return redirect('labs:lab_dashboard')
    except Exception as e:
        messages.error(request, f'Error ordering tests: {str(e)}')
        return redirect('labs:lab_dashboard')

@login_required
def order_lab_tests(request, patient_id):
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Verify doctor has access to this patient
        if not Appointment.objects.filter(doctor=doctor, patient=patient).exists():
            raise PermissionDenied("You are not authorized to order tests for this patient.")
        
        if request.method == 'POST':
            form = ExternalLabTestOfferingForm(request.POST)
            if form.is_valid():
                # Get selected tests and recommended lab
                test_ids = request.POST.getlist('tests')
                recommended_lab_id = request.POST.get('recommended_lab')
                
            if not test_ids:
                messages.error(request, 'Please select at least one test.')
                return redirect('labs:order_tests', patient_id=patient_id)
            
            # Create the lab order
            lab_order = LabOrder.objects.create(
                patient=patient,
                doctor=doctor,
                status='PENDING_PATIENT_CHOICE'
            )
            
            # Add selected tests
            tests = TestDefinition.objects.filter(id__in=test_ids)
            for test in tests:
                LabOrderTest.objects.create(
                    order=lab_order,
                    test=test,
                    price=0  # Price will be set when lab is chosen
                )
            
            # Add doctor's lab recommendation if provided
            if recommended_lab_id:
                recommended_lab = get_object_or_404(LabProfile, id=recommended_lab_id, is_approved=True)
                lab_order.doctor_recommendation = recommended_lab
                lab_order.save()
            
            messages.success(request, 'Lab tests ordered successfully. Patient will be notified to choose a lab.')
            return redirect('users:patient_detail', patient_id=patient_id)
        
        # GET request - show available tests and labs
        # Group tests by category
        from collections import defaultdict
        
        available_tests = TestDefinition.objects.all().order_by('category', 'name')
        approved_labs = LabProfile.objects.filter(is_approved=True)
        
        # Group tests by category
        tests_by_category = defaultdict(list)
        for test in available_tests:
            category = test.category or 'Uncategorized'
            tests_by_category[category].append(test)
        
        # Convert to sorted list of tuples
        categorized_tests = sorted(tests_by_category.items())
        
        # Get all unique categories for filter dropdown
        all_categories = available_tests.values_list('category', flat=True).distinct()
        categories = [cat for cat in all_categories if cat] + ['Uncategorized']
        
        # Create a simple test_prices dictionary for template compatibility
        # Since this is doctor ordering for patients, we don't need specific lab pricing yet
        test_prices = {}
        for test in available_tests:
            test_prices[test.id] = {
                'price': 0,  # Will be determined when lab is chosen
                'turnaround_time': 24,  # Default 24 hours
                'home_collection': False  # Default no home collection
            }
        
        context = {
            'patient': patient,
            'available_tests': available_tests,
            'categorized_tests': categorized_tests,
            'approved_labs': approved_labs,
            'categories': categories,
            'test_prices': test_prices,
            'current_search': '',
            'current_category': ''
        }
        
        return render(request, 'labs/order_tests.html', context)
        
    except Doctor.DoesNotExist:
        raise PermissionDenied("You must be a doctor to order lab tests.")
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found.')
        return redirect('users:patients_list')
    except Exception as e:
        messages.error(request, f'Error ordering tests: {str(e)}')
        return redirect('users:patient_detail', patient_id=patient_id)

@login_required
def patient_choose_lab(request, order_id):
    # Get the order and verify it belongs to the logged-in patient
    order = get_object_or_404(LabOrder, id=order_id, patient=request.user.patient)
    
    if order.status != 'PENDING_PATIENT_CHOICE':
        messages.error(request, 'This order is not in the correct state for lab selection.')
        return redirect('users:patient_dashboard')
    
    # Get all tests in the order
    order_tests = order.tests.all()
    test_ids = [test.id for test in order_tests]
    
    # Find labs that offer all required tests
    available_labs = LabProfile.objects.filter(
        is_approved=True,
        test_offerings__test__in=test_ids,
        test_offerings__is_active=True
    ).distinct()
    
    # Filter to only include labs that offer ALL required tests
    labs_with_all_tests = []
    for lab in available_labs:
        lab_offerings = LabTestOffering.objects.filter(
            lab=lab,
            test__in=test_ids,
            is_active=True
        )
        if lab_offerings.count() == len(test_ids):
            # Calculate total price and get other details
            total_price = sum(offering.price for offering in lab_offerings)
            max_turnaround = max(offering.turnaround_time for offering in lab_offerings)
            home_collection = all(offering.home_collection for offering in lab_offerings)
            
            labs_with_all_tests.append({
                'lab': lab,
                'total_price': total_price,
                'max_turnaround': max_turnaround,
                'home_collection': home_collection,
                'offerings': lab_offerings
            })
    
    if request.method == 'POST':
        lab_id = request.POST.get('chosen_lab')
        if not lab_id:
            messages.error(request, 'Please select a lab.')
            return redirect('labs:choose_lab', order_id=order_id)
        
        try:
            chosen_lab = LabProfile.objects.get(id=lab_id, is_approved=True)
            # Verify the lab offers all required tests
            lab_offerings = LabTestOffering.objects.filter(
                lab=chosen_lab,
                test__in=test_ids,
                is_active=True
            )
            if lab_offerings.count() != len(test_ids):
                messages.error(request, 'Selected lab does not offer all required tests.')
                return redirect('labs:choose_lab', order_id=order_id)
            
            # Update order with chosen lab and calculate total price
            order.chosen_lab = chosen_lab
            order.total_price = sum(offering.price for offering in lab_offerings)
            order.status = 'PENDING_PAYMENT'  # or 'PENDING_LAB' if no integrated payment
            order.save()
            
            messages.success(request, 'Lab selected successfully. Please proceed with payment.')
            return redirect('users:patient_dashboard')  # or payment page if integrated
            
        except LabProfile.DoesNotExist:
            messages.error(request, 'Invalid lab selection.')
            return redirect('labs:choose_lab', order_id=order_id)
    
    context = {
        'order': order,
        'order_tests': order_tests,
        'available_labs': labs_with_all_tests,
        'doctor_recommendation': order.doctor_recommendation
    }
    
    return render(request, 'labs/choose_lab.html', context)

@login_required
def view_lab_result(request, result_id):
    """
    View for doctors to securely access lab results.
    """
    # Get the result and verify doctor's access
    result = get_object_or_404(LabResult, id=result_id)
    order = result.order
    
    # Verify the requesting doctor is associated with the order
    if not request.user.is_staff and order.doctor.user != request.user:
        raise PermissionDenied("You do not have permission to view this result.")
    
    # Prepare context for the template
    context = {
        'result': result,
        'order': order,
        'patient': order.patient,
        'lab': result.uploaded_by_lab,
        'file_name': os.path.basename(result.result_file.name)
    }
    
    return render(request, 'labs/view_result.html', context)

@login_required
def download_lab_result(request, result_id):
    """
    Securely serve the lab result file.
    """
    # Get the result and verify doctor's access
    result = get_object_or_404(LabResult, id=result_id)
    order = result.order
    
    # Verify the requesting doctor is associated with the order
    if not request.user.is_staff and order.doctor.user != request.user:
        raise PermissionDenied("You do not have permission to download this result.")
    
    # Get the file path and name
    file_path = result.result_file.path
    file_name = os.path.basename(result.result_file.name)
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise Http404("Result file not found.")
    
    # Read the file and create response
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response

@login_required
def doctor_commission_dashboard(request):
    """
    View for doctors to see their commission earnings and history.
    """
    # Ensure the user is a doctor
    if not hasattr(request.user, 'doctor'):
        raise PermissionDenied("Only doctors can access this dashboard.")
    
    # Get all commission records for the doctor
    commissions = CommissionLedger.objects.filter(
        user=request.user,
        transaction_type='doctor_commission'
    ).select_related('order', 'rule_used').order_by('-created_at')
    
    # Calculate totals
    totals = commissions.aggregate(
        total_earned=Sum('amount', filter=Q(status='EARNED')),
        total_pending=Sum('amount', filter=Q(status='PENDING_PAYOUT')),
        total_paid=Sum('amount', filter=Q(status='PAID'))
    )
    
    # Replace None with 0 for any totals that didn't have matching records
    for key in totals:
        totals[key] = totals[key] or 0
    
    context = {
        'commissions': commissions,
        'totals': totals
    }
    
    return render(request, 'labs/doctor_commission_dashboard.html', context)

@login_required
def manage_tests(request):
    try:
        # For superusers, show all test offerings
        if request.user.is_superuser:
            test_offerings = ExternalLabTestOffering.objects.all().select_related('test', 'lab_profile')
            context = {
                'tests': test_offerings,
                'is_superuser': True
            }
            return render(request, 'labs/manage_tests.html', context)
        
        # For regular lab users
        lab_profile = get_lab_profile_for_user(request.user)
        if not lab_profile.is_approved:
            messages.error(request, 'Your lab account is not yet approved.')
            return redirect('labs:registration_pending')
        
        # Get filter parameters
        category_filter = request.GET.get('category', '')
        status_filter = request.GET.get('status', '')
        search_query = request.GET.get('search', '')
        
        # Get test offerings for this lab
        test_offerings = ExternalLabTestOffering.objects.filter(
            lab_profile=lab_profile
        ).select_related('test').order_by('test__category', 'test__name')
        
        # Apply filters
        if category_filter:
            test_offerings = test_offerings.filter(test__category__icontains=category_filter)
        if status_filter:
            is_active = status_filter == 'active'
            test_offerings = test_offerings.filter(is_active=is_active)
        if search_query:
            test_offerings = test_offerings.filter(
                Q(test__name__icontains=search_query) |
                Q(test__description__icontains=search_query) |
                Q(test__short_code__icontains=search_query)
            )
        
        # Get unique categories for filter dropdown
        categories = TestDefinition.objects.filter(
            offered_by_external_labs__lab_profile=lab_profile
        ).values_list('category', flat=True).distinct().order_by('category')
        categories = [cat for cat in categories if cat]  # Remove empty categories
        
        context = {
            'tests': test_offerings,
            'categories': categories,
            'current_category': category_filter,
            'current_status': status_filter,
            'current_search': search_query,
            'is_superuser': False
        }
        return render(request, 'labs/manage_tests.html', context)
    except LabProfile.DoesNotExist:
        messages.error(request, 'You must be a lab user to manage tests.')
        return redirect('labs:lab_dashboard')
    except Exception as e:
        messages.error(request, f'Error accessing test management: {str(e)}')
        return redirect('labs:lab_dashboard')

@login_required
def update_test_offering(request):
    """AJAX endpoint for updating test offering fields"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        test_id = data.get('test_id')
        
        if not test_id:
            return JsonResponse({'error': 'Test ID required'}, status=400)
        
        # Get the lab profile for the user
        lab_profile = get_lab_profile_for_user(request.user)
        
        # Get the test offering and verify ownership
        test_offering = get_object_or_404(
            ExternalLabTestOffering, 
            id=test_id, 
            lab_profile=lab_profile
        )
        
        # Update fields if provided
        if 'price' in data:
            try:
                price = float(data['price'])
                if price < 0:
                    raise ValueError("Price cannot be negative")
                test_offering.price = price
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid price value'}, status=400)
        
        if 'turnaround_time_hours' in data:
            try:
                hours = int(data['turnaround_time_hours'])
                if hours < 1:
                    raise ValueError("Turnaround time must be at least 1 hour")
                test_offering.turnaround_time_hours = hours
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid turnaround time'}, status=400)
        
        if 'offers_home_collection' in data:
            test_offering.offers_home_collection = str(data['offers_home_collection']).lower() == 'true'
        
        if 'is_active' in data:
            test_offering.is_active = str(data['is_active']).lower() == 'true'
        
        test_offering.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Test offering updated successfully'
        })
        
    except LabProfile.DoesNotExist:
        return JsonResponse({'error': 'Lab profile not found'}, status=403)
    except ExternalLabTestOffering.DoesNotExist:
        return JsonResponse({'error': 'Test offering not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error updating test offering: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)

@login_required
def delete_test_offering(request, offering_id):
    try:
        offering = get_object_or_404(ExternalLabTestOffering, id=offering_id)
        offering.delete()
        return redirect('labs:manage_tests')
    except Exception as e:
        messages.error(request, f'Error deleting test offering: {str(e)}')
        return redirect('labs:manage_tests')
    
@login_required
def edit_test_offering(request, offering_id):
    offering = get_object_or_404(ExternalLabTestOffering, id=offering_id)
    if request.method == 'POST':
        form = ExternalLabTestOfferingForm(request.POST, instance=offering)
        if form.is_valid():
            form.save()
            return redirect('labs:manage_tests')
    else:
        form = ExternalLabTestOfferingForm(instance=offering)
    return render(request, 'labs/add_edit_offering.html', {'form': form, 'title': 'Edit Test Offering'})


@login_required
def available_labs(request):
    try:
        # Get in-house labs
        inhouse_labs = Lab.objects.filter(is_active=True).values(
            'id', 'name', 'address', 'phone_number', 'email'
        )
        
        # Get external labs
        external_labs = LabProfile.objects.filter(is_approved=True).values(
            'id', 'name', 'address', 'phone_number', 'email'
        )
        
        # Combine and format the results
        labs = []
        
        # Add in-house labs
        for lab in inhouse_labs:
            labs.append({
                'id': lab['id'],
                'name': lab['name'],
                'address': lab['address'],
                'phone_number': lab['phone_number'],
                'email': lab['email'],
                'type': 'INHOUSE'
            })
        
        # Add external labs
        for lab in external_labs:
            labs.append({
                'id': lab['id'],
                'name': lab['name'],
                'address': lab['address'],
                'phone_number': lab['phone_number'],
                'email': lab['email'],
                'type': 'EXTERNAL'
            })
        
        # Check if the request is from React Native (API request)
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'labs': labs})
        
        # Default to existing HTML/HTMX response
        return render(request, 'labs/dashboard.html', {'labs': labs})
        
    except Exception as e:
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': str(e)}, status=500)
        messages.error(request, f'Error fetching labs: {str(e)}')
        return redirect('labs:dashboard')

@login_required
def bulk_upload_tests(request):
    if request.method == 'POST':
        try:
            lab_profile = get_lab_profile_for_user(request.user)
            
            if not lab_profile.is_approved:
                messages.error(request, 'Your lab account is not yet approved.')
                return redirect('labs:registration_pending')
            
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file')
                return redirect('labs:bulk_upload_tests')
            
            data = csv_file.read().decode('utf-8')
            io_string = io.StringIO(data)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            updated_count = 0
            error_count = 0
            processed_count = 0
            
            # Convert reader to list to get total count for progress
            rows = list(reader)
            total_rows = len(rows)
            
            logger.info(f"Starting bulk upload for {lab_profile.name} with {total_rows} rows")
            
            for row in rows:
                processed_count += 1
                try:
                    # Create or get test definition
                    test, test_created = TestDefinition.objects.get_or_create(
                        name=row['name'],
                        defaults={
                            'short_code': row.get('short_code', ''),
                            'description': row.get('description', ''),
                            'category': row.get('category', ''),
                            'preparation_instructions': row.get('preparation_instructions', '')
                        }
                    )
                    
                    # Parse price - handle both numeric and string formats
                    try:
                        price = float(str(row.get('price', 0)).replace(',', ''))
                    except (ValueError, TypeError):
                        price = 0
                    
                    # Parse turnaround time - handle invalid values
                    try:
                        turnaround_time = int(row.get('turnaround_time_hours', 24))
                        # Handle edge case where scraper might have set '00000'
                        if turnaround_time == 0:
                            turnaround_time = 24
                    except (ValueError, TypeError):
                        turnaround_time = 24
                    
                    # Parse boolean for home collection
                    home_collection_str = str(row.get('offers_home_collection', 'false')).lower()
                    offers_home_collection = home_collection_str in ['true', '1', 'yes', 'on']
                    
                    # Check if offering already exists for this lab and test
                    try:
                        offering = ExternalLabTestOffering.objects.get(
                            lab_profile=lab_profile,
                            test=test
                        )
                        # Update existing offering
                        offering.price = price
                        offering.turnaround_time_hours = turnaround_time
                        offering.offers_home_collection = offers_home_collection
                        offering.specific_instructions = row.get('specific_instructions', '')
                        offering.is_active = True
                        offering.save()
                        updated_count += 1
                    except ExternalLabTestOffering.DoesNotExist:
                        # Create new offering
                        offering = ExternalLabTestOffering.objects.create(
                            lab_profile=lab_profile,
                            test=test,
                            price=price,
                            turnaround_time_hours=turnaround_time,
                            offers_home_collection=offers_home_collection,
                            specific_instructions=row.get('specific_instructions', ''),
                            is_active=True
                        )
                        created_count += 1
                        
                except Exception as row_error:
                    error_count += 1
                    logger.error(f"Error processing row {processed_count}/{total_rows} ({row.get('name', 'Unknown')}): {row_error}")
                    continue
            
            # Log completion
            logger.info(f"Bulk upload completed for {lab_profile.name}: {created_count} created, {updated_count} updated, {error_count} errors")
            
            # Provide detailed feedback
            success_count = created_count + updated_count
            if success_count > 0:
                if created_count > 0 and updated_count > 0:
                    messages.success(request, f'✅ Upload completed! Created {created_count} new tests and updated {updated_count} existing tests.')
                elif created_count > 0:
                    messages.success(request, f'✅ Upload completed! Successfully created {created_count} new test offerings.')
                elif updated_count > 0:
                    messages.success(request, f'✅ Upload completed! Successfully updated {updated_count} existing test offerings.')
                    
            if error_count > 0:
                messages.warning(request, f'⚠️ {error_count} out of {total_rows} rows had errors and were skipped. Check the logs for details.')
                
            if success_count == 0:
                messages.error(request, '❌ No tests were added or updated. Please check your CSV format and try again.')
            
            return redirect('labs:lab_dashboard')
            
        except Exception as e:
            logger.error(f"Bulk upload error: {e}")
            messages.error(request, f'Error uploading tests: {str(e)}')
            return redirect('labs:bulk_upload_tests')
    
    return render(request, 'labs/bulk_upload_tests.html')

@login_required
def download_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="test_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'name',
        'short_code',
        'description',
        'category',
        'preparation_instructions',
        'price',
        'turnaround_time_hours',
        'offers_home_collection',
        'specific_instructions'
    ])
    
    # Add example rows
    writer.writerow([
        'Complete Blood Count (CBC)',
        'CBC',
        'Measures various components of blood including red blood cells, white blood cells, and platelets',
        'Hematology',
        'Fasting not required',
        '500',
        '24',
        'true',
        'Sample should be collected in EDTA tube'
    ])
    
    return response

@login_required
def orders_list(request):
    # Get the lab profile for the logged-in user
    try:
        lab_profile = get_lab_profile_for_user(request.user)
    except LabProfile.DoesNotExist:
        messages.error(request, 'You are not associated with any lab.')
        return redirect('home')
    
    # Get filter parameters
    status = request.GET.get('status', '')
    date = request.GET.get('date', '')
    
    # Start with base queryset
    orders = LabOrder.objects.filter(chosen_lab=lab_profile)
    
    # Apply filters
    if status:
        orders = orders.filter(status=status)
    if date:
        orders = orders.filter(order_date__date=date)
    
    # Order by creation date (newest first)
    orders = orders.order_by('-order_date')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(orders, 10)  # Show 10 orders per page
    
    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
    
    context = {
        'orders': orders,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': orders,
    }
    
    return render(request, 'labs/orders_list.html', context)

@login_required
def order_detail(request, order_id):
    # Get the lab profile for the logged-in user
    try:
        lab_profile = get_lab_profile_for_user(request.user)
    except LabProfile.DoesNotExist:
        messages.error(request, 'You are not associated with any lab.')
        return redirect('labs:lab_dashboard')
    
    # Get the order and verify it belongs to this lab
    order = get_object_or_404(LabOrder, id=order_id, chosen_lab=lab_profile)
    
    # Get all tests in this order
    order_tests = order.tests.all()
    
    # Get the patient's profile
    patient = order.patient
    
    # Get the doctor who ordered the tests
    doctor = order.doctor
    
    # Get the lab result if it exists
    try:
        result = LabResult.objects.get(order=order)
    except LabResult.DoesNotExist:
        result = None
    
    context = {
        'order': order,
        'order_tests': order_tests,
        'patient': patient,
        'doctor': doctor,
        'result': result,
    }
    
    return render(request, 'labs/order_detail.html', context)

@login_required
def confirm_payment(request, order_id):
    # Get the lab profile for the logged-in user
    try:
        lab_profile = get_lab_profile_for_user(request.user)
    except LabProfile.DoesNotExist:
        messages.error(request, 'You are not associated with any lab.')
        return redirect('labs:lab_dashboard')
    
    # Get the order and verify it belongs to this lab
    order = get_object_or_404(LabOrder, id=order_id, chosen_lab=lab_profile)
    
    # Verify the order is in a state where payment can be confirmed
    if order.status != 'PENDING_PAYMENT':
        messages.error(request, 'This order is not in a state where payment can be confirmed.')
        return redirect('labs:order_detail', order_id=order_id)
    
    if request.method == 'POST':
        try:
            # Update order status
            order.status = 'PENDING_SAMPLE'
            order.payment_confirmed_at = timezone.now()
            order.save()
            
            # Create commission ledger entry for the doctor
            CommissionLedger.objects.create(
                user=order.doctor.user,
                order=order,
                amount=order.total_price * 0.1,  # 10% commission
                status='PENDING_PAYOUT',
                transaction_type='doctor_commission'
            )
            
            # Send notification to patient
            send_mail(
                'Lab Test Payment Confirmed',
                f'Your payment for lab order #{order.id} has been confirmed.\n\n'
                f'Please visit {lab_profile.name} to provide your sample.\n'
                f'Address: {lab_profile.address}\n'
                f'Phone: {lab_profile.phone_number}',
                'noreply@rxdoctor.com',
                [order.patient.user.email],
                fail_silently=False,
            )
            
            messages.success(request, 'Payment confirmed successfully.')
            return redirect('labs:order_detail', order_id=order_id)
            
        except Exception as e:
            messages.error(request, f'Error confirming payment: {str(e)}')
            return redirect('labs:order_detail', order_id=order_id)
    
    context = {
        'order': order,
        'patient': order.patient,
        'doctor': order.doctor,
    }
    
    return render(request, 'labs/confirm_payment.html', context)

@login_required
def update_sample_status(request, order_id):
    # Get the lab profile for the logged-in user
    try:
        lab_profile = get_lab_profile_for_user(request.user)
    except LabProfile.DoesNotExist:
        messages.error(request, 'You are not associated with any lab.')
        return redirect('labs:lab_dashboard')
    
    # Get the order and verify it belongs to this lab
    order = get_object_or_404(LabOrder, id=order_id, chosen_lab=lab_profile)
    
    # Verify the order is in a state where sample status can be updated
    if order.status != 'PENDING_SAMPLE':
        messages.error(request, 'This order is not in a state where sample status can be updated.')
        return redirect('labs:order_detail', order_id=order_id)
    
    if request.method == 'POST':
        try:
            # Get the new status from the form
            new_status = request.POST.get('sample_status')
            
            if new_status not in ['COLLECTED', 'REJECTED']:
                messages.error(request, 'Invalid sample status.')
                return redirect('labs:order_detail', order_id=order_id)
            
            # Update order status
            order.status = 'SAMPLE_' + new_status
            order.sample_status_updated_at = timezone.now()
            order.save()
            
            # Send notification to patient
            if new_status == 'COLLECTED':
                send_mail(
                    'Lab Sample Collected',
                    f'Your sample for lab order #{order.id} has been collected.\n\n'
                    f'Results will be available soon.',
                    'noreply@rxdoctor.com',
                    [order.patient.user.email],
                    fail_silently=False,
                )
            else:  # REJECTED
                send_mail(
                    'Lab Sample Rejected',
                    f'Your sample for lab order #{order.id} has been rejected.\n\n'
                    f'Please contact the lab for more information:\n'
                    f'Phone: {lab_profile.phone_number}',
                    'noreply@rxdoctor.com',
                    [order.patient.user.email],
                    fail_silently=False,
                )
            
            messages.success(request, f'Sample status updated to {new_status}.')
            return redirect('labs:order_detail', order_id=order_id)
            
        except Exception as e:
            messages.error(request, f'Error updating sample status: {str(e)}')
            return redirect('labs:order_detail', order_id=order_id)
    
    context = {
        'order': order,
        'patient': order.patient,
    }
    
    return render(request, 'labs/update_sample_status.html', context)

@api_view(['POST'])
@login_required
def upload_result_api(request):
    try:
        # Get the lab profile for the logged-in user
        try:
            lab_profile = get_lab_profile_for_user(request.user)
        except LabProfile.DoesNotExist:
            return Response({'error': 'You are not associated with any lab'}, status=403)
        
        # Get the order ID and verify it belongs to this lab
        order_id = request.data.get('order_id')
        if not order_id:
            return Response({'error': 'Order ID is required'}, status=400)
            
        order = get_object_or_404(LabOrder, id=order_id, chosen_lab=lab_profile)
        
        # Verify the order is in a state where results can be uploaded
        if order.status != 'SAMPLE_COLLECTED':
            return Response({'error': 'This order is not in a state where results can be uploaded'}, status=400)
        
        # Get the uploaded file
        result_file = request.FILES.get('result_file')
        if not result_file:
            return Response({'error': 'Result file is required'}, status=400)
        
        # Create the lab result
        result = LabResult.objects.create(
            order=order,
            result_file=result_file,
            uploaded_by_lab=lab_profile,
            uploaded_at=timezone.now()
        )
        
        # Update order status
        order.status = 'COMPLETED'
        order.completed_at = timezone.now()
        order.save()
        
        # Update commission status
        commission = CommissionLedger.objects.get(order=order)
        commission.status = 'EARNED'
        commission.save()
        
        return Response({
            'success': True,
            'message': 'Results uploaded successfully',
            'result_id': result.id
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@login_required
def doctor_requests(request):
    # Get the lab profile for the logged-in user
    try:
        lab_profile = get_lab_profile_for_user(request.user)
    except LabProfile.DoesNotExist:
        messages.error(request, 'You are not associated with any lab.')
        return redirect('labs:lab_dashboard')
    
    # Get filter parameters
    status = request.GET.get('status', '')
    date = request.GET.get('date', '')
    
    # Get all lab test prescriptions directly linked to this lab
    prescriptions = LabTestPrescription.objects.filter(external_lab=lab_profile)
    
    # Get all lab tests from these prescriptions
    lab_tests = LabTest.objects.filter(
        prescription__in=prescriptions
    ).select_related(
        'prescription__patient',
        'prescription__doctor',
        'test_definition'
    )
    
    # Apply filters to lab tests
    if status:
        lab_tests = lab_tests.filter(status=status)
    if date:
        lab_tests = lab_tests.filter(created_at__date=date)
    
    # Get standard lab orders (from the old flow)
    lab_orders = LabOrder.objects.filter(chosen_lab=lab_profile)
    
    # Apply filters to lab orders
    if status:
        lab_orders = lab_orders.filter(status=status)
    if date:
        lab_orders = lab_orders.filter(order_date__date=date)
    
    # Combine and format results
    all_requests = []
    
    # Add lab tests
    for test in lab_tests:
        all_requests.append({
            'id': f'test_{test.id}',  # Format: test_123
            'type': 'test',
            'test_name': test.test_definition.name if test.test_definition else 'Unknown Test',
            'patient_name': test.prescription.patient.get_full_name() if getattr(test.prescription, 'patient', None) and hasattr(test.prescription.patient, 'get_full_name') else (test.prescription.patient.get_full_name() if getattr(test.prescription, 'patient', None) else str(test.prescription.patient)),
            'doctor_name': f"Dr. {test.prescription.doctor.name}" if getattr(test.prescription, 'doctor', None) and hasattr(test.prescription.doctor, 'name') else (test.prescription.doctor.get_full_name() if getattr(test.prescription, 'doctor', None) else str(test.prescription.doctor)),
            'date': test.created_at,
            'status': test.status,
            'collection_type': test.collection_type,
            'object': test,
        })
    
    # Add lab orders
    for order in lab_orders:
        all_requests.append({
            'id': f'order_{order.id}',  # Format: order_123
            'type': 'order',
            'test_name': ', '.join([test.name for test in order.tests.all()]),
            'patient_name': order.patient.get_full_name() if getattr(order, 'patient', None) and hasattr(order.patient, 'get_full_name') else (order.patient.get_full_name() if getattr(order, 'patient', None) else str(order.patient)),
            'doctor_name': f"Dr. {order.doctor.name}" if getattr(order, 'doctor', None) and hasattr(order.doctor, 'name') else (order.doctor.get_full_name() if getattr(order, 'doctor', None) else str(order.doctor)),
            'date': order.order_date,
            'status': order.status,
            'collection_type': 'N/A',
            'object': order,
        })
    
    # Sort combined results by date (newest first)
    all_requests.sort(key=lambda x: x['date'], reverse=True)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(all_requests, 10)  # Show 10 requests per page
    
    try:
        requests_page = paginator.page(page)
    except PageNotAnInteger:
        requests_page = paginator.page(1)
    except EmptyPage:
        requests_page = paginator.page(paginator.num_pages)
    
    context = {
        'requests': requests_page,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': requests_page,
        'lab_profile': lab_profile,
    }
    
    return render(request, 'labs/doctor_requests.html', context)

@login_required
def edit_lab(request, lab_id=None):
    # If lab_id is provided and user is superuser, show that lab's edit page
    if lab_id and request.user.is_superuser:
        lab_profile = get_object_or_404(LabProfile, id=lab_id)
    else:
        # Get the lab profile for the logged-in user
        try:
            lab_profile = get_lab_profile_for_user(request.user)
        except LabProfile.DoesNotExist:
            messages.error(request, 'You are not associated with any lab.')
            return redirect('labs:lab_dashboard')
    
    if request.method == 'POST':
        form = LabRegistrationForm(request.POST, instance=lab_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lab details updated successfully.')
            return redirect('labs:dashboard')
    else:
        form = LabRegistrationForm(instance=lab_profile)
    
    context = {
        'form': form,
        'lab_profile': lab_profile
    }
    
    return render(request, 'labs/edit_lab.html', context)

@login_required
def deactivate_lab(request, lab_id):
    # Only superusers can deactivate labs
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can deactivate labs.")
    
    lab_profile = get_object_or_404(LabProfile, id=lab_id)
    
    if request.method == 'POST':
        try:
            # Deactivate the lab by setting is_approved to False
            lab_profile.is_approved = False
            lab_profile.save(update_fields=['is_approved'])
            
            # Deactivate all test offerings for this lab
            LabTestOffering.objects.filter(lab_profile=lab_profile).update(is_active=False)
            
            # Send deactivation notification email
            send_mail(
                'Lab Account Deactivated',
                f'Your lab "{lab_profile.name}" has been deactivated.\n\n'
                f'You will no longer be able to receive new orders or manage your lab profile.\n\n'
                f'If you believe this is a mistake, please contact support.',
                'noreply@rxdoctor.com',
                [lab_profile.email],
                fail_silently=False,
            )
            
            messages.success(request, f'Lab {lab_profile.name} has been deactivated.')
            return redirect('labs:dashboard')
        except Exception as e:
            messages.error(request, f'Error deactivating lab: {str(e)}')
            return redirect('labs:dashboard')
    
    context = {
        'lab_profile': lab_profile
    }
    return render(request, 'labs/confirm_deactivate.html', context)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_available_labs(request):
    """
    API endpoint specifically for React Native app to fetch available labs.
    """
    try:
        # Get in-house labs
        inhouse_labs = Lab.objects.filter(is_active=True).values(
            'id', 'name', 'address', 'phone_number', 'email'
        )
        
        # Get external labs
        external_labs = LabProfile.objects.filter(is_approved=True).values(
            'id', 'name', 'address', 'phone_number', 'email'
        )
        
        # Combine and format the results
        labs = []
        
        # Add in-house labs
        for lab in inhouse_labs:
            labs.append({
                'id': lab['id'],
                'name': lab['name'],
                'address': lab['address'],
                'phone_number': lab['phone_number'],
                'email': lab['email'],
                'type': 'INHOUSE'
            })
        
        # Add external labs
        for lab in external_labs:
            labs.append({
                'id': lab['id'],
                'name': lab['name'],
                'address': lab['address'],
                'phone_number': lab['phone_number'],
                'email': lab['email'],
                'type': 'EXTERNAL'
            })
        
        return Response({
            'status': 'success',
            'labs': labs
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=500)

@login_required
def process_lab_request(request, request_id, request_type):
    """
    View for processing lab requests (both LabTest and LabOrder)
    """
    lab_profile = get_object_or_404(LabProfile, user=request.user)
    
    if request_type == 'test':
        # Handle LabTest flow
        test_id = request_id.split('_')[1]
        test = get_object_or_404(LabTest, id=test_id, prescription__external_lab=lab_profile)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'assign_technician':
                test.assigned_technician = request.POST.get('technician_name')
                test.status = 'ASSIGNED'
                test.save()
                messages.success(request, 'Technician assigned successfully')
            
            elif action == 'update_collection':
                test.status = 'SAMPLE_COLLECTED'
                test.collection_time = timezone.now()
                test.collection_notes = request.POST.get('collection_notes')
                test.save()
                messages.success(request, 'Sample collection recorded')
            
            elif action == 'start_processing':
                test.status = 'PROCESSING'
                test.processing_notes = request.POST.get('processing_notes')
                test.expected_completion_date = request.POST.get('expected_completion_date')
                test.save()
                messages.success(request, 'Test processing started')
            
            elif action == 'complete_test':
                test.status = 'COMPLETED'
                test.test_results = request.POST.get('test_results')
                if 'result_file' in request.FILES:
                    test.result_file = request.FILES['result_file']
                test.save()
                messages.success(request, 'Test completed successfully')
            
            return redirect('labs:doctor_requests')
        
        context = {
            'request_item': test,
            'type': 'test',
            'status_choices': LabTest.TEST_STATUS,
        }
        
    else:  # request_type == 'order'
        # Handle LabOrder flow
        order_id = request_id.split('_')[1]
        order = get_object_or_404(LabOrder, id=order_id, chosen_lab=lab_profile)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'confirm_payment':
                order.payment_status = 'PAID'
                order.status = 'PROCESSING'
                order.save()
                messages.success(request, 'Payment confirmed and order processing started')
            
            elif action == 'upload_result':
                # Create lab result
                result = LabResult.objects.create(
                    order=order,
                    technician_name=request.POST.get('technician_name'),
                    test_method=request.POST.get('test_method'),
                    result_file=request.FILES.get('result_file'),
                    uploaded_by_lab=lab_profile
                )
                order.status = 'COMPLETED'
                order.save()
                messages.success(request, 'Results uploaded successfully')
            
            elif action == 'update_status':
                new_status = request.POST.get('status')
                if new_status in dict(LabOrder.STATUS_CHOICES):
                    order.status = new_status
                    order.save()
                    messages.success(request, 'Status updated successfully')
            
            return redirect('labs:doctor_requests')
        
        context = {
            'request_item': order,
            'type': 'order',
            'status_choices': LabOrder.STATUS_CHOICES,
        }
    
    return render(request, 'labs/process_lab_request.html', context)

@login_required
def create_lab_user(request, lab_id):
    """Create a new user for a specific lab"""
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can create lab users.")
    
    lab_profile = get_object_or_404(LabProfile, id=lab_id)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        user_type = request.POST.get('user_type', 'LAB_STAFF')
        
        if not all([username, email, password]):
            messages.error(request, 'Username, email, and password are required.')
            return redirect('labs:create_lab_user', lab_id=lab_id)
        
        try:
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('labs:create_lab_user', lab_id=lab_id)
            
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists.')
                return redirect('labs:create_lab_user', lab_id=lab_id)
            
            # Create the user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Add to lab group
            lab_group, created = Group.objects.get_or_create(name='lab')
            user.groups.add(lab_group)
            
            # Create lab user profile
            LabUser.objects.create(
                user=user,
                lab_profile=lab_profile,
                user_type=user_type
            )
            
            messages.success(request, f'User {username} created successfully for {lab_profile.name}.')
            return redirect('labs:dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
            return redirect('labs:create_lab_user', lab_id=lab_id)
    
    return render(request, 'labs/create_lab_user.html', {
        'lab_profile': lab_profile,
        'user_types': [
            ('LAB_STAFF', 'Lab Staff'),
            ('LAB_TECHNICIAN', 'Lab Technician'),
            ('LAB_MANAGER', 'Lab Manager'),
            ('LAB_ADMIN', 'Lab Administrator'),
        ]
    })

@login_required
def manage_lab_tests(request, lab_id):
    """Manage tests for a specific lab"""
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can manage lab tests.")
    
    lab_profile = get_object_or_404(LabProfile, id=lab_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        test_id = request.POST.get('test_id')
        
        if action == 'add_test':
            test_definition_id = request.POST.get('test_definition_id')
            price = request.POST.get('price')
            turnaround_time = request.POST.get('turnaround_time')
            offers_home_collection = request.POST.get('offers_home_collection') == 'on'
            
            if not all([test_definition_id, price, turnaround_time]):
                messages.error(request, 'Test definition, price, and turnaround time are required.')
                return redirect('labs:manage_lab_tests', lab_id=lab_id)
            
            try:
                test_definition = TestDefinition.objects.get(id=test_definition_id)
                ExternalLabTestOffering.objects.create(
                    lab_profile=lab_profile,
                    test=test_definition,
                    price=Decimal(price),
                    turnaround_time_hours=int(turnaround_time),
                    offers_home_collection=offers_home_collection,
                    is_active=True
                )
                messages.success(request, f'Test {test_definition.name} added to {lab_profile.name}.')
            except Exception as e:
                messages.error(request, f'Error adding test: {str(e)}')
        
        elif action == 'remove_test':
            try:
                test_offering = ExternalLabTestOffering.objects.get(id=test_id, lab_profile=lab_profile)
                test_name = test_offering.test.name
                test_offering.delete()
                messages.success(request, f'Test {test_name} removed from {lab_profile.name}.')
            except ExternalLabTestOffering.DoesNotExist:
                messages.error(request, 'Test offering not found.')
            except Exception as e:
                messages.error(request, f'Error removing test: {str(e)}')
        
        elif action == 'toggle_test':
            try:
                test_offering = ExternalLabTestOffering.objects.get(id=test_id, lab_profile=lab_profile)
                test_offering.is_active = not test_offering.is_active
                test_offering.save()
                status = 'activated' if test_offering.is_active else 'deactivated'
                messages.success(request, f'Test {test_offering.test.name} {status}.')
            except ExternalLabTestOffering.DoesNotExist:
                messages.error(request, 'Test offering not found.')
            except Exception as e:
                messages.error(request, f'Error toggling test: {str(e)}')
        
        return redirect('labs:manage_lab_tests', lab_id=lab_id)
    
    # Get current lab tests
    lab_tests = ExternalLabTestOffering.objects.filter(lab_profile=lab_profile).select_related('test')
    
    # Get available test definitions (not already added to this lab)
    existing_test_ids = lab_tests.values_list('test_id', flat=True)
    available_tests = TestDefinition.objects.exclude(id__in=existing_test_ids)
    
    # Get lab users
    # Get main lab user (owner of lab profile)
    main_lab_user = lab_profile.user
    
    # Get additional lab users
    additional_lab_users = LabUser.objects.filter(lab_profile=lab_profile, is_active=True).select_related('user')
    
    # Combine them for display
    lab_users = []
    lab_users.append({
        'user': main_lab_user,
        'user_type': 'LAB_OWNER',
        'is_main_user': True
    })
    
    for lab_user in additional_lab_users:
        lab_users.append({
            'user': lab_user.user,
            'user_type': lab_user.user_type,
            'is_main_user': False
        })
    
    context = {
        'lab_profile': lab_profile,
        'lab_tests': lab_tests,
        'available_tests': available_tests,
        'lab_users': lab_users,
    }
    
    return render(request, 'labs/manage_lab_tests.html', context)

@login_required
def remove_lab_user(request, lab_id, user_id):
    """Remove a user from a lab"""
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can remove lab users.")
    
    lab_profile = get_object_or_404(LabProfile, id=lab_id)
    user = get_object_or_404(User, id=user_id)
    
    try:
        # Remove from lab group
        lab_group = Group.objects.get(name='lab')
        user.groups.remove(lab_group)
        
        # Remove lab user profile if exists
        try:
            lab_user = LabUser.objects.get(user=user, lab_profile=lab_profile)
            lab_user.delete()
        except LabUser.DoesNotExist:
            pass
        
        # If this was the main lab user, deactivate the lab
        if user == lab_profile.user:
            lab_profile.is_active = False
            lab_profile.save()
            messages.warning(request, f'Lab {lab_profile.name} has been deactivated as the main user was removed.')
        else:
            messages.success(request, f'User {user.username} removed from {lab_profile.name}.')
        
    except Exception as e:
        messages.error(request, f'Error removing user: {str(e)}')
    
    return redirect('labs:manage_lab_tests', lab_id=lab_id)
