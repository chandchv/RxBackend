from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum, Q, F

from .models import (
    Pharmacy, PharmacyStock, PharmacyStaff, Prescription,
    BillHeader, Product, ProductStock
)

class PharmacyDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'pharmacy/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get the user's pharmacy
        try:
            pharmacy_staff = PharmacyStaff.objects.get(user=user)
            pharmacy = pharmacy_staff.pharmacy
        except PharmacyStaff.DoesNotExist:
            # If user is not pharmacy staff, try to get a pharmacy if they're an admin
            if user.is_staff:
                try:
                    pharmacy = Pharmacy.objects.first()
                except Pharmacy.DoesNotExist:
                    context['error'] = "No pharmacy found. Please set up a pharmacy first."
                    return context
            else:
                context['error'] = "You do not have permission to access the pharmacy dashboard."
                return context
        
        context['pharmacy'] = pharmacy
        
        # Calculate metrics for today
        today = timezone.now().date()
        
        # KPI 1: New Prescriptions
        new_prescriptions = Prescription.objects.filter(
            status='new'
        ).count()
        
        # KPI 2: Prescriptions Processing
        processing_prescriptions = Prescription.objects.filter(
            status='processing'
        ).count()
        
        # KPI 3: Items Low Stock
        low_stock_items = PharmacyStock.objects.filter(
            pharmacy=pharmacy,
            quantity__lte=F('min_stock_level')
        ).count()
        
        # KPI 4: Items Expiring Soon (next 30 days)
        expiry_threshold = today + timedelta(days=30)
        expiring_soon_items = PharmacyStock.objects.filter(
            pharmacy=pharmacy,
            expiry_date__isnull=False,
            expiry_date__gt=today,
            expiry_date__lte=expiry_threshold
        ).count()
        
        # KPI 5: Today's Sales
        todays_sales = BillHeader.objects.filter(
            pharmacy=pharmacy,
            bill_date=today,
            status__in=['finalized', 'paid']
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # KPI 6: Pending Bills
        pending_bills = BillHeader.objects.filter(
            pharmacy=pharmacy,
            status='finalized',
            total_amount__gt=F('paid_amount')
        ).count()
        
        # Add KPIs to context
        context.update({
            'new_prescriptions': new_prescriptions,
            'processing_prescriptions': processing_prescriptions,
            'low_stock_items': low_stock_items,
            'expiring_soon_items': expiring_soon_items,
            'todays_sales': todays_sales,
            'pending_bills': pending_bills,
        })
        
        # Get details for low stock items
        context['low_stock_details'] = PharmacyStock.objects.filter(
            pharmacy=pharmacy,
            quantity__lte=F('min_stock_level')
        ).select_related('medicine').order_by('quantity')[:10]
        
        # Get details for expiring soon items
        context['expiring_soon_details'] = PharmacyStock.objects.filter(
            pharmacy=pharmacy,
            expiry_date__isnull=False,
            expiry_date__gt=today,
            expiry_date__lte=expiry_threshold
        ).select_related('medicine').order_by('expiry_date')[:10]
        
        # Also check for OTC products with low stock
        context['low_stock_otc'] = ProductStock.objects.filter(
            pharmacy=pharmacy,
            quantity__lte=F('min_stock_level')
        ).select_related('product').order_by('quantity')[:5]
        
        # OTC products expiring soon
        context['expiring_soon_otc'] = ProductStock.objects.filter(
            pharmacy=pharmacy, 
            expiry_date__isnull=False,
            expiry_date__gt=today,
            expiry_date__lte=expiry_threshold
        ).select_related('product').order_by('expiry_date')[:5]
        
        return context
