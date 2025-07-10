import json
import logging
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import ValidationError, ObjectDoesNotExist


# Assuming these are your models and forms/formsets
from ..models import Prescription, Doctor, Patient, PrescriptionItem, PatientVitals, Lab, LabTest, LabTestPrescription
from labs.models import LabProfile, ExternalLabTestOffering, TestDefinition
from users.models import User
from ..forms import (
    VitalsForm, PrescriptionForm, BasePrescriptionItemFormSet, BaseLabTestFormSet
)
# Assuming you have a notification utility function
from notifications.utils import User, create_notification # Adjust import path
from users.models import Appointment, AppointmentSlot # Added for follow-up appointment

# --- Constants ---
VITALS_FORM_PREFIX = 'vitals'
PRESCRIPTION_FORM_PREFIX = 'prescription'
ITEM_FORMSET_PREFIX = 'items'
LAB_FORMSET_PREFIX = 'labs'
LAB_TYPE_INTERNAL = 'internal'
LAB_TYPE_EXTERNAL = 'external'

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _save_vitals(form: VitalsForm, patient: Patient, user: User) -> Optional[PatientVitals]:
    """Saves patient vitals if the form contains data."""
    if form.is_valid() and any(form.cleaned_data.values()):
        try:
            vitals = form.save(commit=False)
            vitals.patient = patient
            vitals.recorded_by = user
            vitals.save()
            logger.info(f"Saved vitals {vitals.id} for patient {patient.id}")
            return vitals
        except (ValidationError, IntegrityError) as e:
            logger.error(f"Error saving vitals for patient {patient.id}: {e}", exc_info=True)
            # Re-raise to be caught by the main transaction handler if needed,
            # or handle more specifically if vitals failure shouldn't stop prescription
            raise ValueError(f"Failed to save vitals: {str(e)}") from e
    else:
        logger.info(f"No vitals entered or form invalid for patient {patient.id}, skipping save.")
        return None

def _save_prescription_items(formset: BasePrescriptionItemFormSet, prescription: Prescription): # type: ignore
    """Saves prescription items from the formset."""
    if formset.is_valid():
        items = formset.save(commit=False)
        saved_items = []
        for item in items:
            item.prescription = prescription
            item.save()
            saved_items.append(item)

        # Handle deleted items
        for form in formset.deleted_forms:
            if form.instance.pk: # Check if it's an existing item being deleted
                try:
                    form.instance.delete()
                    logger.info(f"Deleted PrescriptionItem {form.instance.pk} for prescription {prescription.id}")
                except Exception as e: # Catch potential deletion errors
                    logger.error(f"Error deleting PrescriptionItem {form.instance.pk}: {e}")
                    # Decide if this error should halt the process or just be logged

        # formset.save_m2m() # Uncomment if M2M relations exist on the item form

        logger.info(f"Saved/updated {len(saved_items)} items for prescription {prescription.id}")
    else:
        # This case is handled by the main validation check, but logging here can be useful
        logger.warning(f"Prescription item formset invalid for prescription {prescription.id}. Errors: {formset.errors}")
        raise ValueError("Invalid prescription item data.") # Ensure transaction rollback

