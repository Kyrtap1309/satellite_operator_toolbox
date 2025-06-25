import json
import logging
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from services.todo_service import TodoService

logger = logging.getLogger(__name__)

todo_bp = Blueprint("todo", __name__, url_prefix="/todo")
todo_service = TodoService()


@todo_bp.route("/")
def todo_index() -> str:
    """Display all todo tasks"""
    tasks = todo_service.get_all_tasks()  # This now returns sorted tasks
    logger.info(f"TODO index accessed, found {len(tasks)} tasks")
    logger.info("Rendering template with %d tasks", len(tasks))

    timeline_data = todo_service.get_timeline_data()
    timeline_groups = todo_service.get_timeline_groups()

    return render_template("todo/index.html", tasks=tasks, timeline_data=json.dumps(timeline_data), timeline_groups=json.dumps(timeline_groups))


@todo_bp.route("/task/create", methods=["POST"])
def create_task() -> Response:
    """Create new task"""
    title = request.form.get("title")
    description = request.form.get("description", "")

    if not title:
        flash("Task title is required", "error")
        return redirect(url_for("todo.todo_index"))

    try:
        task = todo_service.create_task(title, description)
        flash(f'Task "{task.title}" created successfully!', "success")
    except Exception as e:
        flash(f"Error creating task: {str(e)}", "error")

    return redirect(url_for("todo.todo_index"))


@todo_bp.route("/subtask/add", methods=["POST"])
def add_subtask() -> Response:
    """Add new subtask to existing task"""
    task_id_str = request.form.get("task_id")
    title = request.form.get("title")
    description = request.form.get("description") or ""
    start_date = request.form.get("start_date")
    start_time = request.form.get("start_time")
    end_date = request.form.get("end_date")
    end_time = request.form.get("end_time")
    scheduled = request.form.get("scheduled") == "on"

    # Validate task ID
    if not task_id_str or not task_id_str.isdigit():
        flash("Invalid task ID", "error")
        return redirect(url_for("todo.todo_index"))

    task_id = int(task_id_str)

    # Validate title
    if not title or not title.strip():
        flash("Subtask title is required", "error")
        return redirect(url_for("todo.task_details", task_id=task_id))

    # Validate and parse datetime
    datetime_result = _validate_and_parse_datetime(scheduled, start_date, start_time, end_date, end_time)
    if scheduled and datetime_result is None:
        return redirect(url_for("todo.task_details", task_id=task_id))

    start_datetime, end_datetime = datetime_result if datetime_result else (None, None)

    # Add subtask
    try:
        success = todo_service.add_subtask(task_id, title, description, start_datetime, end_datetime)
        if success:
            flash(f'Subtask "{title}" added successfully!', "success")
        else:
            flash("Task not found", "error")
    except Exception as e:
        flash(f"Error adding subtask: {str(e)}", "error")

    return redirect(url_for("todo.task_details", task_id=task_id))


