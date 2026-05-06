"""Sequences route for Octotrace API.

Handles CRUD operations for sequences and sequence jumps,
as well as sequence reports and transaction-sequence associations.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json

from src.db import get_connection

# Evidence URL templates
_URL_TX = {"ETH": "https://etherscan.io/tx/{txid}", "TRON": "https://tronscan.org/#/transaction/{txid}"}

router = APIRouter()

class SequenceCreate(BaseModel):
    """Request model for creating a sequence."""
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""

class SequenceUpdate(BaseModel):
    """Request model for updating a sequence."""
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""

class JumpCreate(BaseModel):
    """Request model for creating a jump."""
    txid: str
    jump_number: int = Field(..., ge=1)
    notes: str = ""

class JumpUpdate(BaseModel):
    """Request model for updating a jump."""
    jump_number: int = Field(..., ge=1)

# === SEQUENCE CRUD ENDPOINTS ===

@router.get("/sequences")
async def list_sequences():
    """List all sequences with their jump counts.
    
    Returns:
        List of sequences with id, name, description, created_at, and jump_count
    """
    try:
        with get_connection(read_only=True) as conn:
            rows = conn.execute("""
                SELECT s.id, s.name, s.description, s.created_at, 
                       COUNT(j.id) as jump_count
                FROM sequences s
                LEFT JOIN sequence_jumps j ON s.id = j.sequence_id
                GROUP BY s.id, s.name, s.description, s.created_at
                ORDER BY s.created_at DESC
            """).fetchall()
            
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sequences: {str(e)}")

@router.get("/sequences/{sequence_id}")
async def get_sequence(sequence_id: int):
    """Get a sequence with all its jumps and associated transaction data.
    
    Args:
        sequence_id: ID of the sequence to retrieve
        
    Returns:
        Sequence details with jumps and transaction data
    """
    try:
        with get_connection(read_only=True) as conn:
            # Get sequence details
            sequence_row = conn.execute(
                "SELECT id, name, description, created_at FROM sequences WHERE id = ?",
                (sequence_id,)
            ).fetchone()
            
            if not sequence_row:
                raise HTTPException(status_code=404, detail="Sequence not found")
            
            sequence = dict(sequence_row)
            
            # Get all jumps with transaction data using a LEFT JOIN
            jump_rows = conn.execute("""
                SELECT j.id, j.txid, j.jump_number, j.notes, j.assigned_at,
                       t.chain, t.from_address, t.to_address, t.amount, 
                       t.datetime_utc, t.token_symbol, t.block_number, 
                       t.confirmations, t.tag_from, t.tag_to, t.service_from, 
                       t.service_to, t.url_tx, t.raw_json
                FROM sequence_jumps j
                LEFT JOIN transactions t ON j.txid = t.txid
                WHERE j.sequence_id = ?
                ORDER BY j.jump_number ASC
            """, (sequence_id,)).fetchall()
            
            jumps = []
            for row in jump_rows:
                jump = dict(row)
                # Add transaction data if available
                if row['chain']:  # If transaction data exists
                    jump['tx'] = {
                        'txid': row['txid'],
                        'chain': row['chain'],
                        'from_address': row['from_address'],
                        'to_address': row['to_address'],
                        'amount': row['amount'],
                        'datetime_utc': row['datetime_utc'],
                        'token_symbol': row['token_symbol'],
                        'block_number': row['block_number'],
                        'confirmations': row['confirmations'],
                        'tag_from': row['tag_from'],
                        'tag_to': row['tag_to'],
                        'service_from': row['service_from'],
                        'service_to': row['service_to'],
                        'url_tx': row['url_tx'],
                        'raw_json': row['raw_json']
                    }
                else:
                    jump['tx'] = None
                jumps.append(jump)
            
            sequence['jumps'] = jumps
            return sequence
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sequence: {str(e)}")

@router.post("/sequences")
async def create_sequence(request: SequenceCreate):
    """Create a new sequence.
    
    Args:
        request: Sequence creation request with name and optional description
        
    Returns:
        Success status with new sequence ID
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO sequences (name, description) VALUES (?, ?)",
                (request.name, request.description)
            )
            sequence_id = cursor.lastrowid
            conn.commit()
            return {"status": "success", "id": sequence_id}
    except Exception as e:
        # Check if it's a duplicate name constraint violation
        if "UNIQUE constraint failed: sequences.name" in str(e):
            raise HTTPException(status_code=409, detail="Sequence name already exists")
        raise HTTPException(status_code=500, detail=f"Failed to create sequence: {str(e)}")