def _process_and_save_lab_tests(
    formset: BaseLabTestFormSet, # type: ignore
    patient: Patient,
    doctor: Doctor, # Changed from request.user for clarity, assuming Doctor has user link
    request  # Keep request for messages
) -> Tuple[Optional[LabTestPrescription], List[Dict[str, Any]]]:
    """Processes lab test formset, creates LabTestPrescription and LabTests."""
    if not formset.is_valid() or not formset.has_changed():
        logger.info(f"Lab formset invalid or unchanged for patient {patient.id}. Skipping lab processing.")
        return None, []

    lab_prescription = None
    processed_labs_info = [] # Stores dicts {'lab_test': LabTest, 'lab_type': str, 'lab_pk': int, 'lab_name': str}
    external_lab_profile_to_set = None

    # Create LabTestPrescription only if there are valid labs to add
    # We defer creation until we know at least one lab test is valid
    for form in formset:
         # Check if form has data, is valid and not marked for deletion
        if form.is_valid() and form.has_changed() and not form.cleaned_data.get('DELETE'):
            if not lab_prescription: # Create prescription on the first valid lab form
                lab_prescription = LabTestPrescription.objects.create(
                    doctor=doctor.user, # Assuming doctor model has a 'user' FK
                    patient=patient,
                    # notes="", # Consider adding notes field to LabTestPrescriptionForm/Model
                    preferred_lab_type='PATIENT_CHOICE' # Or get from form if needed
                )
                logger.info(f"Created LabTestPrescription {lab_prescription.id} for patient {patient.id}")

            lab_data = form.cleaned_data
            combined_lab_id = lab_data.get('lab_id')
            test_name = lab_data.get('test_name')

            if not combined_lab_id or not test_name:
                 logger.warning(f"Skipping lab form due to missing lab_id or test_name. Data: {lab_data}")
                 continue # Skip this form if essential data is missing

            # --- Parse Lab ID ---
            lab_type = None
            lab_pk = None
            
            if combined_lab_id and combined_lab_id != 'external':
                try:
                    # Handle potential duplicate prefixes
                    parts = combined_lab_id.split('-')
                    if len(parts) >= 2:
                        lab_type = parts[0]  # Take first part as type
                        lab_pk_str = parts[-1]  # Take last part as ID
                        if lab_type not in [LAB_TYPE_INTERNAL, LAB_TYPE_EXTERNAL]:
                            raise ValueError(f"Invalid lab type '{lab_type}'")
                        lab_pk = int(lab_pk_str)
                    else:
                        raise ValueError(f"Invalid lab identifier format: {combined_lab_id}")
                except (ValueError, TypeError) as e:
                    msg = f"Invalid lab identifier format ('{combined_lab_id}') for test '{test_name}'. Please re-select the lab."
                    messages.error(request, msg)
                    logger.error(f"{msg} Error: {e}")
                    raise ValueError("Invalid lab identifier format.") from e # Critical error, rollback

            # --- Get Lab and Test Definition ---
            test_definition = None
            lab_display_name = "External Lab (Not Associated)"
            lab_obj_for_notification = None # Store the Lab or LabProfile object

            try:
                if lab_type == LAB_TYPE_INTERNAL:
                    lab = get_object_or_404(Lab, pk=lab_pk, clinic=doctor.clinic) # Ensure lab belongs to doctor's clinic
                    lab_display_name = lab.name
                    lab_obj_for_notification = lab
                    test_definition = lab.test_definitions.filter(name=test_name).first()
                    if not test_definition:
                        # Instead of raising an error, create a generic test definition
                        test_definition, created = TestDefinition.objects.get_or_create(name=test_name)
                        logger.warning(f"Test '{test_name}' not found in internal lab '{lab.name}'. Created generic test definition.")

                elif lab_type == LAB_TYPE_EXTERNAL:
                    lab_profile = get_object_or_404(LabProfile, pk=lab_pk, is_approved=True)
                    lab_display_name = lab_profile.name
                    lab_obj_for_notification = lab_profile
                    # Efficiently find the offering and related test definition
                    test_offering = ExternalLabTestOffering.objects.select_related('test').filter(
                        lab_profile=lab_profile,
                        test__name=test_name,
                        is_active=True
                    ).first()
                    if not test_offering:
                        # Instead of raising an error, create a generic test definition
                        test_definition, created = TestDefinition.objects.get_or_create(name=test_name)
                        logger.warning(f"Test '{test_name}' not found in external lab '{lab_profile.name}'. Created generic test definition.")
                    else:
                        test_definition = test_offering.test
                    # Mark the external lab to be set on the prescription later
                    # (handle multiple different external labs if necessary - current logic uses last one)
                    external_lab_profile_to_set = lab_profile
                
                else:
                    # No specific lab selected or external lab option chosen
                    # Create or get a generic test definition
                    test_definition, created = TestDefinition.objects.get_or_create(name=test_name)
                    if created:
                        logger.info(f"Created new test definition for '{test_name}' (no specific lab selected)")
                    else:
                        logger.info(f"Using existing test definition for '{test_name}' (no specific lab selected)")

                # --- Create LabTest Object ---
                lab_test = LabTest.objects.create(
                    prescription=lab_prescription,
                    test_definition=test_definition,
                    status='REQUESTED',
                    collection_type=lab_data.get('collection_type', 'CLINIC'), # Provide default
                    doctor_notes=lab_data.get('description', '')
                )
                processed_labs_info.append({
                    'lab_test': lab_test,
                    'lab_type': lab_type,
                    'lab_pk': lab_pk,
                    'lab_name': lab_display_name,
                    'lab_object': lab_obj_for_notification # Pass the actual lab/profile object
                })
                logger.info(f"Saved LabTest for '{test_name}' (Lab: {lab_display_name}) for LabTestPrescription {lab_prescription.id}")

            except ObjectDoesNotExist as e:
                messages.error(request, str(e))
                logger.error(f"Error finding lab/test for patient {patient.id}: {e}")
                raise ValueError(f"Lab/Test lookup failed: {str(e)}") from e # Critical error, rollback
            except (ValidationError, IntegrityError) as e:
                msg = f"Error saving lab test '{test_name}' for {lab_display_name}: {str(e)}"
                messages.error(request, msg)
                logger.error(msg, exc_info=True)
                raise ValueError(msg) from e # Critical error, rollback
            except Exception as e: # Catch unexpected errors during processing a single lab
                msg = f"An unexpected error occurred while processing lab test '{test_name}' for {lab_display_name}."
                messages.error(request, msg)
                logger.error(f"{msg} Error: {e}", exc_info=True)
                raise e # Re-raise to trigger transaction rollback

    # Update the LabTestPrescription with the external lab if one was processed
    if lab_prescription and external_lab_profile_to_set:
        lab_prescription.external_lab = external_lab_profile_to_set
        lab_prescription.save(update_fields=['external_lab'])
        logger.info(f"Set external lab {external_lab_profile_to_set.name} for LabTestPrescription {lab_prescription.id}")

    # Handle deleted lab forms (if using can_delete=True in formset)
    for form in formset.deleted_forms:
        if form.instance.pk:
            try:
                # You might need custom logic here if deleting a LabTest form means
                # deleting the corresponding LabTest instance.
                # form.instance.delete() # Example: if formset maps directly to LabTest
                logger.info(f"Processing deletion request for lab form instance {form.instance.pk}")
                # Implement actual deletion logic if needed
            except Exception as e:
                logger.error(f"Error processing deletion for lab form instance {form.instance.pk}: {e}")

    return lab_prescription, processed_labs_info


