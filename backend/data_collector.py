import yfinance as yf
import time
from datetime import datetime
import logger_config
from database import StockDatabase
from config import TOP_50_STOCKS, HISTORICAL_PERIOD, FETCH_INTERVAL, BATCH_DELAY

logger = logger_config.get_logger(__name__)

class DataCollector:
    """Collects and stores historical stock data."""
    
    def __init__(self):
        """Initialize data collector with database connection."""
        logger.info("Initializing DataCollector")
        self.db = StockDatabase()
    
    def fetch_stock_info(self, ticker):
        """Fetch stock metadata information."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            company_name = info.get('longName', info.get('shortName', ticker))
            sector = info.get('sector', 'Unknown')
            
            logger.info(f"Fetched info for {ticker}: {company_name}")
            return company_name, sector
        except Exception as e:
            logger.warning(f"Could not fetch info for {ticker}: {str(e)}")
            return ticker, 'Unknown'
    
    def fetch_and_store_stock_data(self, ticker):
        """Fetch historical data for a single stock and store in database."""
        logger.info(f"Starting data collection for {ticker}")
        
        try:
            # Fetch stock metadata
            company_name, sector = self.fetch_stock_info(ticker)
            self.db.insert_stock_metadata(ticker, company_name, sector)
            
            # Fetch historical data
            logger.info(f"Fetching {HISTORICAL_PERIOD} of historical data for {ticker}")
            stock = yf.Ticker(ticker)
            df = stock.history(period=HISTORICAL_PERIOD, interval=FETCH_INTERVAL)
            
            if df.empty:
                logger.warning(f"No historical data available for {ticker}")
                return False
            
            # Add Adj Close if not present
            if 'Adj Close' not in df.columns and 'Close' in df.columns:
                df['Adj Close'] = df['Close']
            
            logger.info(f"Fetched {len(df)} records for {ticker} from {df.index[0]} to {df.index[-1]}")
            
            # Store in database
            records_inserted = self.db.insert_historical_data(ticker, df)
            
            if records_inserted > 0:
                logger.info(f"Successfully stored {records_inserted} records for {ticker}")
                return True
            else:
                logger.warning(f"Failed to store data for {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing {ticker}: {str(e)}", exc_info=True)
            return False
    
    def collect_all_stocks(self, stock_list=None):
        """Collect historical data for all stocks in the list."""
        if stock_list is None:
            stock_list = TOP_50_STOCKS
        
        total_stocks = len(stock_list)
        logger.info(f"Starting batch collection for {total_stocks} stocks")
        print(f"\n{'='*60}")
        print(f"Starting data collection for {total_stocks} stocks")
        print(f"{'='*60}\n")
        
        successful = 0
        failed = 0
        
        for idx, ticker in enumerate(stock_list, 1):
            print(f"[{idx}/{total_stocks}] Processing {ticker}...", end=' ')
            
            success = self.fetch_and_store_stock_data(ticker)
            
            if success:
                successful += 1
                print("[OK]")
            else:
                failed += 1
                print("[FAILED]")
            
            # Rate limiting - delay between requests
            if idx < total_stocks:
                time.sleep(BATCH_DELAY)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Data Collection Complete!")
        print(f"{'='*60}")
        print(f"Successful: {successful}/{total_stocks}")
        print(f"Failed: {failed}/{total_stocks}")
        print(f"{'='*60}\n")
        
        logger.info(f"Batch collection complete. Success: {successful}, Failed: {failed}")
        
        # Get database statistics
        stats = self.db.get_database_stats()
        print(f"Database Statistics:")
        print(f"  Total stocks: {stats.get('total_stocks', 0)}")
        print(f"  Total records: {stats.get('total_records', 0)}")
        if stats.get('date_range'):
            print(f"  Date range: {stats['date_range'][0]} to {stats['date_range'][1]}")
        print()
        
        return successful, failed
    
    def update_stock_data(self, ticker, last_bar_date=None):
        """
        Update data for a specific stock.
        
        If last_bar_date is provided, do an incremental fetch from that date.
        Otherwise, do a full 5-year fetch.
        """
        if last_bar_date is not None:
            return self.incremental_update(ticker, last_bar_date)
        
        logger.info(f"Full update for {ticker} (no prior data)")
        return self.fetch_and_store_stock_data(ticker)
    
    def incremental_update(self, ticker, last_bar_date):
        """
        Fetch only the missing data from last_bar_date to today.
        Much faster than re-downloading 5 years of history.
        """
        from datetime import timedelta
        
        # Start 1 day before last bar to ensure overlap (handles partial bars)
        start_date = last_bar_date - timedelta(days=1)
        start_str = start_date.strftime('%Y-%m-%d')
        
        logger.info(f"Incremental update for {ticker}: fetching from {start_str}")
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_str, interval=FETCH_INTERVAL)
            
            if df.empty:
                logger.warning(f"No new data available for {ticker} since {start_str}")
                return False
            
            # Add Adj Close if not present
            if 'Adj Close' not in df.columns and 'Close' in df.columns:
                df['Adj Close'] = df['Close']
            
            logger.info(f"Incremental fetch: {len(df)} records for {ticker} from {df.index[0].date()} to {df.index[-1].date()}")
            
            # Insert/update in database (upsert — replaces existing bars for overlap dates)
            records_inserted = self.db.insert_historical_data(ticker, df)
            
            if records_inserted > 0:
                logger.info(f"Incremental update: stored {records_inserted} records for {ticker}")
                return True
            else:
                logger.warning(f"Incremental update: no records stored for {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"Incremental update error for {ticker}: {e}", exc_info=True)
            return False
    
    def list_stored_stocks(self):
        """List all stocks currently in the database."""
        tickers = self.db.get_all_tickers()
        
        if not tickers:
            print("No stocks found in database.")
            return
        
        print(f"\n{'='*70}")
        print(f"Stocks in Database ({len(tickers)} total)")
        print(f"{'='*70}")
        print(f"{'Ticker':<10} {'Last Updated':<25} {'Records':<10}")
        print(f"{'-'*70}")
        
        for ticker, last_updated, total_records in tickers:
            print(f"{ticker:<10} {last_updated:<25} {total_records:<10}")
        
        print(f"{'='*70}\n")

def main():
    """Main function to run data collection."""
    # Setup logging
    logger_config.setup_logging()
    
    print("\n" + "="*60)
    print("Stock Historical Data Collector")
    print("="*60 + "\n")
    
    collector = DataCollector()
    
    # Collect data for all top 50 stocks
    collector.collect_all_stocks()
    
    # List all stored stocks
    collector.list_stored_stocks()

if __name__ == "__main__":
    main()