@router.put("/sequences/{sequence_id}")
async def update_sequence(sequence_id: int, request: SequenceUpdate):
    """Update a sequence.
    
    Args:
        sequence_id: ID of the sequence to update
        request: Sequence update request with name and optional description
        
    Returns:
        Success status
    """
    try:
        with get_connection() as conn:
            # Check if sequence exists
            existing = conn.execute(
                "SELECT id FROM sequences WHERE id = ?",
                (sequence_id,)
            ).fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Sequence not found")
            
            # Update sequence
            conn.execute(
                "UPDATE sequences SET name = ?, description = ? WHERE id = ?",
                (request.name, request.description, sequence_id)
            )
            conn.commit()
            return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a duplicate name constraint violation
        if "UNIQUE constraint failed: sequences.name" in str(e):
            raise HTTPException(status_code=409, detail="Sequence name already exists")
        raise HTTPException(status_code=500, detail=f"Failed to update sequence: {str(e)}")

@router.delete("/sequences/{sequence_id}")
async def delete_sequence(sequence_id: int):
    """Delete a sequence and all its jumps.
    
    Args:
        sequence_id: ID of the sequence to delete
        
    Returns:
        Success status
    """
    try:
        with get_connection() as conn:
            # Check if sequence exists
            existing = conn.execute(
                "SELECT id FROM sequences WHERE id = ?",
                (sequence_id,)
            ).fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Sequence not found")
            
            # Delete sequence (CASCADE will delete jumps)
            conn.execute(
                "DELETE FROM sequences WHERE id = ?",
                (sequence_id,)
            )
            conn.commit()
            return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete sequence: {str(e)}")

# === JUMP CRUD ENDPOINTS ===

@router.post("/sequences/{sequence_id}/jumps")
async def create_jump(sequence_id: int, request: JumpCreate):
    """Assign a transaction to a sequence as a jump.
    
    Args:
        sequence_id: ID of the sequence to assign to
        request: Jump creation request with txid, jump_number, and optional notes
        
    Returns:
        Success status with new jump ID
    """
    try:
        with get_connection() as conn:
            # Check if sequence exists
            sequence_exists = conn.execute(
                "SELECT id FROM sequences WHERE id = ?",
                (sequence_id,)
            ).fetchone()
            
            if not sequence_exists:
                raise HTTPException(status_code=404, detail="Sequence not found")
            
            # Check if transaction exists
            tx_exists = conn.execute(
                "SELECT txid, chain FROM transactions WHERE txid = ?",
                (request.txid,)
            ).fetchone()
            
            if not tx_exists:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            # Insert jump
            cursor = conn.execute(
                """INSERT INTO sequence_jumps 
                   (sequence_id, txid, jump_number, notes) 
                   VALUES (?, ?, ?, ?)""",
                (sequence_id, request.txid, request.jump_number, request.notes)
            )
            jump_id = cursor.lastrowid
            conn.commit()
            return {"status": "success", "jump_id": jump_id}
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a duplicate jump_number constraint violation
        if "UNIQUE constraint failed: sequence_jumps.sequence_id, sequence_jumps.jump_number" in str(e):
            raise HTTPException(status_code=409, detail="Jump number already exists in this sequence")
        raise HTTPException(status_code=500, detail=f"Failed to create jump: {str(e)}")

@router.delete("/jumps/{jump_id}")
async def delete_jump(jump_id: int):
    """Remove a transaction from a sequence.
    
    Args:
        jump_id: ID of the jump to remove
        
    Returns:
        Success status
    """
    try:
        with get_connection() as conn:
            # Check if jump exists
            existing = conn.execute(
                "SELECT id FROM sequence_jumps WHERE id = ?",
                (jump_id,)
            ).fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Jump not found")
            
            # Delete jump
            conn.execute(
                "DELETE FROM sequence_jumps WHERE id = ?",
                (jump_id,)
            )
            conn.commit()
            return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete jump: {str(e)}")

