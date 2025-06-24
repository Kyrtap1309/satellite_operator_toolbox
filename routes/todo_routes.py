from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from services.todo_service import TodoService
import json
import logging

logger = logging.getLogger(__name__)

todo_bp = Blueprint('todo', __name__, url_prefix='/todo')
todo_service = TodoService()

@todo_bp.route('/')
def todo_index():
    """Display all tasks with timeline visualization"""
    logger.info(f"TODO index accessed, found {len(todo_service.tasks)} tasks")
    tasks = todo_service.get_all_tasks()
    timeline_data = todo_service.get_timeline_data()
    timeline_groups = todo_service.get_timeline_groups()
    
    logger.info(f"Rendering template with {len(tasks)} tasks")
    return render_template('todo/index.html',
                         tasks=tasks,
                         timeline_data=json.dumps(timeline_data),
                         timeline_groups=json.dumps(timeline_groups))

@todo_bp.route('/task/create', methods=['POST'])
def create_task():
    """Create new task"""
    title = request.form.get('title')
    description = request.form.get('description', '')
    
    if not title:
        flash('Task title is required', 'error')
        return redirect(url_for('todo.todo_index'))
    
    try:
        task = todo_service.create_task(title, description)
        flash(f'Task "{task.title}" created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating task: {str(e)}', 'error')
    
    return redirect(url_for('todo.todo_index'))

@todo_bp.route('/subtask/add', methods=['POST'])
def add_subtask():
    """Add subtask to existing task"""
    task_id = int(request.form.get('task_id'))
    title = request.form.get('title')
    description = request.form.get('description', '')
    start_date = request.form.get('start_date')
    start_time = request.form.get('start_time')
    end_date = request.form.get('end_date')
    end_time = request.form.get('end_time')
    
    if not all([task_id, title, start_date, start_time, end_date, end_time]):
        flash('All fields are required for subtask', 'error')
        return redirect(url_for('todo.todo_index'))
    
    try:
        start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
        
        if end_datetime <= start_datetime:
            flash('End time must be after start time', 'error')
            return redirect(url_for('todo.todo_index'))
        
        subtask = todo_service.add_subtask(task_id, title, description, start_datetime, end_datetime)
        if subtask:
            flash(f'Subtask "{subtask.title}" added successfully!', 'success')
        else:
            flash('Task not found', 'error')
    except ValueError as e:
        flash(f'Invalid date/time format: {str(e)}', 'error')
    except Exception as e:
        flash(f'Error adding subtask: {str(e)}', 'error')
    
    return redirect(url_for('todo.todo_index'))

@todo_bp.route('/subtask/toggle', methods=['POST'])
def toggle_subtask():
    """Toggle subtask completion status"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400
            
        task_id = data.get('task_id')
        subtask_id = data.get('subtask_id')
        
        if not task_id or not subtask_id:
            return jsonify({'success': False, 'error': 'Missing task_id or subtask_id'}), 400
        
        success = todo_service.toggle_subtask_completion(task_id, subtask_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Task or subtask not found'}), 404
            
    except Exception as e:
        logger.error(f"Error toggling subtask: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@todo_bp.route('/task/delete', methods=['POST'])
def delete_task():
    """Delete task"""
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'error': 'Missing task_id'}), 400
    
    success = todo_service.delete_task(task_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Task not found'}), 404

@todo_bp.route('/task/<int:task_id>')
def task_details(task_id):
    """Display detailed view of a single task"""
    task = todo_service.get_task_by_id(task_id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('todo.todo_index'))
    
    timeline_data = todo_service.get_timeline_data(task_id)
    timeline_groups = todo_service.get_timeline_groups(task_id)
    
    return render_template('todo/task_detail.html',
                         task=task,
                         timeline_data=json.dumps(timeline_data),
                         timeline_groups=json.dumps(timeline_groups))

@todo_bp.route('/subtask/delete', methods=['POST'])
def delete_subtask():
    """Delete subtask"""
    data = request.get_json()
    task_id = data.get('task_id')
    subtask_id = data.get('subtask_id')
    
    if not task_id or not subtask_id:
        return jsonify({'error': 'Missing task_id or subtask_id'}), 400
    
    success = todo_service.delete_subtask(task_id, subtask_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Task or subtask not found'}), 404

@todo_bp.route('/task/<int:task_id>/progress', methods=['GET'])
def get_task_progress(task_id):
    """Get task progress information"""
    try:
        task = todo_service.get_task_by_id(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'completion_percentage': task.completion_percentage,
            'completed_subtasks': sum(1 for st in task.subtasks if st.completed),
            'total_subtasks': len(task.subtasks),
            'total_duration_hours': task.total_duration_hours
        })
    except Exception as e:
        logger.error(f"Error getting task progress: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500