"""Test API endpoints for sequences feature."""

import sys
from pathlib import Path
import tempfile
import os
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.web.main import app
from src.db import init_db, get_connection, _DB_PATH

# Create a test client
client = TestClient(app)

def test_sequences_crud():
    """Test CRUD operations for sequences."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        import src.db
        src.db._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        # Test creating a sequence
        response = client.post("/api/sequences", json={
            "name": "Test Sequence",
            "description": "A test sequence for transactions"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        sequence_id = data["id"]
        
        # Test getting the sequence
        response = client.get(f"/api/sequences/{sequence_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Sequence"
        assert data["description"] == "A test sequence for transactions"
        assert len(data["jumps"]) == 0
        
        # Test listing sequences
        response = client.get("/api/sequences")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Sequence"
        assert data[0]["jump_count"] == 0
        
        # Test updating a sequence
        response = client.put(f"/api/sequences/{sequence_id}", json={
            "name": "Updated Sequence",
            "description": "An updated test sequence"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify update
        response = client.get(f"/api/sequences/{sequence_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Sequence"
        assert data["description"] == "An updated test sequence"
        
        # Test deleting a sequence
        response = client.delete(f"/api/sequences/{sequence_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify deletion
        response = client.get(f"/api/sequences/{sequence_id}")
        assert response.status_code == 404
        
    finally:
        # Restore original database path
        src.db._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


def test_jumps_crud():
    """Test CRUD operations for jumps."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        import src.db
        src.db._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        # Insert a test transaction first
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO transactions 
                (txid, chain, from_address, to_address, amount, datetime_utc, token_symbol, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("test_txid_123", "ETH", "from_addr", "to_addr", "100.0", "2023-01-01T00:00:00Z", "USDT", "{}"))
            conn.commit()
        
        # Create a sequence
        response = client.post("/api/sequences", json={
            "name": "Test Sequence",
            "description": "A test sequence for transactions"
        })
        assert response.status_code == 200
        data = response.json()
        sequence_id = data["id"]
        
        # Test creating a jump
        response = client.post(f"/api/sequences/{sequence_id}/jumps", json={
            "txid": "test_txid_123",
            "jump_number": 1,
            "notes": "First jump"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        jump_id = data["jump_id"]
        
        # Verify jump was created
        response = client.get(f"/api/sequences/{sequence_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jumps"]) == 1
        assert data["jumps"][0]["jump_number"] == 1
        assert data["jumps"][0]["notes"] == "First jump"
        
        # Test updating a jump
        response = client.patch(f"/api/jumps/{jump_id}", json={
            "jump_number": 2
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify update
        response = client.get(f"/api/sequences/{sequence_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jumps"]) == 1
        assert data["jumps"][0]["jump_number"] == 2
        
        # Test deleting a jump
        response = client.delete(f"/api/jumps/{jump_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify deletion
        response = client.get(f"/api/sequences/{sequence_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jumps"]) == 0
        
    finally:
        # Restore original database path
        src.db._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


def test_sequence_reports():
    """Test sequence report generation."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        import src.db
        src.db._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        # Insert a test transaction
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO transactions 
                (txid, chain, from_address, to_address, amount, datetime_utc, token_symbol, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("test_txid_123", "ETH", "from_addr", "to_addr", "100.0", "2023-01-01T00:00:00Z", "USDT", "{}"))
            conn.commit()
        
        # Create a sequence
        response = client.post("/api/sequences", json={
            "name": "Test Sequence",
            "description": "A test sequence for transactions"
        })
        assert response.status_code == 200
        data = response.json()
        sequence_id = data["id"]
        
        # Add a jump
        response = client.post(f"/api/sequences/{sequence_id}/jumps", json={
            "txid": "test_txid_123",
            "jump_number": 1,
            "notes": "First jump"
        })
        assert response.status_code == 200
        
        # Test text report
        response = client.get(f"/api/sequences/{sequence_id}/report?format=text")
        assert response.status_code == 200
        data = response.json()
        assert "report" in data
        assert "Test Sequence" in data["report"]
        assert "test_txid_123" in data["report"]
        
        # Test JSON report
        response = client.get(f"/api/sequences/{sequence_id}/report?format=json")
        assert response.status_code == 200
        data = response.json()
        assert "sequence" in data
        assert "jumps" in data
        assert len(data["jumps"]) == 1
        assert data["jumps"][0]["txid"] == "test_txid_123"
        
    finally:
        # Restore original database path
        src.db._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


def test_transaction_sequences():
    """Test getting sequences for a transaction."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_file:
        temp_db_path = tmp_file.name
    
    try:
        # Temporarily override the database path
        original_db_path = _DB_PATH
        import src.db
        src.db._DB_PATH = Path(temp_db_path)
        
        # Initialize the database
        init_db()
        
        # Insert a test transaction
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO transactions 
                (txid, chain, from_address, to_address, amount, datetime_utc, token_symbol, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("test_txid_123", "ETH", "from_addr", "to_addr", "100.0", "2023-01-01T00:00:00Z", "USDT", "{}"))
            conn.commit()
        
        # Create a sequence
        response = client.post("/api/sequences", json={
            "name": "Test Sequence",
            "description": "A test sequence for transactions"
        })
        assert response.status_code == 200
        data = response.json()
        sequence_id = data["id"]
        
        # Add a jump
        response = client.post(f"/api/sequences/{sequence_id}/jumps", json={
            "txid": "test_txid_123",
            "jump_number": 1,
            "notes": "First jump"
        })
        assert response.status_code == 200
        
        # Test getting sequences for transaction
        response = client.get(f"/api/tx/test_txid_123/sequences")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sequence_id"] == sequence_id
        assert data[0]["sequence_name"] == "Test Sequence"
        assert data[0]["jump_number"] == 1
        assert data[0]["notes"] == "First jump"
        
        # Test with non-existent transaction
        response = client.get(f"/api/tx/nonexistent/sequences")
        assert response.status_code == 404
        
    finally:
        # Restore original database path
        src.db._DB_PATH = original_db_path
        # Clean up temporary file
        os.unlink(temp_db_path)


if __name__ == "__main__":
    test_sequences_crud()
    test_jumps_crud()
    test_sequence_reports()
    test_transaction_sequences()
    print("All API tests passed!")