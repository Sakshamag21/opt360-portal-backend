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
    with _global_lock:
        if cache_key not in _cache_locks:
            _cache_locks[cache_key] = threading.Lock()
        return _cache_locks[cache_key]

def _log_cache_state():
    with _global_lock:
        cache_items = len(_cache_store)
        cache_size_bytes = sum(v.get('size', 0) for v in _cache_store.values())
        cache_size_mb = cache_size_bytes / (1024 * 1024)
    logger.info(f"📦 Cache State: {cache_items} items | Size: {cache_size_mb:.4f} MB")

def _cleanup_cache():
    with _global_lock:
        current_time = time.time()
        expired_keys = [k for k, v in _cache_store.items() if current_time > v['expiry']]
        for k in expired_keys:
            del _cache_store[k]
            if k in _cache_locks:
                del _cache_locks[k]
        
        total_size = sum(v['size'] for v in _cache_store.values())
        if total_size > MAX_CACHE_BYTES:
            sorted_keys = sorted(_cache_store.keys(), key=lambda k: _cache_store[k]['accessed'])
            for k in sorted_keys:
                if total_size <= MAX_CACHE_BYTES:
                    break
                total_size -= _cache_store[k]['size']
                del _cache_store[k]
                if k in _cache_locks:
                    del _cache_locks[k]
# ==========================================


def get_all_sids_date(opt_id: str, date_str: str, limit: int = 50, page: int = 1):
    start_time = time.time()
    
    rocksdb_config_operator_store = config.get('rocksdb_operator_store')
    if not rocksdb_config_operator_store:
        logger.error("Fallback triggered: RocksDB configuration missing")
        return Response.error("RocksDB configuration missing")

    endpoint = rocksdb_config_operator_store.get('endpoint') 
    endpoint_url = f"http://{rocksdb_config_operator_store.get('host')}:{rocksdb_config_operator_store.get('port')}{endpoint}"
    
    date_str_clean = date_str.replace('-', '')
    cache_key = f"sids:{opt_id}:{date_str_clean}"

    try:
        logger.info(f"--- Starting execution for opt_id={opt_id}, date={date_str_clean}, page={page} ---")
        _log_cache_state()
        _cleanup_cache()

        # 1. First cache check
        all_sids = None
        with _global_lock:
            cached_item = _cache_store.get(cache_key)
            if cached_item:
                if time.time() <= cached_item['expiry']:
                    all_sids = cached_item['data']
                    cached_item['accessed'] = time.time()
                else:
                    del _cache_store[cache_key]

        # 2. If cache missed, acquire lock to fetch from RocksDB
        if all_sids is None:
            fetch_lock = get_fetch_lock(cache_key)
            with fetch_lock:
                with _global_lock:
                    cached_item = _cache_store.get(cache_key)
                    if cached_item and time.time() <= cached_item['expiry']:
                        all_sids = cached_item['data']
                        cached_item['accessed'] = time.time()
                        logger.info(f"Data fetched by another thread while waiting. Using cache.")

                if all_sids is None:
                    logger.info(f"Cache miss for {cache_key}. Fetching from RocksDB.")
                    payload = {"opt_id": opt_id, "date": date_str_clean}
                    headers = {"Content-Type": "application/json"}
                    
                    response = requests.post(endpoint_url, json=payload, headers=headers, timeout=15)
                    if response.status_code != 200:
                        return Response.error(f"Operator store request failed with status {response.status_code}")
                    
                    try:
                        data = response.json()
                    except ValueError as json_err:
                        return Response.error("Invalid JSON response from Operator store")
                    
                    records = data.get("results", [])
                    all_sids = []
                    for record in records:
                        if isinstance(record, str):
                            all_sids.append(record)
                        elif isinstance(record, dict) and record.get('sid') is not None:
                            all_sids.append(record.get('sid'))

                    data_bytes = len(json.dumps(all_sids).encode('utf-8'))
                    with _global_lock:
                        _cache_store[cache_key] = {
                            'data': all_sids,
                            'expiry': time.time() + 300,
                            'accessed': time.time(),
                            'size': data_bytes
                        }
                    _cleanup_cache()

        # 3. Handle Empty Case
        if not all_sids:
            logger.warning(f"No SIDs found for opt_id={opt_id}, date={date_str_clean}.")
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ Total execution time: {elapsed_time:.4f} seconds")
            return Response.success(
                f"No SIDs found for the operator id: {opt_id}, date={date_str_clean}",
                {"sids": [], "total_sids": 0, "total_pages": 0, "current_page": page, "has_more": False}
            )

        # 4. Pagination Math (Offset logic)
        total_sids = len(all_sids)
        total_pages = (total_sids + limit - 1) // limit  # Ceiling division
        start_index = (page - 1) * limit
        end_index = start_index + limit

        # 5. Slice the list for the current page
        page_sids = all_sids[start_index : end_index]

        # If page requested is out of bounds (e.g., page 5 of 3)
        if not page_sids:
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ Total execution time: {elapsed_time:.4f} seconds")
            return Response.success(
                "No more SIDs to fetch", 
                {"sids": [], "total_sids": total_sids, "total_pages": total_pages, "current_page": page, "has_more": False}
            )

        logger.info(f"Successfully fetched {len(page_sids)} SIDs for page {page}. Proceeding to Step 2.")
        
        # --- INTEGRATED GET_SID_DETAILS CALL ---
        sid_details_response = get_sid_details(page_sids)
        print(sid_details_response,'sid details response')
        details_data = {}
        if hasattr(sid_details_response, 'data') and isinstance(sid_details_response.data, dict):
            details_data = sid_details_response.data
        elif isinstance(sid_details_response, dict): 
            details_data = sid_details_response.get('data', {})
        
        details_map = {}
        sids_info = details_data.get("sids_info", [])
        if sids_info:
            for sid_info in sids_info:
                sid_value = sid_info.get('sid')
                if sid_value is not None:
                    details_map[sid_value] = sid_info
        
        print(details_map,'details data')
        print(page_sids, 'page sids')
        # Build final response list
        sid_det = []
        for sid in page_sids:
            if sid in details_map:
                sid_det.append({'sid': sid, **details_map[sid]})
            else:
                sid_det.append({'sid': sid}) 

        _log_cache_state()
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️ Total execution time: {elapsed_time:.4f} seconds")

        return Response.success(
            f"SIDs and details retrieved successfully for operator id: {opt_id}, date={date_str_clean}",
            {
                "sids": sid_det,
                "total_sids": total_sids,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": len(page_sids)
            }
        )
            
    except requests.exceptions.Timeout:
        return Response.error("Request to Operator store timed out")
    except requests.exceptions.RequestException as req_err:
        return Response.error(f"Failed to connect to Operator store: {str(req_err)}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return Response.error(f"An unexpected error occurred: {str(e)}")