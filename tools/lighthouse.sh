#!/bin/sh
# Lighthouse mobile audits (performance + accessibility) for the home and
# results pages. Run inside the e2e container:
#   docker compose --profile test run --rm e2e sh tools/lighthouse.sh
set -e
BASE="${BASE_URL:-http://localhost:8095}"
OUT=test-results/lighthouse
mkdir -p "$OUT"
for page in "home:/" "results:/near/46052" "state:/state/in/"; do
  name="${page%%:*}"; path="${page#*:}"
  lighthouse "$BASE$path" --quiet --only-categories=performance,accessibility \
    --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
    --output=json --output=html --output-path="$OUT/$name" >/dev/null 2>&1 || true
  python3 - "$OUT/$name.report.json" "$name" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
c = r["categories"]; a = r["audits"]
print(f"{sys.argv[2]:8} performance {round(c['performance']['score']*100):3}  accessibility {round(c['accessibility']['score']*100):3}"
      f"  FCP {a['first-contentful-paint']['displayValue']}  LCP {a['largest-contentful-paint']['displayValue']}"
      f"  TBT {a['total-blocking-time']['displayValue']}  CLS {a['cumulative-layout-shift']['displayValue']}")
PY
done
