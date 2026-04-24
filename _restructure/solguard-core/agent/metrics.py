# agent/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

alerts_total = Counter('solguard_alerts_total', 'Total alerts triggered', ['risk_level'])
programs_monitored = Gauge('solguard_programs_monitored', 'Number of programs under watch')
upgrade_events = Counter('solguard_upgrade_events_total', 'Program upgrade events detected')
claude_latency = Histogram('solguard_claude_latency_seconds', 'Claude API response time')

def start_metrics_server(port=8001):
    start_http_server(port)