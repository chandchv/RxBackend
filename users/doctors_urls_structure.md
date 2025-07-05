# RxDoctor URL Structure

This document describes the organization of URLs in the RxDoctor application.

## Main URL Groups

### Authentication URLs
- `/login/`, `/signup/`, `/logout/`, `/profile/`
- `/auth/google/` - Google authentication
- `/accounts/` - Django allauth integration

### Doctor URLs
All under `/doctor/` prefix:
- `/doctor/dashboard/` - Doctor's dashboard
- `/doctor/profile/` - Doctor's profile
- `/doctor/appointments/` - List of appointments
- `/doctor/appointments/create/` - Create appointment
- `/doctor/patients/` - Patient management
- `/doctor/prescriptions/` - Prescription management
- `/doctor/availability/` - Manage availability
- `/doctor/leaves/` - Manage leaves
- `/doctor/calendar/` - Calendar view

### Patient URLs
All under `/patient/` prefix:
- `/patient/dashboard/` - Patient's dashboard
- `/patient/profile/` - Patient's profile
- `/patient/appointments/` - List of appointments
- `/patient/prescriptions/` - View prescriptions
- `/patient/medical-history/` - Medical history

### Staff URLs
All under `/staff/` prefix:
- `/staff/dashboard/` - Staff dashboard
- `/staff/appointments/` - Manage appointments
- `/staff/patients/` - View patients
- `/staff/billing/` - Billing management

### Clinic Admin URLs
All under `/clinic-admin/` prefix:
- `/clinic-admin/dashboard/` - Admin dashboard
- `/clinic-admin/doctors/` - Manage doctors
- `/clinic-admin/staff/` - Manage staff
- `/clinic-admin/labs/` - Manage labs

### API URLs
All under `/api/` prefix:
- `/api/slots/available/` - Available appointment slots
- `/api/appointments/` - Appointment management
- `/api/doctor/` - Doctor-related APIs
- `/api/patient/` - Patient-related APIs
- `/api/clinics/` - Clinic management

## Benefits of Reorganization

1. **Improved Organization**: URLs are grouped by user role and function
2. **Removed Duplicates**: Duplicate URL patterns have been eliminated
3. **Better Maintainability**: Changes to a specific feature affect only one section
4. **Clearer Documentation**: Structure is now more self-documenting

## API Endpoint Structure

API endpoints follow a consistent pattern:
- `/api/{entity}/{action}/`
- `/api/{user_role}/{entity}/{action}/`

Examples:
- `/api/doctor/patients/` - Get a doctor's patients
- `/api/slots/available/` - Get available time slots
- `/api/clinics/public/` - Get public clinic information 