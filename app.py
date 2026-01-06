"""
Task Manager API - Junior Cloud Engineer Assessment
A simple REST API for the candidate to deploy and monitor on GCP
"""

import os
import logging
import time
from datetime import datetime
from flask import Flask, jsonify, request
from google.cloud import firestore
from google.cloud import secretmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT_ID')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

# Firestore client (lazy initialization)
_db = None

def get_db():
    """Get Firestore client with lazy initialization."""
    global _db
    if _db is None:
        logger.info("Initializing Firestore client")
        _db = firestore.Client(project=PROJECT_ID)
    return _db


def get_secret(secret_id: str) -> str:
    """Retrieve a secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


# Health check endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': ENVIRONMENT
    })


@app.route('/health/ready', methods=['GET'])
def readiness_check():
    """Readiness check - verifies dependencies are available."""
    checks = {
        'firestore': False,
        'config': False
    }
    
    # Check Firestore connectivity
    try:
        db = get_db()
        # Simple read operation to verify connectivity
        db.collection('_health').document('check').get()
        checks['firestore'] = True
    except Exception as e:
        logger.error(f"Firestore health check failed: {e}")
    
    # Check configuration
    checks['config'] = bool(PROJECT_ID)
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return jsonify({
        'status': 'ready' if all_healthy else 'not_ready',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }), status_code


# Task API endpoints
@app.route('/tasks', methods=['GET'])
def list_tasks():
    """List all tasks."""
    logger.info("Listing all tasks")
    start_time = time.time()
    
    try:
        db = get_db()
        tasks_ref = db.collection('tasks')
        
        # Optional filtering
        status_filter = request.args.get('status')
        if status_filter:
            tasks_ref = tasks_ref.where('status', '==', status_filter)
        
        # Get tasks
        tasks = []
        for doc in tasks_ref.stream():
            task = doc.to_dict()
            task['id'] = doc.id
            tasks.append(task)
        
        duration = time.time() - start_time
        logger.info(f"Listed {len(tasks)} tasks in {duration:.3f}s")
        
        return jsonify({
            'tasks': tasks,
            'count': len(tasks)
        })
    
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return jsonify({'error': 'Failed to list tasks'}), 500


@app.route('/tasks', methods=['POST'])
def create_task():
    """Create a new task."""
    logger.info("Creating new task")
    
    try:
        data = request.get_json()
        
        # Validation
        if not data or 'title' not in data:
            return jsonify({'error': 'Title is required'}), 400
        
        # Create task document
        task = {
            'title': data['title'],
            'description': data.get('description', ''),
            'status': 'pending',
            'priority': data.get('priority', 'medium'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        db = get_db()
        doc_ref = db.collection('tasks').document()
        doc_ref.set(task)
        
        task['id'] = doc_ref.id
        logger.info(f"Created task with ID: {doc_ref.id}")
        
        return jsonify(task), 201
    
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({'error': 'Failed to create task'}), 500


@app.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """Get a specific task by ID."""
    logger.info(f"Getting task: {task_id}")
    
    try:
        db = get_db()
        doc = db.collection('tasks').document(task_id).get()
        
        if not doc.exists:
            return jsonify({'error': 'Task not found'}), 404
        
        task = doc.to_dict()
        task['id'] = doc.id
        
        return jsonify(task)
    
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        return jsonify({'error': 'Failed to get task'}), 500


@app.route('/tasks/<task_id>', methods=['PUT'])
def update_task(task_id: str):
    """Update a task."""
    logger.info(f"Updating task: {task_id}")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = get_db()
        doc_ref = db.collection('tasks').document(task_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({'error': 'Task not found'}), 404
        
        # Allowed fields to update
        allowed_fields = ['title', 'description', 'status', 'priority']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        doc_ref.update(update_data)
        
        # Get updated document
        updated_doc = doc_ref.get()
        task = updated_doc.to_dict()
        task['id'] = updated_doc.id
        
        logger.info(f"Updated task: {task_id}")
        return jsonify(task)
    
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}")
        return jsonify({'error': 'Failed to update task'}), 500


@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id: str):
    """Delete a task."""
    logger.info(f"Deleting task: {task_id}")
    
    try:
        db = get_db()
        doc_ref = db.collection('tasks').document(task_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({'error': 'Task not found'}), 404
        
        doc_ref.delete()
        logger.info(f"Deleted task: {task_id}")
        
        return jsonify({'message': 'Task deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        return jsonify({'error': 'Failed to delete task'}), 500


# Metrics endpoint (for monitoring)
@app.route('/metrics', methods=['GET'])
def metrics():
    """Simple metrics endpoint."""
    try:
        db = get_db()
        
        # Count tasks by status
        tasks_ref = db.collection('tasks')
        total = len(list(tasks_ref.stream()))
        pending = len(list(tasks_ref.where('status', '==', 'pending').stream()))
        completed = len(list(tasks_ref.where('status', '==', 'completed').stream()))
        
        return jsonify({
            'tasks_total': total,
            'tasks_pending': pending,
            'tasks_completed': completed,
            'environment': ENVIRONMENT,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': 'Failed to get metrics'}), 500


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Task Manager API on port {port}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Project ID: {PROJECT_ID}")
    
    app.run(host='0.0.0.0', port=port, debug=(ENVIRONMENT == 'development'))