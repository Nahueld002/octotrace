"""Test database schema for sequences feature."""

import sqlite3
import tempfile
import os
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db, get_connection, _DB_PATH


def test_sequences_schema_creation():
    """Test that sequences tables are created correctly."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        db_module = sys.modules['src.db']
        db_module._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        # Check that tables exist
        with get_connection(read_only=True) as conn:
            # Check sequences table
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sequences'"
            ).fetchone()
            assert result is not None, "sequences table should exist"
            
            # Check sequence_jumps table
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sequence_jumps'"
            ).fetchone()
            assert result is not None, "sequence_jumps table should exist"
            
            # Check that indexes exist
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sequence_jumps'"
            ).fetchall()
            index_names = [idx[0] for idx in indexes]
            assert 'idx_jumps_sequence' in index_names, "idx_jumps_sequence index should exist"
            assert 'idx_jumps_txid' in index_names, "idx_jumps_txid index should exist"
            
            # Check table structure for sequences
            columns = conn.execute(
                "PRAGMA table_info(sequences)"
            ).fetchall()
            column_names = [col[1] for col in columns]
            expected_columns = ['id', 'name', 'description', 'created_at']
            for col in expected_columns:
                assert col in column_names, f"Column {col} should exist in sequences table"
            
            # Check table structure for sequence_jumps
            columns = conn.execute(
                "PRAGMA table_info(sequence_jumps)"
            ).fetchall()
            column_names = [col[1] for col in columns]
            expected_columns = ['id', 'sequence_id', 'txid', 'jump_number', 'notes', 'assigned_at']
            for col in expected_columns:
                assert col in column_names, f"Column {col} should exist in sequence_jumps table"
                
    finally:
        # Restore original database path
        db_module._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


def test_foreign_key_constraints():
    """Test that foreign key constraints work correctly."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        db_module = sys.modules['src.db']
        db_module._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        with get_connection() as conn:
            # Enable foreign key checking
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Try to insert a jump with a non-existent sequence_id
            try:
                conn.execute(
                    "INSERT INTO sequence_jumps (sequence_id, txid, jump_number) VALUES (?, ?, ?)",
                    (999, "test_txid", 1)
                )
                conn.commit()
                # If we get here, the foreign key constraint didn't work
                assert False, "Foreign key constraint should prevent inserting jump with non-existent sequence_id"
            except sqlite3.IntegrityError as e:
                # This is expected - foreign key constraint should be violated
                assert "FOREIGN KEY constraint failed" in str(e)
                
    finally:
        # Restore original database path
        db_module._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


def test_unique_constraints():
    """Test that unique constraints work correctly."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        db_module = sys.modules['src.db']
        db_module._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        with get_connection() as conn:
            # Enable foreign key checking
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Insert a sequence first
            conn.execute(
                "INSERT INTO sequences (name, description) VALUES (?, ?)",
                ("Test Sequence", "A test sequence")
            )
            sequence_id = conn.execute("SELECT id FROM sequences").fetchone()[0]
            
            # Insert a test transaction to reference
            conn.execute(
                """INSERT INTO transactions 
                   (txid, chain, from_address, to_address, amount, datetime_utc, token_symbol, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("test_txid", "ETH", "from_addr", "to_addr", "100.0", "2023-01-01T00:00:00Z", "USDT", "{}")
            )
            
            # Insert a jump
            conn.execute(
                "INSERT INTO sequence_jumps (sequence_id, txid, jump_number) VALUES (?, ?, ?)",
                (sequence_id, "test_txid", 1)
            )
            
            # Try to insert another jump with the same sequence_id and jump_number
            try:
                conn.execute(
                    "INSERT INTO sequence_jumps (sequence_id, txid, jump_number) VALUES (?, ?, ?)",
                    (sequence_id, "test_txid_2", 1)
                )
                conn.commit()
                # If we get here, the unique constraint didn't work
                assert False, "Unique constraint should prevent inserting jumps with same sequence_id and jump_number"
            except sqlite3.IntegrityError as e:
                # This is expected - unique constraint should be violated
                assert "UNIQUE constraint failed" in str(e)
                
    finally:
        # Restore original database path
        db_module._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


if __name__ == "__main__":
    test_sequences_schema_creation()
    test_foreign_key_constraints()
    test_unique_constraints()
    print("All database tests passed!")