@router.patch("/jumps/{jump_id}")
async def update_jump(jump_id: int, request: JumpUpdate):
    """Update a jump's number.
    
    Args:
        jump_id: ID of the jump to update
        request: Jump update request with new jump_number
        
    Returns:
        Success status
    """
    try:
        with get_connection() as conn:
            # Check if jump exists
            existing = conn.execute(
                "SELECT id, sequence_id FROM sequence_jumps WHERE id = ?",
                (jump_id,)
            ).fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Jump not found")
            
            # Check if another jump in the same sequence already has this number
            conflict = conn.execute(
                """SELECT id FROM sequence_jumps 
                   WHERE sequence_id = ? AND jump_number = ? AND id != ?""",
                (existing['sequence_id'], request.jump_number, jump_id)
            ).fetchone()
            
            if conflict:
                raise HTTPException(status_code=409, detail="Jump number already exists in this sequence")
            
            # Update jump
            conn.execute(
                "UPDATE sequence_jumps SET jump_number = ? WHERE id = ?",
                (request.jump_number, jump_id)
            )
            conn.commit()
            return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update jump: {str(e)}")

# === REPORT ENDPOINTS ===

@router.get("/sequences/{sequence_id}/report")
async def get_sequence_report(sequence_id: int, format: str = "text"):
    """Generate a report for a sequence.
    
    Args:
        sequence_id: ID of the sequence to generate report for
        format: Output format ("text" or "json")
        
    Returns:
        Sequence report in requested format
    """
    try:
        with get_connection(read_only=True) as conn:
            # Get sequence details
            sequence_row = conn.execute(
                "SELECT id, name, description, created_at FROM sequences WHERE id = ?",
                (sequence_id,)
            ).fetchone()
            
            if not sequence_row:
                raise HTTPException(status_code=404, detail="Sequence not found")
            
            sequence = dict(sequence_row)
            
            # Get all jumps ordered by jump number
            jump_rows = conn.execute("""
                SELECT j.txid, j.jump_number, j.notes, j.assigned_at,
                       t.chain, t.from_address, t.to_address, t.amount, 
                       t.datetime_utc, t.token_symbol, t.raw_json
                FROM sequence_jumps j
                JOIN transactions t ON j.txid = t.txid
                WHERE j.sequence_id = ?
                ORDER BY j.jump_number ASC
            """, (sequence_id,)).fetchall()
            
            jumps = [dict(row) for row in jump_rows]
            
            if format.lower() == "json":
                return {
                    "sequence": sequence,
                    "jumps": jumps
                }
            else:  # text format
                lines = []
                lines.append(f"SEQUENCE REPORT: {sequence['name']}")
                lines.append(f"Description: {sequence['description']}")
                lines.append(f"Created: {sequence['created_at']}")
                lines.append("")
                lines.append("JUMPS:")
                lines.append("------")
                
                for jump in jumps:
                    lines.append(f"#{jump['jump_number']} - {jump['txid']}")
                    lines.append(f"  Amount: {jump['amount']} {jump['token_symbol']}")
                    lines.append(f"  From: {jump['from_address']}")
                    lines.append(f"  To: {jump['to_address']}")
                    lines.append(f"  Date: {jump['datetime_utc']}")
                    lines.append(f"  Chain: {jump['chain']}")
                    if jump['notes']:
                        lines.append(f"  Notes: {jump['notes']}")
                    lines.append("")
                
                return {"report": "\n".join(lines)}
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

# === TRANSACTION SEQUENCES ENDPOINT ===

@router.get("/tx/{txid}/sequences")
async def get_tx_sequences(txid: str):
    """Get all sequences that a transaction belongs to.
    
    Args:
        txid: Transaction ID to check
        
    Returns:
        List of sequences the transaction belongs to
    """
    try:
        with get_connection(read_only=True) as conn:
            # Check if transaction exists
            tx_exists = conn.execute(
                "SELECT txid FROM transactions WHERE txid = ?",
                (txid,)
            ).fetchone()
            
            if not tx_exists:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            # Get sequences for this transaction
            rows = conn.execute("""
                SELECT s.id as sequence_id, s.name as sequence_name, 
                       j.jump_number, j.notes
                FROM sequence_jumps j
                JOIN sequences s ON j.sequence_id = s.id
                WHERE j.txid = ?
                ORDER BY s.name, j.jump_number
            """, (txid,)).fetchall()
            
            return [dict(row) for row in rows]
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction sequences: {str(e)}")