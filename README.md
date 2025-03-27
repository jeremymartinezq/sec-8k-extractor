# SEC 8-K Filing Extractor

A Python-based tool for extracting and analyzing product-related announcements from SEC Form 8-K filings. This tool automatically fetches recent 8-K filings from the SEC EDGAR database and identifies sections containing product announcements.

## Features

- Fetches company tickers and CIK numbers from SEC's database
- Retrieves recent 8-K filings for specified companies
- Extracts text from filing documents
- Identifies product-related announcements using keyword matching
- Attempts to extract product names from context
- Saves results to CSV format
- Respects SEC API rate limits
- Includes fallback data for demonstration purposes

## Prerequisites

- Python 3.6 or higher
- Required Python packages:
  ```
  requests
  pandas
  beautifulsoup4
  lxml
  ```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/jeremymartinezq/sec-8k-extractor.git
   cd sec-8k-extractor
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the script:
```bash
python sec_final.py
```

The script will:
1. Fetch company tickers from SEC
2. Process recent 8-K filings for major tech companies (AAPL, MSFT, GOOGL, AMZN, META)
3. Extract product-related information
4. Save results to `sec_8k_product_filings.csv`

## Configuration

You can modify the following parameters in the `Config` class:

- `SEC_HEADERS`: Headers for SEC API requests
- `REQUEST_DELAY`: Delay between API requests (default: 0.2 seconds)
- `MAX_FILINGS_PER_COMPANY`: Maximum number of filings to process per company
- `MAX_COMPANIES`: Maximum number of companies to process
- `PRODUCT_KEYWORDS`: Keywords to identify product announcements

## Output

The script generates a CSV file (`sec_8k_product_filings.csv`) containing:
- Company ticker and CIK
- Filing date
- Accession number
- Document URL
- Product keyword found
- Extracted product name
- Context around the product announcement

## Rate Limiting

The script includes built-in rate limiting to comply with SEC's requirements:
- Maximum 10 requests per second
- Default delay of 0.2 seconds between requests

## Error Handling

- Graceful handling of API errors
- Fallback to simulated data if no results are found
- Comprehensive logging of operations and errors

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Jeremy Martinez-Quinones

## Acknowledgments

- SEC EDGAR API for providing access to filing data
- BeautifulSoup for HTML parsing
- Pandas for data manipulation 