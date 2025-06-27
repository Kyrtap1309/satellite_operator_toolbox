document.addEventListener('DOMContentLoaded', function() {
    // Initialize timeline
    initializeTimeline();

    // Set default dates
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    document.getElementById('subtask_start_date').value = today.toISOString().split('T')[0];
    document.getElementById('subtask_end_date').value = tomorrow.toISOString().split('T')[0];
    document.getElementById('subtask_start_time').value = '09:00';
    document.getElementById('subtask_end_time').value = '10:00';
});

function initializeTimeline() {
    const timelineData = window.todoTimelineData;

    if (timelineData.length === 0) {
        document.querySelector('#visualization').innerHTML =
            '<div class="d-flex align-items-center justify-content-center h-100 text-muted">' +
            '<div class="text-center">' +
            '<i class="fas fa-calendar-alt fa-3x mb-3"></i>' +
            '<p>No scheduled subtasks yet</p>' +
            '</div></div>';
        return;
    }

    // Create groups - one for each subtask instead of grouping by task
    const groups = timelineData.map((item, index) => ({
        id: item.id,
        content: item.content,
        order: index
    }));

    // Update timeline data to use individual subtask groups
    const updatedTimelineData = timelineData.map(item => ({
        ...item,
        group: item.id // Each subtask uses its own ID as group
    }));

    const items = new vis.DataSet(updatedTimelineData);
    const groupsDataSet = new vis.DataSet(groups);

    const options = {
        editable: false,
        stack: false,
        groupOrder: 'order',
        zoomable: true,
        moveable: true,
        margin: {
            item: 10,
            axis: 5
        },
        // Force UTC time zone
        moment: function(date) {
            return moment.utc(date);
        },
        format: {
            minorLabels: function(date, scale, step) {
                // Use UTC formatting
                if (scale === 'minute') return moment.utc(date).format('HH:mm');
                if (scale === 'hour') return moment.utc(date).format('HH:mm');
                if (scale === 'day') return moment.utc(date).format('DD');
                if (scale === 'month') return moment.utc(date).format('MMM');
                return moment.utc(date).format('YYYY');
            },
            majorLabels: function(date, scale, step) {
                // Use UTC formatting
                if (scale === 'minute' || scale === 'hour') return moment.utc(date).format('ddd DD/MM/YYYY UTC');
                if (scale === 'day') return moment.utc(date).format('MMMM YYYY UTC');
                if (scale === 'month') return moment.utc(date).format('YYYY UTC');
                return '';
            }
        },
        zoomMin: 1000 * 60 * 15,
        zoomMax: 1000 * 60 * 60 * 24 * 365 * 2,
        showCurrentTime: true,
        tooltip: {
            followMouse: true,
            template: function (item) {
                const startTime = moment.utc(item.start).format('YYYY-MM-DD HH:mm');
                const endTime = moment.utc(item.end).format('YYYY-MM-DD HH:mm');
                const duration = moment.utc(item.end).diff(moment.utc(item.start), 'hours', true).toFixed(1);

                return `<div style="padding: 8px;">
                            <strong>${item.content}</strong><br/>
                            ${item.title ? item.title.split(' - ')[1] + '<br/>' : ''}
                            <div style="margin-top: 5px; font-size: 12px; color: #666;">
                                <div><i class="fas fa-clock"></i> Start: ${startTime} UTC</div>
                                <div><i class="fas fa-clock"></i> End: ${endTime} UTC</div>
                                <div><i class="fas fa-hourglass-half"></i> Duration: ${duration}h</div>
                            </div>
                        </div>`;
            }
        }
    };

    const timeline = new vis.Timeline(document.getElementById('visualization'), items, groupsDataSet, options);

    // Set current time to UTC
    timeline.setCurrentTime(moment.utc().toDate());

    // Adjust timeline height based on number of subtasks
    const adjustTimelineHeight = () => {
        const numberOfSubtasks = timelineData.length;
        const minHeight = 200;
        const rowHeight = 60;
        const calculatedHeight = Math.max(minHeight, numberOfSubtasks * rowHeight + 100);

        const container = document.querySelector('.timeline-container');
        container.style.height = `${calculatedHeight}px`;
    };

    adjustTimelineHeight();
    window.addEventListener('resize', adjustTimelineHeight);
}

function toggleSubtask(taskId, subtaskId) {
    const checkbox = event.target;
    const subtaskElement = checkbox.closest('.subtask-card');
    const originalState = checkbox.checked;

    // Optimistically update UI
    if (subtaskElement) {
        subtaskElement.style.opacity = '0.5';
    }

    fetch(window.todoUrls.toggleSubtask, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            task_id: taskId,
            subtask_id: subtaskId
        })
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Server responded with error');
        }
    })
    .then(data => {
        if (data.success) {
            // Update subtask UI
            if (checkbox.checked) {
                subtaskElement.classList.add('completed');
                subtaskElement.querySelector('h6').classList.add('text-decoration-line-through');
            } else {
                subtaskElement.classList.remove('completed');
                subtaskElement.querySelector('h6').classList.remove('text-decoration-line-through');
            }

            // Update Progress Circle
            updateTaskProgressCircle(taskId);

            // Update stats
            updateTaskStats(taskId);
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    })
    .catch(error => {
        console.error('Error toggling subtask:', error);
        checkbox.checked = originalState;
        alert('Failed to update subtask. Please try again.');
    })
    .finally(() => {
        checkbox.disabled = false;
        if (subtaskElement) {
            subtaskElement.style.opacity = '1';
        }
    });
}

