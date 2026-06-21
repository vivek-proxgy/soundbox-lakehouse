"""Linear trend forecasting mathematical engine for Copilot metrics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
import pandas as pd


def forecast_next_days(df_daily: pd.DataFrame, target_days: int = 7) -> List[Dict[str, Any]]:
    """Generate linear trend forecast for next N days based on daily GMV."""
    if df_daily.empty or len(df_daily) < 2:
        return []

    # Sort to ensure sequential day numbers
    df_daily = df_daily.sort_values('date').reset_index(drop=True)
    df_daily['day_num'] = df_daily.index

    # Calculate linear regression parameters: y = mx + c
    n = len(df_daily)
    x = df_daily['day_num']
    y = df_daily['gmv']

    sum_x = x.sum()
    sum_y = y.sum()
    sum_xx = (x ** 2).sum()
    sum_xy = (x * y).sum()

    denominator = (n * sum_xx - sum_x ** 2)
    if denominator == 0:
        slope = 0.0
        intercept = y.mean()
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

    last_date = pd.to_datetime(df_daily['date'].iloc[-1])
    last_day_num = df_daily['day_num'].iloc[-1]

    forecast = []
    for i in range(1, target_days + 1):
        future_day = last_day_num + i
        future_date = (last_date + timedelta(days=i)).strftime('%Y-%m-%d')
        predicted_gmv = max(0.0, slope * future_day + intercept)
        forecast.append({
            "date": future_date,
            "predicted_gmv": round(predicted_gmv, 2)
        })
    return forecast
