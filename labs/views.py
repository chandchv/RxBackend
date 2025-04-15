from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth import get_user_model
from .forms import LabRegistrationForm, LabTestOfferingForm, ExternalLabTestOfferingForm
from .models import ExternalLabTestOffering, LabProfile, LabTestOffering, TestDefinition, LabOrder, LabOrderTest, LabResult, CommissionLedger
from users.models import Appointment, Doctor, Patient, Lab, LabTest, LabTestPrescription
from django.db.models import Q, Sum, Count
import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
import csv
import io
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.models import Group
from notifications.models import Notification

User = get_user_model()

# Create your views here.

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
        lab_profile = LabProfile.objects.get(user=request.user)
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
        ).select_related('doctor', 'test')[:5]
        
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
    """Main lab dashboard view"""
    # Get the lab profile for the logged-in user
    lab_profile = get_object_or_404(LabProfile, user=request.user)
    
    # Get statistics
    stats = {
        'total_tests': ExternalLabTestOffering.objects.filter(lab_profile=lab_profile).count(),
        'pending_orders': LabOrder.objects.filter(chosen_lab=lab_profile, status='PENDING').count(),
        'completed_orders': LabOrder.objects.filter(chosen_lab=lab_profile, status='COMPLETED').count(),
        'total_revenue': LabOrder.objects.filter(
            chosen_lab=lab_profile, 
            status='COMPLETED'
        ).aggregate(total=Sum('total_price'))['total'] or 0
    }
    
    # Get recent orders
    recent_orders = LabOrder.objects.filter(chosen_lab=lab_profile).order_by('-order_date')[:5]
    
    # Get available tests
    available_tests = ExternalLabTestOffering.objects.filter(lab_profile=lab_profile, is_active=True).order_by('test__name')[:5]
    
    # Get recent doctor requests
    recent_requests = LabOrder.objects.filter(
        chosen_lab=lab_profile,
        status='PENDING'
    ).order_by('-order_date')[:5]
    
    # Get payment statistics
    payment_stats = {
        'pending_payments': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='PENDING'
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'completed_payments': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='COMPLETED'
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'total_revenue': stats['total_revenue']
    }
    
    # Get notifications for the user
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')[:5]
    
    context = {
        'lab_profile': lab_profile,
        'stats': stats,
        'recent_orders': recent_orders,
        'available_tests': available_tests,
        'recent_requests': recent_requests,
        'payment_stats': payment_stats,
        'notifications': notifications,
        'is_superuser': request.user.is_superuser
    }
    
    return render(request, 'labs/lab_dashboard.html', context)

