"""Opt-in local HTTP health probe; explicitly allowed URLs only (no public URL scanner)."""
import argparse
import time
import httpx

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--service-id", type=int, required=True)
    p.add_argument("--url", required=True, help="Health endpoint you own or are authorized to monitor")
    p.add_argument("--token", required=True)
    p.add_argument("--interval", type=int, default=20)
    args=p.parse_args()
    if args.interval < 5: p.error("interval must be >= 5 seconds")
    with httpx.Client(timeout=5, follow_redirects=False) as client:
        while True:
            begin=time.monotonic()
            try:
                result=client.get(args.url)
                ok=200<=result.status_code<400
            except httpx.HTTPError:
                ok=False
            elapsed=round((time.monotonic()-begin)*1000,2)
            response=client.post(f"{args.api}/api/services/{args.service_id}/samples",headers={"X-Ingest-Token":args.token},json={"ok":ok,"latency_ms":elapsed})
            response.raise_for_status()
            print(f"ok={ok} latency_ms={elapsed}", flush=True)
            time.sleep(args.interval)

if __name__=="__main__":main()