def _send_notifications(
    request: Any, # HttpRequest
    prescription: Prescription,
    lab_prescription: Optional[LabTestPrescription],
    processed_labs_info: List[Dict[str, Any]],
    patient: Patient,
    doctor: Doctor
):
    """Sends notifications to patient and relevant labs."""
    sender = request.user

    # --- Notify Patient ---
    try:
        if patient.user:
            create_notification(
                recipient=patient.user,
                message=f"Dr. {doctor.name} has created a new prescription for you. View in portal",
                sender=sender,
                notification_type='prescription_new',
                related_object=prescription,
                action_url=reverse('users:prescription_detail_view', kwargs={'pk': prescription.id})
            )
            logger.info(f"Sent patient notification for prescription {prescription.id}")
        else:
            logger.warning(f"Patient {patient.id} has no associated user account. Skipping notification.")
    except Exception as e:
        logger.error(f"Error creating patient prescription notification for {prescription.id}: {e}", exc_info=True)
        messages.warning(request, "Prescription saved, but failed to send patient notification.")

    # --- Notify Labs ---
    if lab_prescription and processed_labs_info:
        notified_labs = set()
        for lab_info in processed_labs_info:
            # Create a unique key for each lab
            lab_key = f"{lab_info['lab_type']}-{lab_info['lab_pk']}"
            if lab_key in notified_labs:
                continue

            # Define message detail based on lab type
            message_detail = f"New lab test request for {patient.get_full_name()}"
            
            try:
                # Get clinic staff to notify - using the correct model relationships
                clinic_recipients = User.objects.filter(
                    labstaff__lab__clinic=doctor.clinic,
                    groups__name='lab'
                ).distinct()

                if clinic_recipients.exists():
                    for recipient in clinic_recipients:
                        if recipient:
                            try:
                                create_notification(
                                    recipient=recipient,
                                    message=f"{message_detail} for internal lab {lab_info['lab_name']}. Collection type: {lab_info['lab_test'].get_collection_type_display()}. {lab_info['lab_test'].doctor_notes or ''}",
                                    sender=sender,
                                    notification_type='lab_test_new',
                                    related_object=lab_prescription,
                                    action_url=f"/labs/test/{lab_prescription.id}/"
                                )
                                logger.info(f"Sent notification to lab staff {recipient.username} for lab {lab_info['lab_name']}")
                            except Exception as e:
                                logger.error(f"Error sending notification to lab staff {recipient.username}: {e}", exc_info=True)
                                messages.warning(request, f"Failed to send notification to lab staff for {lab_info['lab_name']}")
                    
                    notified_labs.add(lab_key)
                    logger.info(f"Successfully sent notifications to {clinic_recipients.count()} internal lab staff for {lab_info['lab_name']}")
                else:
                    logger.warning(f"No lab staff found for clinic {doctor.clinic.id} to notify for lab {lab_info['lab_name']}.")
            except Exception as e:
                logger.error(f"Error finding lab staff for clinic {doctor.clinic.id}: {e}", exc_info=True)
                messages.warning(request, "Failed to find lab staff to notify.")

