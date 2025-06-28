document.addEventListener('DOMContentLoaded', function() {
    // Initialize timeline
    initializeTimeline();

    // Initialize drag & drop
    initializeSortable();

    // Initialize timeline resizer
    initializeTimelineResizer();
});

function initializeTimeline() {
    const timelineData = window.todoTimelineData;
    const groups = window.todoTimelineGroups;

    if (timelineData.length === 0) {
        document.querySelector('.timeline-container').innerHTML =
            '<div class="d-flex align-items-center justify-content-center h-100 text-muted">' +
            '<div class="text-center">' +
            '<i class="fas fa-calendar-alt fa-3x mb-3"></i>' +
            '<p>No scheduled subtasks yet</p>' +
            '</div></div>' +
            '<div class="timeline-resize-handle" id="timeline-resize-handle"></div>';

        // Re-initialize resizer if timeline is empty
        initializeTimelineResizer();
        return;
    }

    const items = new vis.DataSet(timelineData);
    const groupsDataSet = new vis.DataSet(groups);

    // Calculate time range to determine appropriate scale
    const dates = timelineData.flatMap(item => [new Date(item.start), new Date(item.end)]);
    const minDate = new Date(Math.min(...dates));
    const maxDate = new Date(Math.max(...dates));

    const container = document.getElementById('visualization');

    // Calculate proper height based on number of groups
    const numberOfGroups = groups.length;
    const minHeight = 200;
    const groupHeight = 60; // Height per group/row
    const calculatedHeight = Math.max(minHeight, numberOfGroups * groupHeight + 100);

    // Set container height to accommodate all groups
    const timelineContainer = document.getElementById('timeline-container');
    timelineContainer.style.height = calculatedHeight + 'px';

    const options = {
        zoomable: true,
        moveable: true,
        stack: true, // Re-enable stacking within groups
        stackSubgroups: true, // Enable stacking of items in subgroups
        orientation: 'top',
        showCurrentTime: true,
        groupOrder: 'id', // Ensure consistent ordering
        // Force UTC time zone
        moment: function(date) {
            return moment.utc(date);
        },
        format: {
            minorLabels: function(date, scale, step) {
                // Use UTC formatting
                if (scale === 'minute' || scale === 'hour') return moment.utc(date).format('HH:mm');
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

    window.timeline = new vis.Timeline(container, items, groupsDataSet, options);

    // Set current time to UTC
    window.timeline.setCurrentTime(moment.utc().toDate());

    // Force redraw to ensure all groups are visible
    setTimeout(() => {
        window.timeline.redraw();
        window.timeline.fit(); // Fit timeline to show all items
    }, 100);
}

function initializeTimelineResizer() {
    const container = document.getElementById('timeline-container');
    const handle = document.getElementById('timeline-resize-handle');
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    if (!handle) return;

    handle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startY = e.clientY;
        startHeight = parseInt(document.defaultView.getComputedStyle(container).height, 10);
        document.addEventListener('mousemove', doResize);
        document.addEventListener('mouseup', stopResize);
        e.preventDefault();
    });

    function doResize(e) {
        if (!isResizing) return;

        const newHeight = startHeight + (e.clientY - startY);
        const minHeight = 300; // Increased minimum height
        const maxHeight = window.innerHeight - 100; // Max to screen height minus some margin

        if (newHeight >= minHeight && newHeight <= maxHeight) {
            container.style.height = newHeight + 'px';

            // Redraw timeline to fit new container size
            if (window.timeline) {
                setTimeout(() => {
                    window.timeline.redraw();
                }, 10);
            }
        }
    }

    function stopResize() {
        isResizing = false;
        document.removeEventListener('mousemove', doResize);
        document.removeEventListener('mouseup', stopResize);
    }
}

function initializeSortable() {
    const tasksContainer = document.getElementById('tasks-container');

    new Sortable(tasksContainer, {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        handle: '.drag-handle',
        onEnd: function(evt) {
            // Get new order of task IDs
            const taskIds = Array.from(tasksContainer.children).map(el =>
                parseInt(el.getAttribute('data-task-id'))
            );

            // Send new order to server
            fetch(window.todoUrls.reorderTasks, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({task_ids: taskIds})
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    console.error('Failed to reorder tasks');
                    // Optionally reload page on error
                    location.reload();
                }
            })
            .catch(error => {
                console.error('Error reordering tasks:', error);
                // Optionally reload page on error
                location.reload();
            });
        }
    });
}

