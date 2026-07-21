import logging
import time
import threading
import json
from typing import Dict, Any, List
import requests
from utils.response import Response
from enums.queries import OperatorDetailQueries as Queries
from utils.database import db
from config.config import config
from opt_details.info import get_operator_details
from datetime import datetime, timezone
from sid_details.info import get_sid_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# LRU + MEMORY + TTL CACHE DEFINITIONS
# ==========================================
_cache_store = {}
_cache_locks = {}
_global_lock = threading.Lock()
MAX_CACHE_BYTES = 5 * 1024 * 1024  # 5 MB Limit

def get_fetch_lock(cache_key: str):
    """Gets or creates a specific lock for a cache key to prevent thundering herd."""
    with _global_lock:
        if cache_key not in _cache_locks:
            _cache_locks[cache_key] = threading.Lock()
        return _cache_locks[cache_key]

def _log_cache_state():
    """Logs the current item count and memory size of the cache."""
    with _global_lock:
        cache_items = len(_cache_store)
        cache_size_bytes = sum(v.get('size', 0) for v in _cache_store.values())
        cache_size_mb = cache_size_bytes / (1024 * 1024)
    logger.info(f"📦 Cache State: {cache_items} items | Size: {cache_size_mb:.4f} MB")

def _cleanup_cache():
    """Synchronously cleans up expired TTL items and enforces 5MB memory limit (LRU)."""
    with _global_lock:
        current_time = time.time()
        
        # 1. Remove Expired Items (TTL)
        expired_keys = [k for k, v in _cache_store.items() if current_time > v['expiry']]
        for k in expired_keys:
            del _cache_store[k]
            if k in _cache_locks:
                del _cache_locks[k]
        
        # 2. Enforce Memory Limit (LRU)
        total_size = sum(v['size'] for v in _cache_store.values())
        
        if total_size > MAX_CACHE_BYTES:
            # Sort keys by 'accessed' time (oldest first)
            sorted_keys = sorted(_cache_store.keys(), key=lambda k: _cache_store[k]['accessed'])
            
            for k in sorted_keys:
                if total_size <= MAX_CACHE_BYTES:
                    break # We are back under 5MB, stop deleting
                
                total_size -= _cache_store[k]['size']
                del _cache_store[k]
                if k in _cache_locks:
                    del _cache_locks[k]
# ==========================================