@login_required
def add_test_offering(request):
    # Allow both superusers and lab users to add test offerings
    if not request.user.is_superuser:
        try:
            lab_profile = LabProfile.objects.get(user=request.user)
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
                    lab_profile = LabProfile.objects.get(user=request.user)
                
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
                if 'is_custom_test' in request.POST and request.POST.get('custom_test_name'):
                    custom_test_name = request.POST.get('custom_test_name').strip()
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
        lab_profile = request.user.lab_profile
        if not lab_profile.is_approved:
            raise PermissionDenied("Your lab account is not yet approved.")
        
        offering = get_object_or_404(ExternalLabTestOffering, id=offering_id, lab_profile=lab_profile)
        
        if request.method == 'POST':
            form = LabTestOfferingForm(request.POST, instance=offering)
            if form.is_valid():
                # Don't save the form yet
                test_offering = form.save(commit=False)
                
                # Check if this is a custom test
                custom_test_name = request.POST.get('custom_test_name')
                if custom_test_name:
                    # Check if it's a valid string and not empty
                    custom_test_name = custom_test_name.strip()
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
        lab_profile = request.user.lab_profile
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
def order_lab_tests(request, patient_id):
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Verify doctor has access to this patient
        if not Appointment.objects.filter(doctor=doctor, patient=patient).exists():
            raise PermissionDenied("You are not authorized to order tests for this patient.")
        
        if request.method == 'POST':
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
        available_tests = TestDefinition.objects.all()
        approved_labs = LabProfile.objects.filter(is_approved=True)
        
        context = {
            'patient': patient,
            'available_tests': available_tests,
            'approved_labs': approved_labs
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
        lab_profile = LabProfile.objects.get(user=request.user)
        if not lab_profile.is_approved:
            messages.error(request, 'Your lab account is not yet approved.')
            return redirect('labs:registration_pending')
        
        # Get test offerings for this lab
        test_offerings = ExternalLabTestOffering.objects.filter(
            lab_profile=lab_profile
        ).select_related('test')
        
        context = {
            'tests': test_offerings,
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


@api_view(['GET'])
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
        
        return Response({'labs': labs})
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@login_required
def bulk_upload_tests(request):
    if request.method == 'POST':
        try:
            lab_profile = LabProfile.objects.get(user=request.user)
            lab = Lab.objects.get(profile=lab_profile)
            
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file')
                return redirect('labs:dashboard')
            
            data = csv_file.read().decode('utf-8')
            io_string = io.StringIO(data)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            for row in reader:
                # Create or get test definition
                test, created = TestDefinition.objects.get_or_create(
                    name=row['name'],
                    defaults={
                        'short_code': row.get('short_code', ''),
                        'description': row.get('description', ''),
                        'category': row.get('category', ''),
                        'preparation_instructions': row.get('preparation_instructions', '')
                    }
                )
                
                # Create test offering for the lab
                offering, created = ExternalLabTestOffering.objects.get_or_create(
                    lab_profile=lab_profile,
                    test=test,
                    defaults={
                        'price': row.get('price', 0),
                        'turnaround_time_hours': row.get('turnaround_time_hours', 24),
                        'offers_home_collection': row.get('offers_home_collection', 'False').lower() == 'true',
                        'specific_instructions': row.get('specific_instructions', ''),
                        'is_active': True
                    }
                )
                
                if created:
                    created_count += 1
            
            messages.success(request, f'Successfully uploaded {created_count} test offerings')
            return redirect('labs:dashboard')
            
        except Exception as e:
            messages.error(request, f'Error uploading tests: {str(e)}')
            return redirect('labs:dashboard')
    
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
        lab_profile = LabProfile.objects.get(user=request.user)
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
    lab_profile = get_object_or_404(LabProfile, user=request.user)
    
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
    lab_profile = get_object_or_404(LabProfile, user=request.user)
    
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
    lab_profile = get_object_or_404(LabProfile, user=request.user)
    
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
        lab_profile = get_object_or_404(LabProfile, user=request.user)
        
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
    lab_profile = get_object_or_404(LabProfile, user=request.user)
    
    # Print out key information for debugging
    print(f"SIMPLIFIED DEBUG: Processing doctor_requests for lab profile: {lab_profile.name} (ID: {lab_profile.id})")
    
    # Check for force create parameter - this will always create a test for debugging
    force_create = request.GET.get('force_create', 'false') == 'true'
    
    if force_create:
        # Import all necessary models correctly
        from users.models import LabTest, LabTestPrescription, Patient
        from labs.models import TestDefinition
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Find any doctor in the system to assign as creator
        doctor = User.objects.filter(is_active=True).first()
        
        # Find any patient in the system
        patient = Patient.objects.first()
        
        # Create a test definition if needed
        test_def, created = TestDefinition.objects.get_or_create(
            name="EMERGENCY TEST", 
            defaults={
                'description': 'This is a test created for debugging purposes'
            }
        )
        
        # Create a new lab test prescription
        try:
            prescription = LabTestPrescription.objects.create(
                doctor=doctor,
                patient=patient,
                notes="Force created test prescription",
                preferred_lab_type='EXTERNAL',
                external_lab=lab_profile  # This is the key relationship
            )
            
            # Create a lab test linked to this prescription
            lab_test = LabTest.objects.create(
                prescription=prescription,
                test_definition=test_def,
                status='REQUESTED',
                collection_type='IN_CLINIC',
                doctor_notes="Force created test - please process"
            )
            
            messages.success(request, f"Created emergency test successfully! Test ID: {lab_test.id}")
            print(f"SIMPLIFIED DEBUG: Created emergency test with ID {lab_test.id}")
        except Exception as e:
            messages.error(request, f"Error creating test: {str(e)}")
            print(f"SIMPLIFIED DEBUG: Error creating test: {e}")
    
    # Get all lab test prescriptions directly linked to this lab
    from users.models import LabTestPrescription, LabTest
    
    # Method 1: Get lab tests via direct relationship
    direct_prescriptions = LabTestPrescription.objects.filter(external_lab=lab_profile)
    print(f"SIMPLIFIED DEBUG: Found {direct_prescriptions.count()} prescriptions directly linked to lab")
    
    # Get all lab tests from these prescriptions
    test_ids = []
    for p in direct_prescriptions:
        tests = LabTest.objects.filter(prescription=p)
        test_ids.extend([t.id for t in tests])
        print(f"SIMPLIFIED DEBUG: Prescription {p.id} has {tests.count()} tests")
    
    # Get the actual lab test objects
    lab_test_requests = LabTest.objects.filter(id__in=test_ids).select_related(
        'prescription', 
        'prescription__patient', 
        'prescription__doctor', 
        'test_definition'
    )
    
    print(f"SIMPLIFIED DEBUG: Final test count: {lab_test_requests.count()}")
    
    # Also get standard lab orders (from the old flow)
    lab_orders = LabOrder.objects.filter(chosen_lab=lab_profile)
    print(f"SIMPLIFIED DEBUG: Found {lab_orders.count()} lab orders from old flow")
    
    # Combine and paginate results
    all_requests = []
    for test in lab_test_requests:
        try:
            test_name = test.test_definition.name if test.test_definition else 'Unknown Test'
            patient_name = test.prescription.patient.get_full_name() if test.prescription and test.prescription.patient else 'Unknown Patient'
            doctor_name = "Dr. " + (test.prescription.doctor.get_full_name() if hasattr(test.prescription.doctor, 'get_full_name') else test.prescription.doctor.username) if test.prescription and test.prescription.doctor else 'Unknown Doctor'
            
            all_requests.append({
                'id': f'test_{test.id}',
                'type': 'test',
                'test_name': test_name,
                'patient_name': patient_name,
                'doctor_name': doctor_name,
                'date': test.prescription.prescription_date if test.prescription else timezone.now(),
                'status': test.status,
                'collection_type': test.collection_type,
                'object': test,
            })
            print(f"SIMPLIFIED DEBUG: Added test {test.id} ({test_name}) to results")
        except Exception as e:
            print(f"SIMPLIFIED DEBUG: Error adding test to results: {e}")
    
    for order in lab_orders:
        try:
            all_requests.append({
                'id': f'order_{order.id}',
                'type': 'order',
                'test_name': ', '.join([test.name for test in order.tests.all()]),
                'patient_name': order.patient.get_full_name() if order.patient else 'Unknown Patient',
                'doctor_name': order.doctor.name if order.doctor else 'Unknown Doctor',
                'date': order.order_date,
                'status': order.status,
                'collection_type': 'N/A',
                'object': order,
            })
        except Exception as e:
            print(f"SIMPLIFIED DEBUG: Error adding order to results: {e}")
    
    print(f"SIMPLIFIED DEBUG: Total requests to display: {len(all_requests)}")
    
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
        lab_profile = get_object_or_404(LabProfile, user=request.user)
    
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