function addSubtask(taskId) {
    document.getElementById('subtask_task_id').value = taskId;
    const modal = new bootstrap.Modal(document.getElementById('subtaskModal'));
    modal.show();
}

function toggleSubtask(taskId, subtaskId) {
    const checkbox = event.target;
    const originalState = !checkbox.checked;
    const subtaskElement = checkbox.closest('.subtask-item');

    checkbox.disabled = true;
    subtaskElement.style.opacity = '0.6';

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
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (checkbox.checked) {
                subtaskElement.classList.add('completed');
            } else {
                subtaskElement.classList.remove('completed');
            }

            updateTaskProgress(taskId);
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        checkbox.checked = originalState;
        alert('Failed to update subtask. Please try again.');
    })
    .finally(() => {
        checkbox.disabled = false;
        subtaskElement.style.opacity = '1';
    });
}

function updateTaskProgress(taskId) {
    fetch(window.todoUrls.getTaskProgress.replace('0', taskId))
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Find task card
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            if (!taskCard) return;

            // Update progress bar
            const progressBar = taskCard.querySelector('.progress-bar');
            const progressText = taskCard.querySelector('.progress-text');

            if (progressBar) {
                progressBar.style.width = `${data.completion_percentage}%`;
            }

            if (progressText) {
                progressText.textContent = `${Math.round(data.completion_percentage)}%`;
            }

            // Update card header counters if they exist
            const subtaskCounter = taskCard.querySelector('.subtask-counter');
            if (subtaskCounter) {
                subtaskCounter.textContent = `Subtasks (${data.total_subtasks})`;
            }

            // Update total time
            const totalTime = taskCard.querySelector('.total-time');
            if (totalTime) {
                totalTime.textContent = `Total time: ${data.total_duration_hours.toFixed(1)} hours`;
            }

            // Add/remove completed class from card if task is totally done
            if (data.completion_percentage === 100) {
                taskCard.classList.add('completed');
            } else {
                taskCard.classList.remove('completed');
            }
        }
    })
    .catch(error => {
        console.error('Error updating progress:', error);
    });
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
                location.reload();
            }
        });
    }
}

function toggleSubtasks(taskId) {
    const subtasksList = document.querySelector(`.subtasks-list[data-task-id="${taskId}"]`);
    const toggleBtn = document.querySelector(`.toggle-subtasks-btn[data-task-id="${taskId}"]`);
    const hiddenSubtasks = subtasksList.querySelectorAll('.hidden-subtask');

    const isExpanded = !hiddenSubtasks[0].classList.contains('d-none');

    hiddenSubtasks.forEach(subtask => {
        if (isExpanded) {
            subtask.classList.add('d-none');
        } else {
            subtask.classList.remove('d-none');
        }
    });

    // Update button text and icon
    const icon = toggleBtn.querySelector('i');
    const text = toggleBtn.querySelector('small');

    if (isExpanded) {
        icon.className = 'fas fa-chevron-down';
        text.innerHTML = '<i class="fas fa-chevron-down"></i> Show all';
    } else {
        icon.className = 'fas fa-chevron-up';
        text.innerHTML = '<i class="fas fa-chevron-up"></i> Show less';
    }
}

function toggleSubtaskScheduleFields() {
    const scheduleFields = document.getElementById('subtask_schedule_fields');
    const isChecked = document.getElementById('subtask_scheduled').checked;

    if (isChecked) {
        scheduleFields.style.display = 'block';
        // Set default times if not already set
        if (!document.getElementById('subtask_start_time').value) {
            document.getElementById('subtask_start_time').value = '09:00';
        }
        if (!document.getElementById('subtask_end_time').value) {
            document.getElementById('subtask_end_time').value = '10:00';
        }
    } else {
        scheduleFields.style.display = 'none';
    }
}