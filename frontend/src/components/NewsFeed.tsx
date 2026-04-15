import React, { useState } from 'react';

interface NewsArticle {
    headline: string;
    summary: string;
    source: string;
    datetime: number;
    url: string;
    sentiment_score?: number | null;
    upvotes?: number;  // For Reddit
    engagement?: number;  // For Twitter
}

interface NewsFeedProps {
    articles: NewsArticle[];
}

const NewsFeed: React.FC<NewsFeedProps> = ({ articles }) => {
    const [selectedSource, setSelectedSource] = useState<string>('all');

    // Get unique sources
    const sources = ['all', ...new Set(articles.map(a => {
        if (a.source.startsWith('r/')) return 'Reddit';
        return a.source;
    }))];

    // Filter articles by source
    const filteredArticles = selectedSource === 'all'
        ? articles
        : articles.filter(a => {
            if (selectedSource === 'Reddit') return a.source.startsWith('r/');
            return a.source === selectedSource;
        });

    // Format timestamp
    const formatTime = (timestamp: number) => {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

        if (diffHours < 1) {
            const diffMins = Math.floor(diffMs / (1000 * 60));
            return `${diffMins}m ago`;
        } else if (diffHours < 24) {
            return `${diffHours}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    };

    // Get sentiment badge
    const getSentimentBadge = (score: number | null | undefined) => {
        if (score === null || score === undefined) {
            return <span className="sentiment-badge neutral">Analyzing...</span>;
        }

        if (score > 0.3) {
            return <span className="sentiment-badge positive">😊 Positive</span>;
        } else if (score < -0.3) {
            return <span className="sentiment-badge negative">😟 Negative</span>;
        } else {
            return <span className="sentiment-badge neutral">😐 Neutral</span>;
        }
    };

    return (
        <div className="news-feed">
            <div className="news-feed-header">
                <h3>Recent News & Sentiment</h3>
                <div className="source-filters">
                    {sources.map(source => (
                        <button
                            key={source}
                            className={`filter-btn ${selectedSource === source ? 'active' : ''}`}
                            onClick={() => setSelectedSource(source)}
                        >
                            {source}
                        </button>
                    ))}
                </div>
            </div>

            <div className="news-list">
                {filteredArticles.length === 0 ? (
                    <div className="no-news">No news articles available</div>
                ) : (
                    filteredArticles.map((article, index) => (
                        <div key={index} className="news-item">
                            <div className="news-item-header">
                                <span className="news-source">{article.source}</span>
                                <span className="news-time">{formatTime(article.datetime)}</span>
                                {getSentimentBadge(article.sentiment_score)}
                            </div>

                            <h4 className="news-headline">
                                <a
                                    href={article.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="news-link"
                                >
                                    {article.headline}
                                </a>
                            </h4>

                            {article.summary && (
                                <p className="news-summary">{article.summary.slice(0, 200)}...</p>
                            )}

                            {(article.upvotes || article.engagement) && (
                                <div className="news-engagement">
                                    {article.upvotes && (
                                        <span className="engagement-stat">
                                            ↑ {article.upvotes} upvotes
                                        </span>
                                    )}
                                    {article.engagement && (
                                        <span className="engagement-stat">
                                            ♥ {article.engagement} engagement
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default NewsFeed;
