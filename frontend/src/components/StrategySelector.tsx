import React from 'react';

interface StrategySelectorProps {
    strategies: string[];
    selected: string[];
    onChange: (selected: string[]) => void;
}

const StrategySelector: React.FC<StrategySelectorProps> = ({ strategies, selected, onChange }) => {

    const handleCheckboxChange = (strategy: string) => {
        if (selected.includes(strategy)) {
            onChange(selected.filter(s => s !== strategy));
        } else {
            onChange([...selected, strategy]);
        }
    };

    const handleSelectAll = () => {
        if (selected.length === strategies.length) {
            onChange([]);
        } else {
            onChange([...strategies]);
        }
    };

    const isAllSelected = selected.length === strategies.length && strategies.length > 0;

    return (
        <div className="strategy-selector">
            <h3>Select Strategies</h3>
            <div className="checkbox-group">
                <label className="checkbox-label">
                    <input
                        type="checkbox"
                        checked={isAllSelected}
                        onChange={handleSelectAll}
                    />
                    <span>Select All</span>
                </label>
                {strategies.map(strategy => (
                    <label key={strategy} className="checkbox-label">
                        <input
                            type="checkbox"
                            checked={selected.includes(strategy)}
                            onChange={() => handleCheckboxChange(strategy)}
                        />
                        <span>{strategy}</span>
                    </label>
                ))}
            </div>
        </div>
    );
};

export default StrategySelector;
