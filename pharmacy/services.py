from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, Q
from decimal import Decimal
import uuid

from .models import (
    Pharmacy, PharmacyStaff, PharmacyStock, ProductStock,
    Prescription, PrescriptionDrug, Dispensing, OTCSale,
    StockReceipt, StockReceiptItem, BillHeader, BillItem, Payment, Product
)


def get_prescription_details(prescription_id):
    """
    Fetches prescription and its drug lines.
    
    Args:
        prescription_id (int): ID of the prescription to fetch
        
    Returns:
        dict: Dictionary containing prescription details and its drugs
    """
    try:
        prescription = Prescription.objects.get(id=prescription_id)
        prescription_drugs = prescription.prescription_drugs.all().select_related('drug')
        
        # Get dispensing status for each drug
        for drug in prescription_drugs:
            drug.total_dispensed = sum(d.quantity for d in drug.dispensings.all())
            drug.remaining = max(0, drug.quantity - drug.total_dispensed)
            
        return {
            'prescription': prescription,
            'drugs': prescription_drugs,
            'is_dispensable': not prescription.is_expired and prescription.status not in ['fully_dispensed', 'cancelled']
        }
    except Prescription.DoesNotExist:
        return None


def check_stock_availability(pharmacy_id, drug_id, quantity, batch_number=None):
    """
    Checks if a pharmacy has enough stock of a specific drug.
    
    Args:
        pharmacy_id (int): ID of the pharmacy
        drug_id (int): ID of the drug to check
        quantity (int): Quantity needed
        batch_number (str, optional): Specific batch number to check
        
    Returns:
        tuple: (bool, str) - (is_available, message)
    """
    query = PharmacyStock.objects.filter(
        pharmacy_id=pharmacy_id,
        medicine_id=drug_id,
        quantity__gt=0
    )
    
    # If batch number is specified, filter by it
    if batch_number:
        query = query.filter(batch_number=batch_number)
    
    # Exclude expired batches
    today = timezone.now().date()
    query = query.filter(Q(expiry_date__isnull=True) | Q(expiry_date__gt=today))
    
    available_quantity = query.aggregate(total=Sum('quantity'))['total'] or 0
    
    if available_quantity < quantity:
        return False, f"Insufficient stock. Available: {available_quantity}, Required: {quantity}"
    
    return True, f"Stock available: {available_quantity}"