function updateTaskProgressCircle(taskId) {
    fetch(window.todoUrls.getTaskProgress.replace('0', taskId))
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update Progress Circle
            const progressCircle = document.querySelector('.progress-circle');
            const progressText = document.querySelector('.progress-text');

            if (progressCircle) {
                const percentage = data.completion_percentage;
                const degrees = percentage * 3.6;
                progressCircle.style.background = `conic-gradient(#28a745 0deg, #28a745 ${degrees}deg, #e9ecef ${degrees}deg)`;
            }

            if (progressText) {
                progressText.textContent = `${Math.round(data.completion_percentage)}%`;
            }
        }
    })
    .catch(error => {
        console.error('Error updating progress circle:', error);
    });
}

function updateTaskStats(taskId) {
    fetch(window.todoUrls.getTaskProgress.replace('0', taskId))
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update Card Stats
            const completedCard = document.querySelector('.card-title.text-success');
            const pendingCard = document.querySelector('.card-title.text-warning');
            const totalTimeCard = document.querySelector('.card-title.text-info');

            if (completedCard) {
                completedCard.textContent = data.completed_subtasks;
            }

            if (pendingCard) {
                pendingCard.textContent = data.total_subtasks - data.completed_subtasks;
            }

            if (totalTimeCard) {
                totalTimeCard.textContent = `${data.total_duration_hours.toFixed(1)}h`;
            }
        }
    })
    .catch(error => {
        console.error('Error updating stats:', error);
    });
}

function toggleScheduleFields() {
    const checkbox = document.getElementById('subtask_scheduled');
    const fields = document.getElementById('schedule_fields');

    if (checkbox.checked) {
        fields.style.display = 'block';
        // Set default values
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        document.getElementById('subtask_start_date').value = today.toISOString().split('T')[0];
        document.getElementById('subtask_end_date').value = tomorrow.toISOString().split('T')[0];
        document.getElementById('subtask_start_time').value = '09:00';
        document.getElementById('subtask_end_time').value = '10:00';
    } else {
        fields.style.display = 'none';
    }
}

function toggleEditScheduleFields() {
    const checkbox = document.getElementById('edit_subtask_scheduled');
    const fields = document.getElementById('edit_schedule_fields');

    fields.style.display = checkbox.checked ? 'block' : 'none';
}

function editSubtask(taskId, subtaskId, title, description, startDate, startTime, endDate, endTime) {
    // Fill the form with current values
    document.getElementById('edit_subtask_id').value = subtaskId;
    document.getElementById('edit_subtask_title').value = title;
    document.getElementById('edit_subtask_description').value = description;

    const hasSchedule = startDate && startTime && endDate && endTime;
    document.getElementById('edit_subtask_scheduled').checked = hasSchedule;

    if (hasSchedule) {
        document.getElementById('edit_subtask_start_date').value = startDate;
        document.getElementById('edit_subtask_start_time').value = startTime;
        document.getElementById('edit_subtask_end_date').value = endDate;
        document.getElementById('edit_subtask_end_time').value = endTime;
        document.getElementById('edit_schedule_fields').style.display = 'block';
    } else {
        document.getElementById('edit_schedule_fields').style.display = 'none';
    }

    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('editSubtaskModal'));
    modal.show();
}

function addSubtask(taskId) {
    // Clear the form
    document.getElementById('subtask_title').value = '';
    document.getElementById('subtask_description').value = '';

    // Set default dates and times
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    document.getElementById('subtask_start_date').value = today.toISOString().split('T')[0];
    document.getElementById('subtask_end_date').value = tomorrow.toISOString().split('T')[0];
    document.getElementById('subtask_start_time').value = '09:00';
    document.getElementById('subtask_end_time').value = '10:00';

    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('subtaskModal'));
    modal.show();
}

function deleteTask(taskId) {
    if (confirm('Are you sure you want to delete this task and all its subtasks?')) {
        fetch(window.todoUrls.deleteTask, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({task_id: taskId})
        }).then(response => {
            if (response.ok) {
                // Redirect to todo index after successful deletion
                window.location.href = window.todoUrls.todoIndex;
            } else {
                alert('Failed to delete task. Please try again.');
            }
        }).catch(error => {
            console.error('Error deleting task:', error);
            alert('Failed to delete task. Please try again.');
        });
    }
}

function deleteSubtask(taskId, subtaskId) {
    if (confirm('Are you sure you want to delete this subtask?')) {
        fetch(window.todoUrls.deleteSubtask, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                task_id: taskId,
                subtask_id: subtaskId
            })
        }).then(response => {
            if (response.ok) {
                location.reload();
            } else {
                alert('Failed to delete subtask. Please try again.');
            }
        }).catch(error => {
            console.error('Error deleting subtask:', error);
            alert('Failed to delete subtask. Please try again.');
        });
    }
}