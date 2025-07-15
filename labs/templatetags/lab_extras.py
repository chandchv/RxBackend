from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    if dictionary and hasattr(dictionary, 'get'):
        return dictionary.get(key, {})
    return {}

@register.filter  
def get_price(test_prices, test_id):
    """Get price for a test from test_prices dictionary"""
    if test_prices and test_id:
        test_data = test_prices.get(test_id, {})
        return test_data.get('price', 0)
    return 0

@register.filter
def get_turnaround_time(test_prices, test_id):
    """Get turnaround time for a test from test_prices dictionary"""
    if test_prices and test_id:
        test_data = test_prices.get(test_id, {})
        return test_data.get('turnaround_time', 24)
    return 24

@register.filter
def get_home_collection(test_prices, test_id):
    """Get home collection availability for a test from test_prices dictionary"""
    if test_prices and test_id:
        test_data = test_prices.get(test_id, {})
        return test_data.get('home_collection', False)
    return False 