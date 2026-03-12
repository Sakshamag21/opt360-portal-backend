import mysql.connector
from mysql.connector import Error, pooling
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
import logging
from config.config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MySQLDatabase:
    """MySQL Database utility class for read and write operations"""
    
    def __init__(self):
        """Initialize database connection pool"""
        self.pool = None
        self._create_connection_pool()
    
    def _create_connection_pool(self):
        """Create a connection pool for efficient database connections"""
        try:
            db_config = config.database
            
            pool_config = {
                "pool_name": "operator360_pool",
                "pool_size": 5,
                "pool_reset_session": True,
                "host": db_config.get("host", "localhost"),
                "port": db_config.get("port", 3306),
                "database": db_config.get("name", "operator360"),
                "user": db_config.get("username", "root"),
                "password": db_config.get("password", "")
            }
            
            self.pool = pooling.MySQLConnectionPool(**pool_config)
            logger.info("Database connection pool created successfully")
            
        except Error as e:
            logger.error(f"Error creating connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = None
        try:
            connection = self.pool.get_connection()
            yield connection
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    def execute_query(
        self, 
        query: str, 
        params: Optional[Tuple] = None,
        fetch_one: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SELECT query and return results
        
        Args:
            query: SQL SELECT query
            params: Query parameters (optional)
            fetch_one: If True, return only one record
            
        Returns:
            List of dictionaries containing query results, or None if error
        """
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(query, params or ())
                
                if fetch_one:
                    result = cursor.fetchone()
                    cursor.close()
                    return result
                else:
                    results = cursor.fetchall()
                    cursor.close()
                    return results
                    
        except Error as e:
            logger.error(f"Error executing query: {e}")
            logger.error(f"Query: {query}")
            return None
    
    def execute_write(
        self, 
        query: str, 
        params: Optional[Tuple] = None
    ) -> Optional[int]:
        """
        Execute an INSERT, UPDATE, or DELETE query
        
        Args:
            query: SQL INSERT/UPDATE/DELETE query
            params: Query parameters (optional)
            
        Returns:
            Last inserted ID for INSERT, affected rows for UPDATE/DELETE, or None if error
        """
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(query, params or ())
                connection.commit()
                
                # Return last inserted ID for INSERT, affected rows for UPDATE/DELETE
                last_id = cursor.lastrowid if cursor.lastrowid > 0 else cursor.rowcount
                cursor.close()
                
                logger.info(f"Write operation successful. Affected/Inserted ID: {last_id}")
                return last_id
                
        except Error as e:
            logger.error(f"Error executing write operation: {e}")
            logger.error(f"Query: {query}")
            return None
    
    def execute_many(
        self, 
        query: str, 
        data: List[Tuple]
    ) -> Optional[int]:
        """
        Execute multiple INSERT/UPDATE operations efficiently
        
        Args:
            query: SQL INSERT/UPDATE query with placeholders
            data: List of tuples containing data for each operation
            
        Returns:
            Number of affected rows, or None if error
        """
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.executemany(query, data)
                connection.commit()
                
                affected_rows = cursor.rowcount
                cursor.close()
                
                logger.info(f"Batch write operation successful. Affected rows: {affected_rows}")
                return affected_rows
                
        except Error as e:
            logger.error(f"Error executing batch operation: {e}")
            logger.error(f"Query: {query}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with self.get_connection() as connection:
                if connection.is_connected():
                    logger.info("Database connection test successful")
                    return True
                return False
        except Error as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Singleton instance
db = MySQLDatabase()