@todo_bp.route("/subtask/toggle", methods=["POST"])
def toggle_subtask() -> tuple[Response, int] | Response:
    """Toggle subtask completion status"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data received"}), 400

        task_id = data.get("task_id")
        subtask_id = data.get("subtask_id")

        if not task_id or not subtask_id:
            return jsonify({"success": False, "error": "Missing task_id or subtask_id"}), 400

        success = todo_service.toggle_subtask_completion(task_id, subtask_id)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Task or subtask not found"}), 404

    except Exception as e:
        logger.error(f"Error toggling subtask: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@todo_bp.route("/task/delete", methods=["POST"])
def delete_task() -> tuple[Response, int] | Response:
    """Delete task"""
    data = request.get_json()
    task_id = data.get("task_id")

    if not task_id:
        return jsonify({"error": "Missing task_id"}), 400

    success = todo_service.delete_task(task_id)
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Task not found"}), 404


@todo_bp.route("/task/<int:task_id>")
def task_details(task_id: int) -> str | Response:
    """Display detailed view of a single task"""
    task = todo_service.get_task_by_id(task_id)
    if not task:
        flash("Task not found", "error")
        return redirect(url_for("todo.todo_index"))

    timeline_data = todo_service.get_timeline_data(task_id)
    timeline_groups = todo_service.get_timeline_groups(task_id)

    return render_template("todo/task_detail.html", task=task, timeline_data=json.dumps(timeline_data), timeline_groups=json.dumps(timeline_groups))


@todo_bp.route("/subtask/delete", methods=["POST"])
def delete_subtask() -> tuple[Response, int] | Response:
    """Delete subtask"""
    data = request.get_json()
    task_id = data.get("task_id")
    subtask_id = data.get("subtask_id")

    if not task_id or not subtask_id:
        return jsonify({"error": "Missing task_id or subtask_id"}), 400

    success = todo_service.delete_subtask(task_id, subtask_id)
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Task or subtask not found"}), 404


@todo_bp.route("/task/<int:task_id>/progress", methods=["GET"])
def get_task_progress(task_id: int) -> tuple[Response, int] | Response:
    """Get task progress information"""
    try:
        task = todo_service.get_task_by_id(task_id)
        if not task:
            return jsonify({"success": False, "error": "Task not found"}), 404

        return jsonify(
            {
                "success": True,
                "completion_percentage": task.completion_percentage,
                "completed_subtasks": sum(1 for st in task.subtasks if st.completed),
                "total_subtasks": len(task.subtasks),
                "total_duration_hours": task.total_duration_hours,
            }
        )
    except Exception as e:
        logger.error(f"Error getting task progress: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


def _validate_subtask_ids(task_id_str: str | None, subtask_id_str: str | None) -> tuple[int, int] | None:
    """Validate and convert task and subtask IDs"""
    if not task_id_str or not task_id_str.isdigit():
        flash("Invalid task ID", "error")
        return None

    if not subtask_id_str or not subtask_id_str.isdigit():
        flash("Invalid subtask ID", "error")
        return None

    return int(task_id_str), int(subtask_id_str)


def _validate_and_parse_datetime(
    scheduled: bool, start_date: str | None, start_time: str | None, end_date: str | None, end_time: str | None
) -> tuple[datetime | None, datetime | None] | None:
    """Validate and parse datetime fields"""
    if not scheduled:
        return None, None

    if not all([start_date, start_time, end_date, end_time]):
        flash("All date and time fields are required when scheduling", "error")
        return None

    try:
        start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")

        if end_datetime <= start_datetime:
            flash("End time must be after start time", "error")
            return None

        return start_datetime, end_datetime
    except ValueError as e:
        flash(f"Invalid date/time format: {str(e)}", "error")
        return None


@todo_bp.route("/subtask/edit", methods=["POST"])
def edit_subtask() -> Response:
    """Edit existing subtask"""
    task_id_str = request.form.get("task_id")
    subtask_id_str = request.form.get("subtask_id")
    title = request.form.get("title")
    description = request.form.get("description") or ""
    start_date = request.form.get("start_date")
    start_time = request.form.get("start_time")
    end_date = request.form.get("end_date")
    end_time = request.form.get("end_time")
    scheduled = request.form.get("scheduled") == "on"

    # Validate IDs
    ids_result = _validate_subtask_ids(task_id_str, subtask_id_str)
    if ids_result is None:
        return redirect(url_for("todo.todo_index"))

    task_id, subtask_id = ids_result

    # Validate title
    if not title or not title.strip():
        flash("Subtask title is required", "error")
        return redirect(url_for("todo.task_details", task_id=task_id))

    # Validate and parse datetime
    datetime_result = _validate_and_parse_datetime(scheduled, start_date, start_time, end_date, end_time)
    if scheduled and datetime_result is None:
        return redirect(url_for("todo.task_details", task_id=task_id))

    start_datetime, end_datetime = datetime_result if datetime_result else (None, None)

    # Update subtask
    try:
        success = todo_service.edit_subtask(task_id, subtask_id, title, description, start_datetime, end_datetime)
        if success:
            flash(f'Subtask "{title}" updated successfully!', "success")
        else:
            flash("Subtask not found", "error")
    except Exception as e:
        flash(f"Error updating subtask: {str(e)}", "error")

    return redirect(url_for("todo.task_details", task_id=task_id))


@todo_bp.route("tasks/reorder", methods=["POST"])
def reorder_tasks() -> tuple[Response, int] | Response:
    """Reorder tasks"""
    try:
        data = request.get_json()
        task_ids = data.get("task_ids", [])

        if not task_ids:
            return jsonify({"error": "No task IDs provided"}), 400

        success = todo_service.reorder_tasks(task_ids)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to reorder tasks"}), 500

    except Exception as e:
        logger.error(f"Error in reorder_tasks route: {e}")
        return jsonify({"error": "Internal server error"}), 500
