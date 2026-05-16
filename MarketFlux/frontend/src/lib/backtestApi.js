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