def _create_followup_appointment(prescription: Prescription, doctor: Doctor, patient: Patient, request, selected_time: str = None) -> Optional[Appointment]:
    """
    Creates a follow-up appointment based on the prescription's follow-up date.
    Returns the created appointment or None if creation fails.
    """
    if not prescription.follow_up_date:
        return None
    
    try:
        appointment_time = None
        available_slots = None
        
        if selected_time:
            # Use the selected time if provided
            try:
                appointment_time = datetime.strptime(selected_time, '%H:%M').time()
                # Check if the selected time slot is available
                available_slots = AppointmentSlot.objects.filter(
                    doctor=doctor,
                    date=prescription.follow_up_date,
                    start_time=appointment_time,
                    is_booked=False
                ).first()
                
                if not available_slots:
                    logger.warning(f"Selected time slot {selected_time} is not available for follow-up date {prescription.follow_up_date}. Will try to find another slot.")
                    appointment_time = None
            except ValueError:
                logger.error(f"Invalid time format: {selected_time}")
                appointment_time = None
        
        if not appointment_time:
            # Get first available slot for the follow-up date
            available_slots = AppointmentSlot.objects.filter(
                doctor=doctor,
                date=prescription.follow_up_date,
                is_booked=False
            ).order_by('start_time').first()
            
            if not available_slots:
                # If no slots available, create a default appointment time (9 AM)
                appointment_time = datetime.strptime('09:00', '%H:%M').time()
                logger.warning(f"No available slots found for follow-up date {prescription.follow_up_date}. Using default time 9:00 AM.")
            else:
                appointment_time = available_slots.start_time
        
        # Create the follow-up appointment
        try:
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                appointment_date=prescription.follow_up_date,
                appointment_time=appointment_time,
                reason=f"Follow-up appointment for prescription #{prescription.id}",
                status='scheduled',
                is_telemedicine=False,
                is_emergency=False,
                is_walk_in=False
            )
        except Exception as e:
            logger.error(f"Error creating appointment object: {e}", exc_info=True)
            raise
        
        # Mark the slot as booked if we used an existing slot
        if available_slots:
            available_slots.is_booked = True
            available_slots.save()
            logger.info(f"Marked slot {available_slots.id} as booked for appointment {appointment.id}")
        
        logger.info(f"Created follow-up appointment {appointment.id} for prescription {prescription.id} at {appointment_time}")
        
        # Send notification to patient about the follow-up appointment
        if patient.user:
            try:
                create_notification(
                    recipient=patient.user,
                    message=f"Follow-up appointment scheduled for {prescription.follow_up_date.strftime('%B %d, %Y')} at {appointment_time.strftime('%I:%M %p')}",
                    sender=request.user,
                    notification_type='appointment_scheduled',
                    related_object=appointment,
                    action_url=reverse('users:appointment_detail', kwargs={'pk': appointment.id})
                )
                logger.info(f"Sent follow-up appointment notification to patient {patient.id}")
            except Exception as e:
                logger.error(f"Error sending follow-up appointment notification: {e}", exc_info=True)
        
        return appointment
        
    except Exception as e:
        logger.error(f"Error creating follow-up appointment for prescription {prescription.id}: {e}", exc_info=True)
        return None

