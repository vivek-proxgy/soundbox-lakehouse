"""Deterministic template formatter fallback for Chanakya Copilot answers."""

from __future__ import annotations

import json
from typing import Any, Dict


def generate_template_fallback(intent: str, prompt: str, context: Dict[str, Any]) -> str:
    """Generate structured, highly professional markdown format responses directly from the data context."""
    if not context:
        return "No matching records found in the database. Please verify your query filters."

    if intent == "daily_brief":
        return f"""### Soundbox Portfolio Daily Brief
Here is the operational summary of your active Soundbox portfolio:
* **Total Merchants**: {context.get('total_merchants', 0):,} ({context.get('active_merchants', 0):,} currently active)
* **Total GMV**: INR {context.get('total_gmv', 0.0):,.2f} across {context.get('total_transactions', 0):,} transactions
* **Network Latency**: Average transaction latency is **{context.get('average_latency_seconds', 0.0):.2f}s**
* **Fleet Health**: Average signal strength is **{context.get('average_signal_strength', 0.0):.1f} dBm** with **{context.get('low_battery_devices', 0)}** critical battery warnings (<3.5V)."""

    elif intent == "merchant_profile":
        results = context.get("search_results", [])
        lines = [f"### Merchant Profile Search Results (Found {len(results)} matches)"]
        for m in results:
            lines.append(f"""* **{m['name']}** (ID: `{m['id']}`)
  - **Location**: {m['city']}, {m['state']}
  - **Contact**: {m['email']} | {m['phone']}
  - **Status**: {m['merchant_activity_status'].upper()} (Linked Device: `{m['device_id']}`)""")
        return "\n".join(lines)

    elif intent == "merchant_risk":
        prof = context.get("profile", {})
        metrics = context.get("transaction_metrics", {})
        tele = context.get("latest_telemetry", {})
        if not prof:
            return "Merchant details not found."
        return f"""### Merchant Risk Diagnostics: {prof['name']} (ID: `{prof['id']}`)
* **Operational Status**: {prof['merchant_activity_status'].upper()}
* **Transaction Summary**:
  - Total Transactions: **{metrics.get('tx_count', 0):,}**
  - Portfolio GMV: **INR {metrics.get('gmv', 0.0):,.2f}**
  - Average Latency: **{metrics.get('avg_latency', 0.0):.2f} seconds**
* **Linked Device Health**:
  - Device ID: `{prof['device_id']}`
  - Battery: **{tele.get('battery_voltage', 'N/A')} mV** (Charging: {str(tele.get('charger', False))})
  - Signal strength: **{tele.get('signal_strength', 'N/A')} dBm**"""

    elif intent == "fleet_health":
        return f"""### Fleet Operational Health Summary
An analysis of device telemetry metrics reveals the following fleet distribution:
* **Total Tracked Devices**: {context.get('total_devices', 0):,}
* **Battery Degradation**:
  - Critical (<3.5V): **{context.get('critical_battery', 0)}** devices
  - Warning (3.5V - 3.7V): **{context.get('warning_battery', 0)}** devices
* **Signal Offline Risk**: **{context.get('critical_signal', 0)}** devices reporting extremely weak signals (<10 dBm)
* **Charging Stations**: **{context.get('charging_count', 0)}** devices are actively plugged into a charger."""

    elif intent == "gmv_trend":
        hist = context.get("historical_daily_gmv", [])
        fore = context.get("seven_day_forecast", [])
        lines = ["### Portfolio GMV Trend Analysis & Linear Projection"]
        if hist:
            lines.append(f"* **Historical Analysis**: Fetched daily metrics over the last {len(hist)} days.")
            lines.append(f"  - Peak Daily GMV: **INR {max(h['gmv'] for h in hist):,.2f}**")
            lines.append(f"  - Total Period GMV: **INR {sum(h['gmv'] for h in hist):,.2f}**")
        if fore:
            lines.append("\n* **7-Day Trend Forecast (Linear Regression Projection)**:")
            for f in fore:
                lines.append(f"  - {f['date']}: Projected GMV **INR {f['predicted_gmv']:,.2f}**")
        else:
            lines.append("\n* **Forecast**: Insufficient historical data to construct a regression curve.")
        return "\n".join(lines)

    return f"Retrieved Context: {json.dumps(context, indent=2)}"
