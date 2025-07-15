#!/usr/bin/env python3
"""
Test script to verify pagination fix for Aster Labs scraper
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aster_labs_advanced_scraper import AsterLabsAdvancedScraper

def test_pagination():
    """Test the pagination functionality"""
    print("🧪 Testing Aster Labs Scraper Pagination")
    print("=" * 50)
    
    scraper = AsterLabsAdvancedScraper()
    
    # Test with a small number of pages first
    print("Testing with max_pages=2...")
    result = scraper.run_scraper(max_pages=2)
    
    if result:
        print(f"✅ Success! Scraped {result['total_count']} tests across multiple pages")
        print(f"📁 CSV file: {result['csv_file']}")
        
        # Check if we got more than 15 tests (which was the single page result)
        if result['total_count'] > 15:
            print("🎉 Pagination is working correctly!")
        else:
            print("⚠️  Still only getting single page results")
            
        return True
    else:
        print("❌ Scraping failed")
        return False

if __name__ == "__main__":
    test_pagination() 