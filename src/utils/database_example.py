"""
Example usage of MySQL database utility

This file demonstrates how to use the database utility for read and write operations.
"""

from utils.database import db

# Example 1: Read a single record
def get_user_by_id(user_id: int):
    query = "SELECT * FROM users WHERE id = %s"
    result = db.execute_query(query, (user_id,), fetch_one=True)
    return result

# Example 2: Read multiple records
def get_all_users():
    query = "SELECT * FROM users"
    results = db.execute_query(query)
    return results

# Example 3: Insert a new record
def create_user(name: str, email: str):
    query = "INSERT INTO users (name, email) VALUES (%s, %s)"
    inserted_id = db.execute_write(query, (name, email))
    return inserted_id

# Example 4: Update a record
def update_user(user_id: int, name: str):
    query = "UPDATE users SET name = %s WHERE id = %s"
    affected_rows = db.execute_write(query, (name, user_id))
    return affected_rows

# Example 5: Delete a record
def delete_user(user_id: int):
    query = "DELETE FROM users WHERE id = %s"
    affected_rows = db.execute_write(query, (user_id,))
    return affected_rows

# Example 6: Batch insert
def create_multiple_users(users_data):
    """
    users_data: List of tuples like [('John', 'john@example.com'), ('Jane', 'jane@example.com')]
    """
    query = "INSERT INTO users (name, email) VALUES (%s, %s)"
    affected_rows = db.execute_many(query, users_data)
    return affected_rows

# Example 7: Complex query with JOIN
def get_user_with_orders(user_id: int):
    query = """
        SELECT u.id, u.name, o.order_id, o.total 
        FROM users u 
        LEFT JOIN orders o ON u.id = o.user_id 
        WHERE u.id = %s
    """
    results = db.execute_query(query, (user_id,))
    return results

# Example 8: Test database connection
def check_database_connection():
    return db.test_connection()
