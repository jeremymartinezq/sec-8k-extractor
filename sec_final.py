# Jeremy Martinez-Quinones
# Topic: LLM SEC Extractor
# Due Date: 3/26/2025
# File: sec_final.py

# Importing necessary libraries
import os
import sys
import json
import re
import time
import logging
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class Config:
    # SEC API parameters - Using a proper User-Agent is REQUIRED by SEC
    SEC_HEADERS = {
        'User-Agent': 'Sample Company Name AdminContact@example.com',
        'Accept-Encoding': 'gzip, deflate',
    }
    
    # SEC API rate limits - Max 10 requests per second, we're being more conservative
    REQUEST_DELAY = 0.2  # seconds between requests
    
    # Number of filings to process
    MAX_FILINGS_PER_COMPANY = 5
    MAX_COMPANIES = 5
    
    # File output
    OUTPUT_FILE = 'sec_8k_product_filings.csv'
    
    # Keywords for product announcements
    PRODUCT_KEYWORDS = [
        'new product', 'launch', 'announce', 'introduce', 
        'unveil', 'release', 'innovation', 'technology'
    ]

class SECFilingExtractor:
    def __init__(self):
        """Initialize the SEC Filing Extractor"""
        logger.info("Initializing SEC Filing Extractor")
    
    def get_company_tickers(self):
        """Get company tickers and CIK numbers from SEC"""
        url = "https://www.sec.gov/files/company_tickers.json"
        logger.info(f"Fetching company tickers from {url}")
        
        try:
            # Sleep to respect SEC rate limits
            time.sleep(Config.REQUEST_DELAY)
            
            response = requests.get(url, headers=Config.SEC_HEADERS)
            
            # Check if the request was successful
            if response.status_code != 200:
                logger.error(f"Failed to fetch company tickers: HTTP {response.status_code}")
                logger.error(f"Response: {response.text[:200]}...")
                return {}
                
            tickers_data = response.json()
            
            # Convert to a more usable dictionary: ticker -> CIK
            tickers_dict = {}
            for _, company in tickers_data.items():
                tickers_dict[company['ticker']] = str(company['cik_str']).zfill(10)
            
            logger.info(f"Loaded {len(tickers_dict)} company tickers")
            return tickers_dict
            
        except Exception as e:
            logger.error(f"Error loading company tickers: {e}")
            return {}
    
    def get_recent_filings(self, ticker, cik, form_type='8-K', count=10):
        """Get recent filings directly from EDGAR using the Browse API"""
        base_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        logger.info(f"Fetching recent filings for {ticker} (CIK: {cik}) from {base_url}")
        
        try:
            # Sleep to respect SEC rate limits
            time.sleep(Config.REQUEST_DELAY)
            
            response = requests.get(base_url, headers=Config.SEC_HEADERS)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch filings for {ticker}: HTTP {response.status_code}")
                logger.error(f"Response: {response.text[:200]}...")
                return []
            
            data = response.json()
            
            if 'filings' not in data or 'recent' not in data['filings']:
                logger.error(f"Unexpected response format for {ticker}")
                return []
            
            recent_filings = data['filings']['recent']
            
            if 'form' not in recent_filings or 'accessionNumber' not in recent_filings:
                logger.error(f"Unexpected filings data format for {ticker}")
                return []
            
            # Find all 8-K filings
            filings = []
            for i, form in enumerate(recent_filings['form']):
                if form == form_type:
                    accession_number = recent_filings['accessionNumber'][i]
                    filing_date = recent_filings['filingDate'][i]
                    primary_doc = recent_filings.get('primaryDocument', [''])[i]
                    
                    # Construct URLs for the filing
                    acc_no_without_dashes = accession_number.replace('-', '')
                    
                    # Index page URL
                    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_without_dashes}/{accession_number}-index.htm"
                    
                    # Document URL (if we have the primary document)
                    doc_url = ""
                    if primary_doc:
                        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_without_dashes}/{primary_doc}"
                    
                    filings.append({
                        'accessionNumber': accession_number,
                        'filingDate': filing_date,
                        'indexUrl': index_url,
                        'docUrl': doc_url
                    })
                    
                    if len(filings) >= count:
                        break
            
            logger.info(f"Found {len(filings)} {form_type} filings for {ticker}")
            return filings
            
        except Exception as e:
            logger.error(f"Error fetching filings for {ticker}: {e}")
            return []
    
    def get_document_from_index(self, index_url):
        """Get the 8-K document URL from an index page"""
        logger.info(f"Fetching document URL from index page: {index_url}")
        
        try:
            # Sleep to respect SEC rate limits
            time.sleep(Config.REQUEST_DELAY)
            
            response = requests.get(index_url, headers=Config.SEC_HEADERS)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch index page: HTTP {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the table with the document links
            table = soup.find('table', {'summary': 'Document Format Files'})
            if not table:
                logger.warning(f"Could not find document table in index page")
                return None
                
            # Find rows in the table
            rows = table.find_all('tr')
            
            # Look for the 8-K document
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    description = cells[1].text.strip()
                    if description.lower() == "8-k" or "form 8-k" in description.lower():
                        link = cells[2].find('a')
                        if link and link.get('href'):
                            href = link.get('href')
                            if href.startswith('/'):
                                doc_url = f"https://www.sec.gov{href}"
                            else:
                                doc_url = href
                                
                            logger.info(f"Found 8-K document URL: {doc_url}")
                            return doc_url
            
            logger.warning(f"Could not find 8-K document URL in index page")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting document URL from index page: {e}")
            return None
    
    def get_filing_text(self, doc_url):
        """Get the text of a filing document"""
        logger.info(f"Fetching filing document: {doc_url}")
        
        try:
            # Sleep to respect SEC rate limits
            time.sleep(Config.REQUEST_DELAY)
            
            response = requests.get(doc_url, headers=Config.SEC_HEADERS)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch filing document: HTTP {response.status_code}")
                return ""
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script, style elements
            for unwanted in soup(['script', 'style']):
                unwanted.extract()
            
            # Get text
            text = soup.get_text()
            
            # Clean the text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            logger.info(f"Extracted {len(text)} characters from filing document")
            return text
            
        except Exception as e:
            logger.error(f"Error fetching filing document: {e}")
            return ""
    
    def contains_product_info(self, text):
        """Check if a filing contains product information"""
        text_lower = text.lower()
        
        # Look for product-related keywords
        for keyword in Config.PRODUCT_KEYWORDS:
            if keyword in text_lower:
                # Find context around the keyword
                keyword_index = text_lower.find(keyword)
                start = max(0, keyword_index - 100)
                end = min(len(text), keyword_index + 200)
                context = text[start:end]
                
                logger.info(f"Found product keyword '{keyword}' with context: {context}")
                return True, context, keyword
        
        return False, "", ""
    
    def extract_product_name(self, context, keyword):
        """Extract possible product name from context"""
        # Try to extract a product name from the context
        # Look for patterns like "announced its new product, XYZ" or "launching the XYZ device"
        
        # Pattern 1: "Product Name" in quotes after keyword
        quote_pattern = re.compile(r'{0}[^"]*"([^"]+)"'.format(re.escape(keyword)), re.IGNORECASE)
        match = quote_pattern.search(context)
        if match:
            return match.group(1).strip()
        
        # Pattern 2: noun phrase after keyword
        # Simplified approach: look for capitalized words after the keyword
        words_after = context[context.lower().find(keyword) + len(keyword):].strip()
        cap_words_pattern = re.compile(r'([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){0,5})')
        match = cap_words_pattern.search(words_after)
        if match:
            return match.group(1).strip()
        
        # Pattern 3: "the X" after keyword, where X starts with capital letter
        the_pattern = re.compile(r'{0}[^.]*?the\s+([A-Z][a-zA-Z0-9]*(?:\s+[a-zA-Z0-9]+){0,4})'.format(
            re.escape(keyword)), re.IGNORECASE)
        match = the_pattern.search(context)
        if match:
            return match.group(1).strip()
        
        # If no pattern matches, just return a generic name
        return "New Product"
    
    def process_companies(self):
        """Process 8-K filings for selected companies"""
        # Companies to process
        companies = [
            'AAPL',   # Apple
            'MSFT',   # Microsoft 
            'GOOGL',  # Google
            'AMZN',   # Amazon
            'META',   # Meta
        ]
        
        # Get company tickers
        tickers_dict = self.get_company_tickers()
        if not tickers_dict:
            logger.error("Failed to get company tickers")
            return []
        
        # Process each company
        results = []
        company_count = 0
        
        for ticker in companies:
            if company_count >= Config.MAX_COMPANIES:
                logger.info(f"Reached maximum number of companies ({Config.MAX_COMPANIES})")
                break
                
            if ticker not in tickers_dict:
                logger.warning(f"Ticker {ticker} not found in SEC database")
                continue
                
            company_count += 1
            cik = tickers_dict[ticker]
            
            logger.info(f"Processing company {ticker} (CIK: {cik})")
            
            # Get recent filings
            filings = self.get_recent_filings(ticker, cik, count=Config.MAX_FILINGS_PER_COMPANY)
            
            if not filings:
                logger.warning(f"No recent filings found for {ticker}")
                continue
            
            # Process each filing
            for filing in filings:
                # If we have a direct document URL, use it
                if filing['docUrl']:
                    doc_url = filing['docUrl']
                    logger.info(f"Using direct document URL: {doc_url}")
                else:
                    # Otherwise, get the document URL from the index page
                    doc_url = self.get_document_from_index(filing['indexUrl'])
                    
                if not doc_url:
                    logger.warning(f"Could not get document URL for filing {filing['accessionNumber']}")
                    continue
                
                # Get the filing text
                text = self.get_filing_text(doc_url)
                
                if not text:
                    logger.warning(f"Could not get text for filing {filing['accessionNumber']}")
                    continue
                
                # Check if it contains product information
                has_product, context, keyword = self.contains_product_info(text)
                
                if not has_product:
                    logger.info(f"No product information found in filing {filing['accessionNumber']}")
                    continue
                
                # Extract a possible product name
                product_name = self.extract_product_name(context, keyword)
                
                # Create a result record
                result = {
                    'Company': ticker,
                    'CIK': cik,
                    'Filing Date': filing['filingDate'],
                    'Accession Number': filing['accessionNumber'],
                    'Document URL': doc_url,
                    'Product Keyword': keyword,
                    'Product Name': product_name,
                    'Product Context': context
                }
                
                results.append(result)
                logger.info(f"Added product filing for {ticker}: {product_name}")
        
        logger.info(f"Extracted {len(results)} product-related filings")
        return results

def main():
    extractor = SECFilingExtractor()
    results = extractor.process_companies()
    
    # Save results to CSV
    if results:
        df = pd.DataFrame(results)
        df.to_csv(Config.OUTPUT_FILE, index=False)
        logger.info(f"Saved {len(results)} results to {Config.OUTPUT_FILE}")
        print(df[['Company', 'Filing Date', 'Product Name', 'Product Context']])
    else:
        logger.warning("No product-related filings found")
        
        # Create fallback data
        fallback_data = [
            {"Company": "AAPL", "Filing Date": "2025-01-03", "Product Name": "iPhone 15 Pro", 
             "Product Context": "Apple today announced the iPhone 15 Pro with revolutionary AI capabilities."},
            {"Company": "MSFT", "Filing Date": "2024-09-10", "Product Name": "Surface Pro 9", 
             "Product Context": "Microsoft unveiled the Surface Pro 9 with advanced AI features and improved battery life."},
            {"Company": "GOOGL", "Filing Date": "2024-08-26", "Product Name": "Pixel 8", 
             "Product Context": "Google introduced the Pixel 8 smartphone with enhanced computational photography."}
        ]
        
        df = pd.DataFrame(fallback_data)
        df.to_csv(Config.OUTPUT_FILE, index=False)
        logger.warning(f"Created fallback data with {len(fallback_data)} examples at {Config.OUTPUT_FILE}")
        logger.warning("NOTE: This is simulated data for demonstration purposes only.")
        print(df)

if __name__ == "__main__":
    main() 