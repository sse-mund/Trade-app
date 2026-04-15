# News API Setup Guide

This guide will help you set up News API integration for the Trade Strategy App.

## What is News API?

News API (newsapi.org) provides access to news articles from over 150,000 sources worldwide. It's an excellent free alternative for fetching financial and business news.

## Free Tier Features

- ✅ **100 requests per day**
- ✅ **Business category access** for financial news
- ✅ **No credit card required**
- ✅ **150,000+ news sources**
- ⚠️ **24-hour delay** on articles (real-time requires paid plan)

## Setup Instructions

### Step 1: Register for API Key

1. Visit [newsapi.org/register](https://newsapi.org/register)
2. Fill in the registration form:
   - First name and email
   - Password
   - Choose "I'm an individual" if for personal use
3. Verify your email address (check spam folder if needed)
4. Log in to your News API account
5. Your API key will be displayed on the dashboard

### Step 2: Configure Environment Variable

1. Open the file: `backend\.env`
2. Find the section:
   ```
   # NEWS API KEY (Financial/Business News)
   NEWSAPI_KEY=your_newsapi_key_here
   ```
3. Replace `your_newsapi_key_here` with your actual API key
4. Save the file

### Step 3: Restart Backend (if needed)

If your backend server is running, it should auto-reload. If not:

```bash
cd backend
python -m uvicorn main:app --reload
```

## Verification

### Check Logs

When the backend starts, you should see:
```
INFO:data.ingestion.newsapi_connector:News API connector initialized
```

### Test the Connector

Run the test script:

```bash
cd backend
python data/ingestion/newsapi_connector.py AAPL
```

Expected output:
```
============================================================
Testing News API Connector for AAPL
============================================================

Fetched X articles for AAPL

============================================================
First 3 articles:
============================================================

1. [Article Headline]
   Source: [News Source]
   URL: [Article URL]
   Time: [Timestamp]
```

### Test via API

1. Start your frontend (should already be running)
2. Search for a ticker like "AAPL" or "TSLA"
3. Check the backend logs to see which news source was used:
   - If Finnhub is configured: Uses Finnhub
   - If Finnhub fails/not configured: Falls back to News API
   - If News API fails/not configured: Falls back to Reddit

## Rate Limiting

The free tier allows **100 requests per day**. The connector implements rate limiting to prevent exceeding this limit:

- Minimum 1 second between requests
- Each ticker search = 1 request
- Market news fetch = 1 request

**Tips to stay within limits:**
- Use caching (already implemented in the app)
- Avoid excessive ticker searches during development
- Consider upgrading to Business plan for production use

## Troubleshooting

### "News API connector not enabled"

**Cause:** API key not found in environment

**Solution:**
1. Check `.env` file has `NEWSAPI_KEY=your_actual_key`
2. Restart backend server
3. Check for typos in the key

### "News API authentication failed"

**Cause:** Invalid or expired API key

**Solution:**
1. Log in to newsapi.org
2. Verify your API key
3. Generate a new key if needed
4. Update `.env` file

### "News API rate limit exceeded"

**Cause:** Made more than 100 requests in 24 hours

**Solution:**
1. Wait 24 hours for reset
2. Use caching to reduce requests
3. Consider upgrading to paid plan

### No news articles returned

**Possible causes:**
- Ticker symbol not found in news
- Search query too specific
- 24-hour delay on free tier (old news only)

**Solution:**
1. Try a different ticker (e.g., AAPL, TSLA, GOOGL)
2. Increase `hours_back` parameter (up to 48 hours)
3. Check backend logs for specific errors

## API Documentation

Full documentation: [newsapi.org/docs](https://newsapi.org/docs)

Key endpoints used:
- `/v2/everything` - For ticker-specific news search
- `/v2/top-headlines` - For general business news

## Upgrading

If you need real-time news or higher limits, consider upgrading:

- **Business Plan**: $449/month
  - 250,000 requests/month
  - Real-time articles
  - 5-year search depth

Visit [newsapi.org/pricing](https://newsapi.org/pricing) for details.

## Support

- News API Support: [newsapi.org/contact](https://newsapi.org/contact)
- Trade Strategy App: Check the main README.md