@transaction.atomic
def dispense_prescription_drug(prescription_drug_id, quantity, pharmacy_id, staff_user, batch_number=None):
    """
    Dispenses medication to a patient and decrements pharmacy stock.
    
    Args:
        prescription_drug_id (int): ID of the prescription drug to dispense
        quantity (int): Quantity to dispense
        pharmacy_id (int): ID of the pharmacy dispensing the medication
        staff_user: User dispensing the medication
        batch_number (str, optional): Specific batch to use
        
    Returns:
        dict: Result of the dispensing operation
    """
    try:
        prescription_drug = PrescriptionDrug.objects.select_related(
            'prescription', 'prescription__patient', 'drug'
        ).get(id=prescription_drug_id)
        
        prescription = prescription_drug.prescription
        drug = prescription_drug.drug
        
        # Check prescription status
        if prescription.status in ['cancelled', 'expired', 'fully_dispensed']:
            return {
                'success': False,
                'message': f"Cannot dispense from {prescription.get_status_display()} prescription"
            }
        
        # Check if prescription is expired
        if prescription.is_expired:
            return {
                'success': False,
                'message': "Prescription has expired"
            }
        
        # Check if already fully dispensed
        total_dispensed = sum(d.quantity for d in prescription_drug.dispensings.all())
        remaining = prescription_drug.quantity - total_dispensed
        
        if remaining <= 0:
            return {
                'success': False,
                'message': f"This medication has already been fully dispensed"
            }
        
        if quantity > remaining:
            return {
                'success': False,
                'message': f"Cannot dispense more than the remaining quantity ({remaining})"
            }
        
        # Check stock availability
        stock_available, message = check_stock_availability(
            pharmacy_id=pharmacy_id,
            drug_id=drug.id,
            quantity=quantity,
            batch_number=batch_number
        )
        
        if not stock_available:
            return {
                'success': False,
                'message': message
            }
        
        # Get the stock to use (oldest expiry date first)
        stock_query = PharmacyStock.objects.filter(
            pharmacy_id=pharmacy_id,
            medicine_id=drug.id,
            quantity__gt=0
        )
        
        # If batch number specified, filter by it
        if batch_number:
            stock_query = stock_query.filter(batch_number=batch_number)
        
        # Exclude expired batches
        today = timezone.now().date()
        stock_query = stock_query.filter(Q(expiry_date__isnull=True) | Q(expiry_date__gt=today))
        
        # Order by expiry date (soonest first)
        stock_query = stock_query.order_by('expiry_date')
        
        if not stock_query.exists():
            return {
                'success': False,
                'message': "No valid stock found"
            }
        
        # Get first stock item
        stock = stock_query.first()
        
        # Create dispensing record
        dispensing = Dispensing.objects.create(
            prescription_drug=prescription_drug,
            pharmacy_id=pharmacy_id,
            quantity=quantity,
            batch_number_dispensed=stock.batch_number,
            dispensed_price_per_unit=stock.unit_price,
            total_dispensed_price=stock.unit_price * quantity,
            dispensed_by=staff_user,
            notes=f"Dispensed from stock batch {stock.batch_number or 'N/A'}"
        )
        
        # Update stock quantity
        stock.quantity -= quantity
        stock.save()
        
        # Update prescription status
        prescription.refresh_from_db()
        
        return {
            'success': True,
            'message': f"Successfully dispensed {quantity} units of {drug.product_name}",
            'dispensing': dispensing
        }
        
    except PrescriptionDrug.DoesNotExist:
        return {
            'success': False,
            'message': "Prescription drug not found"
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error dispensing medication: {str(e)}"
        }


