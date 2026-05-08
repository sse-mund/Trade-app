
import sqlite3
import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockDatabase:
    """
    Manages SQLite database operations for stock data, news, and feedback.
    """
    
    def __init__(self, db_path='stock_data.db'):
        self.db_path = db_path
        self._initialize_db()
        
    def get_connection(self):
        """Create a database connection."""
        return sqlite3.connect(self.db_path)
        
    def _initialize_db(self):
        """Initialize database tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Stocks Table (Metadata)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            ticker TEXT PRIMARY KEY,
            company_name TEXT,
            sector TEXT,
            last_updated TIMESTAMP
        )
        ''')
        
        # 2. Historical Prices Table (OHLCV)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            date TIMESTAMP,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            FOREIGN KEY (ticker) REFERENCES stocks (ticker),
            UNIQUE(ticker, date)
        )
        ''')
        
        # 3. News Articles Table (New for Phase 1)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            source TEXT,
            headline TEXT,
            summary TEXT,
            url TEXT,
            published_at TIMESTAMP,
            sentiment_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticker) REFERENCES stocks (ticker),
            UNIQUE(url)
        )
        ''')
        
        # 4. User Feedback Table (New for RL/Phase 3)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            recommendation TEXT,
            user_action TEXT, -- 'agree', 'disagree', 'correct_buy', 'correct_sell'
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (ticker) REFERENCES stocks (ticker)
        )
        ''')
        
        # 5. Company Fundamentals Table (cached for 10 days)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_fundamentals (
            ticker TEXT PRIMARY KEY,
            market_cap REAL,
            pe_ratio REAL,
            forward_pe REAL,
            price_to_book REAL,
            revenue_ttm REAL,
            gross_profit REAL,
            net_income REAL,
            eps REAL,
            free_cash_flow REAL,
            return_on_equity REAL,
            total_debt REAL,
            debt_to_equity REAL,
            current_ratio REAL,
            next_earnings_date TEXT,
            earnings_growth REAL,
            revenue_growth REAL,
            fetched_at TIMESTAMP
        )
        ''')

        # 6. Alert History Table (Watchlist Monitor)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            previous_recommendation TEXT,
            current_recommendation TEXT,
            previous_signal REAL,
            current_signal REAL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Migration: add new columns if the table already exists without them
        for col, col_type in [
            ('free_cash_flow', 'REAL'),
            ('return_on_equity', 'REAL'),
        ]:
            try:
                cursor.execute(f'ALTER TABLE company_fundamentals ADD COLUMN {col} {col_type}')
            except Exception:
                pass  # column already exists

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def insert_stock_metadata(self, ticker: str, company_name: str, sector: str):
        """Insert or update stock metadata."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO stocks (ticker, company_name, sector, last_updated)
        VALUES (?, ?, ?, ?)
        ''', (ticker, company_name, sector, datetime.now()))
        
        conn.commit()
        conn.close()
        logger.info(f"Updated metadata for {ticker}")

    def insert_historical_data(self, ticker: str, df: pd.DataFrame):
        """Insert historical price data from a DataFrame."""
        if df.empty:
            return 0
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        records_added = 0
        try:
            for index, row in df.iterrows():
                # Handle potential index variations
                date_val = index
                if isinstance(date_val, pd.Timestamp):
                    date_val = date_val.to_pydatetime()
                
                cursor.execute('''
                INSERT OR REPLACE INTO historical_prices 
                (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ticker, 
                    date_val,
                    row['Open'], row['High'], row['Low'], row['Close'], row['Volume']
                ))
            records_added = cursor.rowcount  # Note: This might only capture last operation depending on driver
            # For accurate count with executemany or loop, manual tracking is safer
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting historical data for {ticker}: {e}")
        finally:
            conn.close()
            
        logger.info(f"Inserted/Updated historical records for {ticker}")
        return len(df) # Return processed count as proxy

    def get_historical_data(self, ticker: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Retrieve historical data as a DataFrame."""
        conn = self.get_connection()
        
        query = "SELECT cast(date as text) as date, open as Open, high as High, low as Low, close as Close, volume as Volume FROM historical_prices WHERE ticker = ?"
        params = [ticker]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += " ORDER BY date ASC"
        
        try:
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                # Ensure date parsing handles timezones and mixed formats
                df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
                # Remove rows where date parsing failed
                df = df.dropna(subset=['date'])
                df.set_index('date', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error retrieving data for {ticker}: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def insert_news(self, ticker: str, news_items: List[Dict]):
        """Insert news articles into the database."""
        if not news_items:
            return 0
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        count = 0
        for item in news_items:
            try:
                # Handle varying date formats or missing keys
                pub_date = item.get('datetime', datetime.now())
                if isinstance(pub_date, int): # Unix timestamp
                    pub_date = datetime.fromtimestamp(pub_date)
                    
                cursor.execute('''
                INSERT OR IGNORE INTO news_articles 
                (ticker, source, headline, summary, url, published_at, sentiment_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ticker,
                    item.get('source', 'Unknown'),
                    item.get('headline', ''),
                    item.get('summary', ''),
                    item.get('url', ''),
                    pub_date,
                    item.get('sentiment_score', 0.0)
                ))
                if cursor.rowcount > 0:
                    count += 1
            except Exception as e:
                logger.error(f"Error inserting individual news item: {e}")
                
        conn.commit()
        conn.close()
        logger.info(f"Inserted {count} new news articles for {ticker}")
        return count

    def get_latest_news(self, ticker: str, limit: int = 10) -> List[Dict]:
        """Retrieve latest news for a ticker."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT source, headline, summary, url, published_at, sentiment_score
            FROM news_articles
            WHERE ticker = ?
            ORDER BY published_at DESC
            LIMIT ?
            ''', (ticker, limit))
            
            rows = cursor.fetchall()
            news = []
            for r in rows:
                news.append({
                    "source": r[0],
                    "headline": r[1],
                    "summary": r[2],
                    "url": r[3],
                    "datetime": r[4],
                    "sentiment": r[5]
                })
            return news
        except Exception as e:
            logger.error(f"Error retrieving news for {ticker}: {e}")
            return []
        finally:
            conn.close()

    def get_all_tickers(self) -> List[tuple]:
        """Get list of all tracked tickers."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT ticker, company_name FROM stocks")
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting tickers: {e}")
            return []
        finally:
            conn.close()

    def upsert_fundamentals(self, ticker: str, data: Dict) -> None:
        """Insert or replace company fundamentals data."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO company_fundamentals (
                ticker, market_cap, pe_ratio, forward_pe, price_to_book,
                revenue_ttm, gross_profit, net_income, eps,
                free_cash_flow, return_on_equity,
                total_debt, debt_to_equity, current_ratio,
                next_earnings_date, earnings_growth, revenue_growth,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                data.get('market_cap'),
                data.get('pe_ratio'),
                data.get('forward_pe'),
                data.get('price_to_book'),
                data.get('revenue_ttm'),
                data.get('gross_profit'),
                data.get('net_income'),
                data.get('eps'),
                data.get('free_cash_flow'),
                data.get('return_on_equity'),
                data.get('total_debt'),
                data.get('debt_to_equity'),
                data.get('current_ratio'),
                data.get('next_earnings_date'),
                data.get('earnings_growth'),
                data.get('revenue_growth'),
                datetime.now()
            ))
            conn.commit()
            logger.info(f"Upserted fundamentals for {ticker}")
        except Exception as e:
            logger.error(f"Error upserting fundamentals for {ticker}: {e}")
        finally:
            conn.close()

    def get_fundamentals(self, ticker: str) -> Optional[Dict]:
        """Retrieve cached fundamentals for a ticker, or None if not found."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT market_cap, pe_ratio, forward_pe, price_to_book,
                   revenue_ttm, gross_profit, net_income, eps,
                   free_cash_flow, return_on_equity,
                   total_debt, debt_to_equity, current_ratio,
                   next_earnings_date, earnings_growth, revenue_growth,
                   fetched_at
            FROM company_fundamentals WHERE ticker = ?
            ''', (ticker,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'market_cap': row[0],
                'pe_ratio': row[1],
                'forward_pe': row[2],
                'price_to_book': row[3],
                'revenue_ttm': row[4],
                'gross_profit': row[5],
                'net_income': row[6],
                'eps': row[7],
                'free_cash_flow': row[8],
                'return_on_equity': row[9],
                'total_debt': row[10],
                'debt_to_equity': row[11],
                'current_ratio': row[12],
                'next_earnings_date': row[13],
                'earnings_growth': row[14],
                'revenue_growth': row[15],
                'fetched_at': row[16],
            }
        except Exception as e:
            logger.error(f"Error fetching fundamentals for {ticker}: {e}")
            return None
        finally:
            conn.close()

    def delete_stock_data(self, ticker: str):
        """Delete all data associated with a ticker."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM historical_prices WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM news_articles WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM user_feedback WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
            conn.commit()
            logger.info(f"Deleted all data for {ticker}")
        except Exception as e:
            logger.error(f"Error deleting data for {ticker}: {e}")
        finally:
            conn.close()

    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        stats = {}
        try:
            cursor.execute("SELECT COUNT(*) FROM stocks")
            stats['total_stocks'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM historical_prices")
            stats['total_records'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM news_articles")
            res = cursor.fetchone()
            stats['total_news'] = res[0] if res else 0
            
            cursor.execute("SELECT MIN(date), MAX(date) FROM historical_prices")
            min_date, max_date = cursor.fetchone()
            stats['date_range'] = f"{min_date} to {max_date}"
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
        finally:
            conn.close()
        return stats

    # ──────────────────────────────────────────────────────────────────────────
    # Alert History (Watchlist Monitor)
    # ──────────────────────────────────────────────────────────────────────────

    def insert_alert(self, ticker: str, alert_type: str, severity: str,
                     message: str, prev_rec: str = None, curr_rec: str = None,
                     prev_signal: float = None, curr_signal: float = None,
                     details: str = None) -> int:
        """Insert an alert into alert_history. Returns the new row ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO alert_history
            (ticker, alert_type, severity, message,
             previous_recommendation, current_recommendation,
             previous_signal, current_signal, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticker, alert_type, severity, message,
                  prev_rec, curr_rec, prev_signal, curr_signal, details))
            conn.commit()
            row_id = cursor.lastrowid
            logger.info(f"Inserted alert #{row_id} for {ticker}: [{severity}] {alert_type}")
            return row_id
        except Exception as e:
            logger.error(f"Error inserting alert for {ticker}: {e}")
            return -1
        finally:
            conn.close()

    def get_recent_alerts(self, limit: int = 50, since: str = None) -> List[Dict]:
        """Retrieve the most recent alerts across all tickers, optionally filtered by cutoff datetime."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if since:
                cursor.execute('''
                SELECT id, ticker, alert_type, severity, message,
                       previous_recommendation, current_recommendation,
                       previous_signal, current_signal, details, created_at
                FROM alert_history
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                ''', (since, limit))
            else:
                cursor.execute('''
                SELECT id, ticker, alert_type, severity, message,
                       previous_recommendation, current_recommendation,
                       previous_signal, current_signal, details, created_at
                FROM alert_history
                ORDER BY created_at DESC
                LIMIT ?
                ''', (limit,))
            rows = cursor.fetchall()
            return [
                {
                    'id': r[0], 'ticker': r[1], 'alert_type': r[2],
                    'severity': r[3], 'message': r[4],
                    'previous_recommendation': r[5],
                    'current_recommendation': r[6],
                    'previous_signal': r[7], 'current_signal': r[8],
                    'details': r[9], 'created_at': r[10],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching recent alerts: {e}")
            return []
        finally:
            conn.close()


    def get_alerts_for_ticker(self, ticker: str, limit: int = 10) -> List[Dict]:
        """Retrieve recent alerts for a specific ticker."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT id, ticker, alert_type, severity, message,
                   previous_recommendation, current_recommendation,
                   previous_signal, current_signal, details, created_at
            FROM alert_history
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT ?
            ''', (ticker, limit))
            rows = cursor.fetchall()
            return [
                {
                    'id': r[0], 'ticker': r[1], 'alert_type': r[2],
                    'severity': r[3], 'message': r[4],
                    'previous_recommendation': r[5],
                    'current_recommendation': r[6],
                    'previous_signal': r[7], 'current_signal': r[8],
                    'details': r[9], 'created_at': r[10],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching alerts for {ticker}: {e}")
            return []
        finally:
            conn.close()