# --- Main View ---

@login_required
@transaction.atomic # Wrap in transaction to ensure atomicity
def create_prescription(request, patient_id):
    """
    Handles the creation of a prescription, including optional vitals,
    medication items, and lab test requests.
    """
    patient = get_object_or_404(Patient, id=patient_id)
    # Ensure the request user is linked to a Doctor profile
    try:
        doctor = Doctor.objects.select_related('user', 'clinic').get(user=request.user)
    except Doctor.DoesNotExist:
        messages.error(request, "Your user account is not associated with a doctor profile.")
        # Redirect to a relevant page, e.g., dashboard or profile setup
        return redirect('some_default_view_name') # Replace with appropriate URL name

    latest_vitals = PatientVitals.objects.filter(patient=patient).order_by('-created_at').first()

    if request.method == 'POST':
        vitals_form = VitalsForm(request.POST, prefix=VITALS_FORM_PREFIX)
        prescription_form = PrescriptionForm(request.POST, prefix=PRESCRIPTION_FORM_PREFIX)
        item_formset = BasePrescriptionItemFormSet(request.POST, prefix=ITEM_FORMSET_PREFIX)
        lab_formset = BaseLabTestFormSet(request.POST, prefix=LAB_FORMSET_PREFIX)

        # Validate all forms initially
        forms_are_valid = all([
            vitals_form.is_valid(), # is_valid() even if empty, checks field formats
            prescription_form.is_valid(),
            item_formset.is_valid(),
            lab_formset.is_valid() # is_valid() allows empty forms in formset
        ])

        if forms_are_valid:
            try:
                # --- Save Vitals (Optional) ---
                # Note: _save_vitals handles the check for actual data presence
                saved_vitals = _save_vitals(vitals_form, patient, request.user)

                # --- Save Prescription ---
                prescription = prescription_form.save(commit=False)
                prescription.patient = patient
                prescription.doctor = doctor
                # prescription.date = timezone.now() # Usually handled by auto_now_add=True on model field
                prescription.save()
                logger.info(f"Saved prescription {prescription.id} for patient {patient_id} by doctor {doctor.id}")

                # --- Save Prescription Items ---
                _save_prescription_items(item_formset, prescription)

                # --- Process and Save Lab Tests ---
                lab_prescription, processed_labs_info = _process_and_save_lab_tests(
                    lab_formset, patient, doctor, request
                )

                # --- Create Follow-up Appointment (if follow-up date is set) ---
                followup_appointment = None
                if prescription.follow_up_date:
                    # Get selected time from request
                    selected_time = request.POST.get('selected_followup_time')
                    followup_appointment = _create_followup_appointment(prescription, doctor, patient, request, selected_time)
                    if followup_appointment:
                        messages.success(request, f'Follow-up appointment scheduled for {prescription.follow_up_date.strftime("%B %d, %Y")} at {followup_appointment.appointment_time.strftime("%I:%M %p")}.')
                    else:
                        messages.warning(request, 'Prescription saved, but failed to schedule follow-up appointment. Please schedule it manually.')

                # --- Send Notifications (After successful save) ---
                # This runs outside the main saving logic failure path, but inside the transaction
                _send_notifications(request, prescription, lab_prescription, processed_labs_info, patient, doctor)

                messages.success(request, 'Prescription created successfully.')
                # Redirect to detail view upon successful creation
                return redirect('users:prescription_detail', pk=prescription.id) # Adjust URL name

            except (ValueError, IntegrityError, ObjectDoesNotExist, ValidationError) as e:
                # Catch specific errors raised by helper functions that require rollback
                logger.error(f"Validation or Database error during prescription creation for patient {patient_id}: {e}", exc_info=True)
                # Message might have already been set in helper, or set a generic one here
                if not messages.get_messages(request):
                    messages.error(request, f'An error occurred: {str(e)}. Please review the form and try again.')
                # Transaction automatically rolls back here due to the exception

            except Exception as e:
                # Catch unexpected errors
                logger.critical(f"Unexpected error during prescription creation process for patient {patient_id}: {e}", exc_info=True)
                messages.error(request, 'An unexpected error occurred. Please try again later or contact support.')
                # Transaction automatically rolls back

            # If we reach here after an exception, it means the transaction rolled back.
            # Re-render the form with errors below (outside the try/except)

        else: # Forms are not valid (initial validation failed)
            logger.warning(f"Prescription form validation failed for patient {patient_id}. Errors below.")
            # Log detailed errors for debugging
            if vitals_form.errors: logger.warning(f"Vitals Form Errors: {vitals_form.errors.as_json()}")
            if prescription_form.errors: logger.warning(f"Prescription Form Errors: {prescription_form.errors.as_json()}")
            if item_formset.errors: logger.warning(f"Item Formset Errors: {item_formset.errors}") # Formset errors structure is different
            if item_formset.non_form_errors(): logger.warning(f"Item Formset Non-Form Errors: {item_formset.non_form_errors().as_json()}")
            if lab_formset.errors: logger.warning(f"Lab Formset Errors: {lab_formset.errors}")
            if lab_formset.non_form_errors(): logger.warning(f"Lab Formset Non-Form Errors: {lab_formset.non_form_errors().as_json()}")

            messages.error(request, 'Please correct the errors highlighted below.')
            # Fall through to render the template with invalid forms

    else: # GET request
        vitals_form = VitalsForm(prefix=VITALS_FORM_PREFIX, instance=latest_vitals) # Pre-fill vitals if available
        prescription_form = PrescriptionForm(prefix=PRESCRIPTION_FORM_PREFIX)
        item_formset = BasePrescriptionItemFormSet(prefix=ITEM_FORMSET_PREFIX)
        lab_formset = BaseLabTestFormSet(prefix=LAB_FORMSET_PREFIX)

    # --- Prepare Context (for GET and POST-error re-render) ---
    available_labs_json = "[]"
    has_lab = False
    if doctor.clinic: # Check if doctor is associated with a clinic
        internal_labs = Lab.objects.filter(clinic=doctor.clinic).values('id', 'name')
        external_labs = LabProfile.objects.filter(is_approved=True).values('id', 'name')

        combined_labs_list = [
            {'id': f'{LAB_TYPE_INTERNAL}-{lab["id"]}', 'name': f"{lab['name']} (Internal)", 'type': LAB_TYPE_INTERNAL}
            for lab in internal_labs
        ] + [
            {'id': f'{LAB_TYPE_EXTERNAL}-{lab["id"]}', 'name': f"{lab['name']} (External)", 'type': LAB_TYPE_EXTERNAL}
            for lab in external_labs
        ]
        available_labs_json = json.dumps(combined_labs_list)
        has_lab = bool(combined_labs_list)
    else:
        logger.warning(f"Doctor {doctor.id} has no clinic associated, cannot fetch labs.")


    context = {
        'patient': patient,
        'doctor': doctor,
        'vitals_form': vitals_form,
        'prescription_form': prescription_form,
        'item_formset': item_formset,
        'lab_formset': lab_formset,
        'available_labs_json': available_labs_json, # Pass combined labs as JSON
        'has_lab': has_lab,
    }
    return render(request, 'doctor/create_prescription.html', context) # Adjust template path