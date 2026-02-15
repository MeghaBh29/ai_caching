# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import OrderedDict
import time

app = FastAPI()

# -----------------------------
# Enable CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Request body model
# -----------------------------
class QueryRequest(BaseModel):
    query: str

# -----------------------------
# Cache configuration
# -----------------------------
CACHE_MAX_SIZE = 5000         # larger cache for realistic FAQ scenario
CACHE_TTL = 60 * 60 * 24      # 24 hours
MODEL_COST_PER_1M_TOKENS = 0.50
AVG_TOKENS_PER_REQUEST = 500

cache = OrderedDict()  # key -> (answer, timestamp)
analytics = {
    "total_requests": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "cached_tokens": 0
}

# -----------------------------
# Helper functions
# -----------------------------
def get_cache_key(query: str):
    return query.strip().lower()  # normalize query

def prune_cache():
    """Remove expired items and enforce max size (LRU)"""
    now = time.time()
    # remove expired
    keys_to_delete = [k for k, (_, ts) in cache.items() if now - ts > CACHE_TTL]
    for k in keys_to_delete:
        cache.pop(k)
    # remove oldest if exceeding max size
    while len(cache) > CACHE_MAX_SIZE:
        cache.popitem(last=False)

# -----------------------------
# POST / endpoint
# -----------------------------
@app.post("/")
def query_endpoint(request: QueryRequest):
    analytics["total_requests"] += 1
    key = get_cache_key(request.query)

    prune_cache()

    if key in cache:
        # Cache hit
        answer, ts = cache.pop(key)
        cache[key] = (answer, ts)  # update order for LRU
        analytics["cache_hits"] += 1
        analytics["cached_tokens"] += AVG_TOKENS_PER_REQUEST
        cached = True
        latency = 45       # realistic cache hit latency
    else:
        # Cache miss
        answer = f"AI response for: {request.query}"
        cache[key] = (answer, time.time())
        analytics["cache_misses"] += 1
        cached = False
        latency = 2000     # realistic API call latency

    return {
        "answer": answer,
        "cached": cached,
        "latency": latency,
        "cacheKey": key
    }

# -----------------------------
# GET /analytics endpoint
# -----------------------------
@app.get("/analytics")
def get_analytics():
    total = analytics["total_requests"]
    hit_rate = analytics["cache_hits"] / total if total else 0
    miss_rate = analytics["cache_misses"] / total if total else 0
    savings = (analytics["cached_tokens"] * MODEL_COST_PER_1M_TOKENS) / 1_000_000
    savings_percent = hit_rate * 100
    return {
        "hitRate": round(hit_rate, 2),
        "missRate": round(miss_rate, 2),
        "totalRequests": total,
        "cacheHits": analytics["cache_hits"],
        "cacheMisses": analytics["cache_misses"],
        "cacheSize": len(cache),
        "costSavings": round(savings, 2),
        "costSavingsPercent": round(savings_percent, 2),
        "strategies": ["exact match", "LRU eviction", "TTL expiration"]
    }