def get_all_sids_date(opt_id: str, date_str: str, limit: int = 50, cursor: str = None):
    # Start Timer
    start_time = time.time()
    
    rocksdb_config_operator_store = config.get('rocksdb_operator_store')
    if not rocksdb_config_operator_store:
        logger.error("Fallback triggered: RocksDB configuration missing")
        return Response.error("RocksDB configuration missing")

    endpoint = rocksdb_config_operator_store.get('endpoint') 
    endpoint_url = f"http://{rocksdb_config_operator_store.get('host')}:{rocksdb_config_operator_store.get('port')}{endpoint}"
    logger.info(f"Step 1: Connecting to RocksDB Operator store endpoint: {endpoint_url}")
    
    date_str_clean = date_str.replace('-', '')
    cache_key = f"sids:{opt_id}:{date_str_clean}"

    try:
        # 0. Log Initial Cache State & Trigger Cleanup
        logger.info(f"--- Starting execution for opt_id={opt_id}, date={date_str_clean} ---")
        _log_cache_state()
        _cleanup_cache()

        # 1. First cache check (fast)
        all_sids = None
        with _global_lock:
            cached_item = _cache_store.get(cache_key)
            if cached_item:
                if time.time() <= cached_item['expiry']:
                    all_sids = cached_item['data']
                    cached_item['accessed'] = time.time() # Update LRU timestamp
                else:
                    # Expired, remove it
                    del _cache_store[cache_key]

        # 2. If cache missed, acquire lock to fetch from RocksDB
        if all_sids is None:
            fetch_lock = get_fetch_lock(cache_key)
            
            with fetch_lock:
                # Double-check lock inside
                with _global_lock:
                    cached_item = _cache_store.get(cache_key)
                    if cached_item and time.time() <= cached_item['expiry']:
                        all_sids = cached_item['data']
                        cached_item['accessed'] = time.time()
                        logger.info(f"Data fetched by another thread while waiting. Using cache for {cache_key}.")

                if all_sids is None:
                    logger.info(f"Cache miss for {cache_key}. Fetching from RocksDB.")
                    payload = {
                        "opt_id": opt_id,
                        "date": date_str_clean
                    }
                    headers = {"Content-Type": "application/json"}
                    
                    response = requests.post(endpoint_url, json=payload, headers=headers, timeout=15)
                    
                    if response.status_code != 200:
                        logger.error(f"Fallback triggered: Operator store returned non-200 status code: {response.status_code}. Response: {response.text}")
                        return Response.error(f"Operator store request failed with status {response.status_code}")
                    
                    try:
                        data = response.json()
                    except ValueError as json_err:
                        logger.error(f"Fallback triggered: Failed to decode JSON from Operator store. Error: {json_err}. Raw response: {response.text}")
                        return Response.error("Invalid JSON response from Operator store")
                    
                    records = data.get("Results", [])
                    
                    # Normalize to list of strings
                    all_sids = []
                    for record in records:
                        if isinstance(record, str):
                            all_sids.append(record)
                        elif isinstance(record, dict) and record.get('sid') is not None:
                            all_sids.append(record.get('sid'))

                    # Save to cache with TTL of 300 seconds (5 minutes)
                    # Calculate exact byte size of the data for memory tracking
                    data_bytes = len(json.dumps(all_sids).encode('utf-8'))
                    
                    with _global_lock:
                        _cache_store[cache_key] = {
                            'data': all_sids,
                            'expiry': time.time() + 300,
                            'accessed': time.time(),
                            'size': data_bytes
                        }
                    
                    # Run cleanup again after inserting large data to ensure we didn't breach 5MB
                    _cleanup_cache()

        # 3. Handle Empty Case
        if not all_sids:
            logger.warning(f"Fallback triggered: No SIDs found for opt_id={opt_id}, date={date_str_clean}.")
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ Total execution time: {elapsed_time:.4f} seconds")
            return Response.success(
                f"No SIDs found for the operator id: {opt_id}, date={date_str_clean}",
                {"sids": [], "next_cursor": None, "total_sids": 0}
            )

        # 4. Pagination: Find starting index based on cursor
        start_index = 0
        if cursor:
            try:
                start_index = all_sids.index(cursor) + 1
            except ValueError:
                logger.warning(f"Invalid cursor {cursor} for {cache_key}. Starting from 0.")
                start_index = 0

        # 5. Pagination: Slice the list for the current page
        page_sids = all_sids[start_index : start_index + limit]

        # If we've gone past the end of the list
        if not page_sids:
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ Total execution time: {elapsed_time:.4f} seconds")
            return Response.success(
                "No more SIDs to fetch", 
                {"sids": [], "next_cursor": None, "total_sids": len(all_sids)}
            )

        logger.info(f"Successfully fetched {len(page_sids)} SIDs for this page. Proceeding to Step 2: Fetching SID details.")
        
        # --- INTEGRATED GET_SID_DETAILS CALL ---
        sid_details_response = get_sid_details(page_sids)
        
        details_data = {}
        if hasattr(sid_details_response, 'data') and isinstance(sid_details_response.data, dict):
            details_data = sid_details_response.data
        elif isinstance(sid_details_response, dict): 
            details_data = sid_details_response.get('data', {})
        
        sids_info = details_data.get("sids_info", [])

        # Build lookup map for this page only
        details_map = {}
        for sid_info in sids_info:
            sid_value = sid_info.get('sid')
            if sid_value:
                values = sid_info.get('values', [])
                value_entry = values[0] if values else {}
                details_map[sid_value] = value_entry

        # Build final response list
        sid_det = []
        for sid in page_sids:
            if sid in details_map:
                sid_det.append({'sid': sid, **details_map[sid]})
            else:
                sid_det.append({'sid': sid}) 

        # 6. Determine next cursor
        next_cursor = None
        if len(page_sids) == limit and (start_index + limit) < len(all_sids):
            next_cursor = page_sids[-1]

        # Log final cache state and execution time
        _log_cache_state()
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️ Total execution time: {elapsed_time:.4f} seconds")

        return Response.success(
            f"SIDs and details retrieved successfully for operator id: {opt_id}, date={date_str_clean}",
            {
                "sids": sid_det,
                "next_cursor": next_cursor,
                "total_sids": len(all_sids),
                "page_size": len(page_sids)
            }
        )
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        logger.error(f"Fallback triggered: Request timed out while connecting to Operator endpoint {endpoint_url}. Executed in {elapsed_time:.4f}s")
        return Response.error("Request to Operator store timed out")
        
    except requests.exceptions.RequestException as req_err:
        elapsed_time = time.time() - start_time
        logger.error(f"Fallback triggered: Network error occurred while fetching SIDs. Error: {req_err}. Executed in {elapsed_time:.4f}s")
        return Response.error(f"Failed to connect to Operator store: {str(req_err)}")
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"Fallback triggered: An unexpected error occurred while fetching SIDs. Error: {e}. Executed in {elapsed_time:.4f}s")
        return Response.error(f"An unexpected error occurred: {str(e)}")