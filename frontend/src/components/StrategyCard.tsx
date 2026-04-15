import React from 'react';
import { ArrowUpCircle, ArrowDownCircle, MinusCircle } from 'lucide-react';

interface StrategyCardProps {
    strategyName: string;
    signal: number; // 1 = Buy, -1 = Sell, 0 = Neutral
    details?: any;
}

const StrategyCard: React.FC<StrategyCardProps> = ({ strategyName, signal, details }) => {
    console.log(`StrategyCard [${strategyName}] rendered. Signal: ${signal}`, details);

    let statusText = "Neutral";
    let Icon = MinusCircle;

    if (signal === 1) {
        statusText = "Buy";
        Icon = ArrowUpCircle;
    } else if (signal === -1) {
        statusText = "Sell";
        Icon = ArrowDownCircle;
    }

    return (
        <div className="strategy-card">
            <div className="card-header">
                <h4>{strategyName}</h4>
                <div className={`status-badge ${signal === 1 ? 'status-buy' : signal === -1 ? 'status-sell' : 'status-neutral'}`}>
                    <Icon size={20} />
                    <span>{statusText}</span>
                </div>
            </div>

            <div className="card-details">
                {details && Object.entries(details).map(([key, value]) => (
                    key !== 'signal' && key !== 'data' && (
                        <div key={key} className="detail-row">
                            <span className="capitalize">{key.replace('_', ' ')}:</span>
                            <span className="detail-value">{typeof value === 'number' ? value.toFixed(2) : String(value)}</span>
                        </div>
                    )
                ))}
            </div>
        </div>
    );
};

export default StrategyCard;
