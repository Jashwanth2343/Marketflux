import api from '@/lib/api';

export async function getExampleStrategy() {
    const { data } = await api.get('/backtest/example');
    return data.strategy;
}

export async function validateStrategy(strategy) {
    const { data } = await api.post('/backtest/validate', strategy);
    return data;
}

export async function runBacktest({ strategy, start, end, initial_capital = 100000, costs = null }) {
    const { data } = await api.post('/backtest/run', { strategy, start, end, initial_capital, costs });
    return data;
}

export async function runWalkForward({ strategy, start, end, initial_capital = 100000, train_months = 36, test_months = 12, step_months = null, costs = null }) {
    const { data } = await api.post('/backtest/walk-forward', { strategy, start, end, initial_capital, train_months, test_months, step_months, costs });
    return data;
}

export async function fetchBenchmark({ ticker = 'SPY', start, end, initial_capital = 100000 }) {
    const { data } = await api.post('/backtest/benchmark', { ticker, start, end, initial_capital });
    return data;
}

export async function runMonteCarlo({ trades, initial_capital, num_simulations = 500 }) {
    const { data } = await api.post('/backtest/monte-carlo', { trades, initial_capital, num_simulations });
    return data;
}

export async function aiCritique({ strategy, metrics, trades_summary }) {
    const { data } = await api.post('/backtest/ai-critique', { strategy, metrics, trades_summary });
    return data;
}

export async function aiParseStrategy({ description }) {
    const { data } = await api.post('/backtest/ai-parse-strategy', { description });
    return data;
}

export async function fetchMarketContext() {
    const { data } = await api.get('/backtest/market-context');
    return data;
}
