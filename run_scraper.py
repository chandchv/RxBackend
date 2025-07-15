#!/usr/bin/env python3
"""
Simple script to run the Aster Labs scraper with different options
"""

import sys
import argparse
from aster_labs_advanced_scraper import AsterLabsAdvancedScraper

def main():
    parser = argparse.ArgumentParser(description='Scrape tests from Aster Labs website')
    parser.add_argument('--url', default='https://www.asterlabs.in/bengaluru/tests',
                       help='URL to scrape (default: Aster Labs Bengaluru tests)')
    parser.add_argument('--max-pages', type=int, default=5,
                       help='Maximum number of pages to scrape (default: 5)')
    parser.add_argument('--output', default=None,
                       help='Output CSV filename (default: auto-generated)')
    parser.add_argument('--json', action='store_true',
                       help='Also save results to JSON file')
    
    args = parser.parse_args()
    
    print("🔬 Aster Labs Test Scraper")
    print("=" * 40)
    print(f"URL: {args.url}")
    print(f"Max pages: {args.max_pages}")
    print(f"Output file: {args.output or 'auto-generated'}")
    print("=" * 40)
    
    # Create scraper instance
    scraper = AsterLabsAdvancedScraper()
    
    try:
        # Run the scraper
        result = scraper.run_scraper(args.url, max_pages=args.max_pages)
        
        if result:
            print(f"\n✅ Successfully scraped {result['total_count']} tests!")
            print(f"📁 CSV file: {result['csv_file']}")
            
            if args.json and result['json_file']:
                print(f"📄 JSON file: {result['json_file']}")
            
            # Show quick stats
            tests = result['tests']
            prices = [int(t['price']) for t in tests if t['price'] != '0']
            
            if prices:
                print(f"\n💰 Price Statistics:")
                print(f"   Min: Rs.{min(prices)}")
                print(f"   Max: Rs.{max(prices)}")
                print(f"   Average: Rs.{sum(prices) / len(prices):.0f}")
            
            # Show top categories
            categories = {}
            for test in tests:
                cat = test['category']
                categories[cat] = categories.get(cat, 0) + 1
            
            print(f"\n📂 Top Categories:")
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {cat}: {count} tests")
            
            print(f"\n🎉 Scraping completed successfully!")
            
        else:
            print("❌ No tests were scraped.")
            print("Possible reasons:")
            print("  - Website structure may have changed")
            print("  - Network connection issues")
            print("  - Website may be blocking automated requests")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 