@transaction.atomic
def sell_otc_product(product_id, quantity, pharmacy_id, staff_user, batch_number=None):
    """
    Sells an over-the-counter product and decrements stock.
    
    Args:
        product_id (int): ID of the product to sell
        quantity (int): Quantity to sell
        pharmacy_id (int): ID of the pharmacy selling the product
        staff_user: User selling the product
        batch_number (str, optional): Specific batch to use
        
    Returns:
        dict: Result of the sale operation
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # Check stock availability
        stock_query = ProductStock.objects.filter(
            pharmacy_id=pharmacy_id,
            product_id=product_id,
            quantity__gt=0
        )
        
        # If batch specified, filter by it
        if batch_number:
            stock_query = stock_query.filter(batch_number=batch_number)
        
        # Exclude expired batches
        today = timezone.now().date()
        stock_query = stock_query.filter(Q(expiry_date__isnull=True) | Q(expiry_date__gt=today))
        
        available_quantity = stock_query.aggregate(total=Sum('quantity'))['total'] or 0
        
        if available_quantity < quantity:
            return {
                'success': False,
                'message': f"Insufficient stock. Available: {available_quantity}, Required: {quantity}"
            }
        
        # Get first stock item (oldest expiry date first)
        stock_query = stock_query.order_by('expiry_date')
        stock = stock_query.first()
        
        # Create OTC sale record
        sale = OTCSale.objects.create(
            pharmacy_id=pharmacy_id,
            product=product,
            quantity=quantity,
            sale_price_per_unit=stock.unit_price,
            total_sale_price=stock.unit_price * quantity,
            sold_by=staff_user
        )
        
        # Update stock quantity
        stock.quantity -= quantity
        stock.save()
        
        return {
            'success': True,
            'message': f"Successfully sold {quantity} units of {product.name}",
            'sale': sale
        }
        
    except Product.DoesNotExist:
        return {
            'success': False,
            'message': "Product not found"
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error selling product: {str(e)}"
        }


@transaction.atomic
def create_bill_from_dispensing(dispensing_records, patient_id, pharmacy_id, staff_user, additional_notes=None):
    """
    Creates a bill from dispensing records.
    
    Args:
        dispensing_records (list): List of Dispensing objects or IDs
        patient_id (int): ID of the patient being billed
        pharmacy_id (int): ID of the pharmacy creating the bill
        staff_user: User creating the bill
        additional_notes (str, optional): Additional notes for the bill
        
    Returns:
        dict: Result of the bill creation operation
    """
    try:
        # Generate bill number
        bill_number = f"PHARM-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Get prescription if all dispensings are from the same prescription
        prescription_id = None
        dispensing_objects = []
        
        # Convert IDs to objects if needed
        for record in dispensing_records:
            if isinstance(record, int):
                try:
                    dispensing = Dispensing.objects.get(id=record)
                    dispensing_objects.append(dispensing)
                except Dispensing.DoesNotExist:
                    continue
            else:
                dispensing_objects.append(record)
        
        if not dispensing_objects:
            return {
                'success': False,
                'message': "No valid dispensing records provided"
            }
        
        # Check if all dispensings are from the same prescription
        prescription_ids = set(d.prescription_drug.prescription_id for d in dispensing_objects)
        if len(prescription_ids) == 1:
            prescription_id = prescription_ids.pop()
        
        # Create bill header
        bill = BillHeader.objects.create(
            patient_id=patient_id,
            pharmacy_id=pharmacy_id,
            prescription_id=prescription_id,
            bill_number=bill_number,
            bill_date=timezone.now().date(),
            status='draft',
            notes=additional_notes,
            created_by=staff_user
        )
        
        # Create bill items for each dispensing
        for dispensing in dispensing_objects:
            # Check if dispensing is already billed
            if hasattr(dispensing, 'bill_item') and dispensing.bill_item:
                continue
                
            BillItem.objects.create(
                bill=bill,
                item_type='prescription',
                name=dispensing.prescription_drug.drug.product_name,
                description=f"Prescribed by Dr. {dispensing.prescription_drug.prescription.doctor.name}",
                quantity=dispensing.quantity,
                price_per_unit=dispensing.dispensed_price_per_unit,
                total_price=dispensing.total_dispensed_price,
                dispensing=dispensing
            )
        
        # Update bill status
        bill.status = 'finalized'
        bill.save()
        
        return {
            'success': True,
            'message': f"Successfully created bill #{bill.bill_number}",
            'bill': bill
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error creating bill: {str(e)}"
        }


@transaction.atomic
def create_bill_from_otc_sales(sale_records, patient_id, pharmacy_id, staff_user, additional_notes=None):
    """
    Creates a bill from OTC sale records.
    
    Args:
        sale_records (list): List of OTCSale objects or IDs
        patient_id (int): ID of the patient being billed
        pharmacy_id (int): ID of the pharmacy creating the bill
        staff_user: User creating the bill
        additional_notes (str, optional): Additional notes for the bill
        
    Returns:
        dict: Result of the bill creation operation
    """
    try:
        # Generate bill number
        bill_number = f"PHARM-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        sale_objects = []
        
        # Convert IDs to objects if needed
        for record in sale_records:
            if isinstance(record, int):
                try:
                    sale = OTCSale.objects.get(id=record)
                    sale_objects.append(sale)
                except OTCSale.DoesNotExist:
                    continue
            else:
                sale_objects.append(record)
        
        if not sale_objects:
            return {
                'success': False,
                'message': "No valid sale records provided"
            }
        
        # Create bill header
        bill = BillHeader.objects.create(
            patient_id=patient_id,
            pharmacy_id=pharmacy_id,
            bill_number=bill_number,
            bill_date=timezone.now().date(),
            status='draft',
            notes=additional_notes,
            created_by=staff_user
        )
        
        # Create bill items for each sale
        for sale in sale_objects:
            # Check if sale is already billed
            if hasattr(sale, 'bill_item') and sale.bill_item:
                continue
                
            BillItem.objects.create(
                bill=bill,
                item_type='otc',
                name=sale.product.name,
                description=f"OTC Product - {sale.product.get_type_display()}",
                quantity=sale.quantity,
                price_per_unit=sale.sale_price_per_unit,
                total_price=sale.total_sale_price,
                otc_sale=sale
            )
        
        # Update bill status
        bill.status = 'finalized'
        bill.save()
        
        return {
            'success': True,
            'message': f"Successfully created bill #{bill.bill_number}",
            'bill': bill
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error creating bill: {str(e)}"
        }


@transaction.atomic
def record_payment(bill_id, amount, payment_method, staff_user, reference_number=None, notes=None):
    """
    Records a payment for a bill.
    
    Args:
        bill_id (int): ID of the bill to pay
        amount (Decimal): Amount paid
        payment_method (str): Method of payment
        staff_user: User recording the payment
        reference_number (str, optional): Reference or transaction number
        notes (str, optional): Additional notes
        
    Returns:
        dict: Result of the payment operation
    """
    try:
        bill = BillHeader.objects.get(id=bill_id)
        
        # Check if bill can be paid
        if bill.status == 'cancelled':
            return {
                'success': False,
                'message': "Cannot pay a cancelled bill"
            }
        
        # Check if amount is valid
        if amount <= 0:
            return {
                'success': False,
                'message': "Payment amount must be greater than zero"
            }
            
        # Check if amount exceeds due amount
        if amount > bill.due_amount:
            return {
                'success': False,
                'message': f"Payment amount (₹{amount}) exceeds due amount (₹{bill.due_amount})"
            }
        
        # Create payment record
        payment = Payment.objects.create(
            bill=bill,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            received_by=staff_user,
            notes=notes
        )
        
        # Bill status is updated automatically in the save method of Payment model
        
        return {
            'success': True,
            'message': f"Successfully recorded payment of ₹{amount}",
            'payment': payment,
            'paid_amount': bill.paid_amount,
            'due_amount': bill.due_amount,
            'is_fully_paid': bill.is_fully_paid
        }
        
    except BillHeader.DoesNotExist:
        return {
            'success': False,
            'message': "Bill not found"
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error recording payment: {str(e)}"
        }


@transaction.atomic
def add_stock_from_receipt(receipt_data, pharmacy_id, staff_user):
    """
    Creates stock receipt and updates pharmacy stock.
    
    Args:
        receipt_data (dict): Dictionary containing receipt data and items
        pharmacy_id (int): ID of the pharmacy receiving stock
        staff_user: User creating the receipt
        
    Returns:
        dict: Result of the stock receipt operation
    """
    try:
        # Generate receipt number if not provided
        if not receipt_data.get('receipt_number'):
            receipt_data['receipt_number'] = f"STOCK-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Create receipt
        receipt = StockReceipt.objects.create(
            pharmacy_id=pharmacy_id,
            receipt_number=receipt_data['receipt_number'],
            supplier_name=receipt_data['supplier_name'],
            supplier_invoice=receipt_data.get('supplier_invoice'),
            receipt_date=receipt_data.get('receipt_date', timezone.now().date()),
            status='received',
            notes=receipt_data.get('notes'),
            created_by=staff_user
        )
        
        # Process items
        for item_data in receipt_data.get('items', []):
            # Create receipt item
            receipt_item = StockReceiptItem.objects.create(
                receipt=receipt,
                drug_id=item_data['drug_id'],
                quantity=item_data['quantity'],
                batch_number=item_data.get('batch_number'),
                date_of_manufacture=item_data.get('date_of_manufacture'),
                date_of_expiry=item_data['date_of_expiry'],
                purchase_price_per_unit=item_data['purchase_price_per_unit'],
                total_purchase_price=item_data['quantity'] * Decimal(str(item_data['purchase_price_per_unit']))
            )
            
            # Update or create stock
            stock, created = PharmacyStock.objects.get_or_create(
                pharmacy_id=pharmacy_id,
                medicine_id=item_data['drug_id'],
                batch_number=item_data.get('batch_number'),
                defaults={
                    'quantity': 0,
                    'expiry_date': item_data['date_of_expiry'],
                    'unit_price': item_data.get('selling_price_per_unit', receipt_item.purchase_price_per_unit * Decimal('1.2'))
                }
            )
            
            # Increment stock quantity
            stock.quantity += receipt_item.quantity
            stock.save()
        
        return {
            'success': True,
            'message': f"Successfully created stock receipt #{receipt.receipt_number}",
            'receipt': receipt
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error creating stock receipt: {str(e)}"
        }


def get_stock_levels(pharmacy_id, drug_id=None, product_id=None):
    """
    Returns current stock quantities for a pharmacy.
    
    Args:
        pharmacy_id (int): ID of the pharmacy
        drug_id (int, optional): ID of the drug to filter
        product_id (int, optional): ID of the product to filter
        
    Returns:
        dict: Dictionary containing stock information
    """
    today = timezone.now().date()
    
    # Get drug stock
    drug_stock_query = PharmacyStock.objects.filter(pharmacy_id=pharmacy_id)
    if drug_id:
        drug_stock_query = drug_stock_query.filter(medicine_id=drug_id)
    
    drug_stock = drug_stock_query.select_related('medicine').annotate(
        is_expired=Q(expiry_date__isnull=False) & Q(expiry_date__lte=today)
    ).order_by('medicine__product_name', 'expiry_date')
    
    # Get product stock
    product_stock_query = ProductStock.objects.filter(pharmacy_id=pharmacy_id)
    if product_id:
        product_stock_query = product_stock_query.filter(product_id=product_id)
    
    product_stock = product_stock_query.select_related('product').annotate(
        is_expired=Q(expiry_date__isnull=False) & Q(expiry_date__lte=today)
    ).order_by('product__name', 'expiry_date')
    
    return {
        'drug_stock': drug_stock,
        'product_stock': product_stock
    }


def get_low_stock_report(pharmacy_id, threshold=None):
    """
    Identifies low stock items.
    
    Args:
        pharmacy_id (int): ID of the pharmacy
        threshold (int, optional): Override default threshold
        
    Returns:
        dict: Dictionary containing low stock items
    """
    # Get drug low stock
    drug_query = PharmacyStock.objects.filter(pharmacy_id=pharmacy_id)
    if threshold:
        drug_query = drug_query.filter(quantity__lte=threshold)
    else:
        drug_query = drug_query.filter(quantity__lte=F('min_stock_level'))
    
    low_drug_stock = drug_query.select_related('medicine').order_by('medicine__product_name')
    
    # Get product low stock
    product_query = ProductStock.objects.filter(pharmacy_id=pharmacy_id)
    if threshold:
        product_query = product_query.filter(quantity__lte=threshold)
    else:
        product_query = product_query.filter(quantity__lte=F('min_stock_level'))
    
    low_product_stock = product_query.select_related('product').order_by('product__name')
    
    return {
        'low_drug_stock': low_drug_stock,
        'low_product_stock': low_product_stock
    }


def get_expiring_stock_report(pharmacy_id, days=30):
    """
    Identifies stock items that will expire soon.
    
    Args:
        pharmacy_id (int): ID of the pharmacy
        days (int): Number of days to consider "soon"
        
    Returns:
        dict: Dictionary containing expiring stock items
    """
    today = timezone.now().date()
    expiry_threshold = today + timezone.timedelta(days=days)
    
    # Get drug expiring stock
    drug_query = PharmacyStock.objects.filter(
        pharmacy_id=pharmacy_id,
        expiry_date__isnull=False,
        expiry_date__gt=today,
        expiry_date__lte=expiry_threshold,
        quantity__gt=0
    )
    
    expiring_drug_stock = drug_query.select_related('medicine').order_by('expiry_date')
    
    # Get product expiring stock
    product_query = ProductStock.objects.filter(
        pharmacy_id=pharmacy_id,
        expiry_date__isnull=False,
        expiry_date__gt=today,
        expiry_date__lte=expiry_threshold,
        quantity__gt=0
    )
    
    expiring_product_stock = product_query.select_related('product').order_by('expiry_date')
    
    return {
        'expiring_drug_stock': expiring_drug_stock,
        'expiring_product_stock': expiring_product_stock,
        'days_threshold': days
    }


def get_pending_prescriptions(pharmacy_id):
    """
    Gets prescriptions that are new or in process.
    
    Args:
        pharmacy_id (int): ID of the pharmacy
        
    Returns:
        queryset: Prescriptions waiting to be dispensed
    """
    return Prescription.objects.filter(
        status__in=['new', 'processing', 'partially_dispensed']
    ).select_related('patient', 'doctor').order_by('-created_at') 