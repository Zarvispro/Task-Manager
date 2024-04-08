from flask import render_template, redirect, url_for, flash, request, session, jsonify
from app import app, db
from app.forms import RegistrationForm, LoginForm, TaskForm
from app.models import User, Task
from flask_login import login_user, current_user, login_required, logout_user
from sqlalchemy.exc import IntegrityError
from datetime import date
from datetime import datetime
from .forms import ChangePasswordForm


@app.route('/')
@app.route('/home')
def home():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in', 'success')
            return redirect(url_for('login'))
        except IntegrityError as e:
            db.session.rollback()
            if 'UNIQUE constraint failed: user.email' in str(e):
                flash('Email address is already in use. Please choose a different one.', 'danger')
            elif 'UNIQUE constraint failed: user.username' in str(e):
                flash('Username is already in use. Please choose a different one.', 'danger')
            else:
                flash('An error occurred. Please try again later.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                if field == 'confirm_password':
                    flash('Confirm Password must be equal to Password', 'danger')
                elif field == 'username' and 'already exists' in error:
                    flash('Username already exists', 'danger')
                elif field == 'email' and 'Invalid email address' in error:
                    flash('Invalid email address', 'danger')
                elif field == 'email' and 'already exists' in error:
                    flash('Email already exists', 'danger')
                else:
                    flash(f'{field.capitalize()}: {error}', 'danger')
    return render_template('register.html', title='Register', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    if request.method == 'POST':
        logout_user()
        flash('You have been logged out.', 'success')
        return redirect(url_for('home'))
    else:
        return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Get all tasks
    all_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    all_pending_tasks = [task for task in all_tasks if not task.completed_at and not task.skipped_at]

    # Filter tasks due today
    today = date.today()
    today_tasks = [task for task in all_tasks if task.due_date.date() == today and not task.completed_at and not task.skipped_at]

    # Calculate counts for each priority
    high_priority_count = sum(1 for task in all_pending_tasks if task.priority == 1)
    medium_priority_count = sum(1 for task in all_pending_tasks if task.priority == 2)
    low_priority_count = sum(1 for task in all_pending_tasks if task.priority == 3)

    return render_template('dashboard.html', today_tasks=today_tasks, tasks=all_pending_tasks,
                           high_priority_count=high_priority_count, medium_priority_count=medium_priority_count,
                           low_priority_count=low_priority_count)


@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(title=form.title.data, description=form.description.data, due_date=form.due_date.data, priority=form.priority.data, user_id=current_user.id)
        db.session.add(task)
        db.session.commit()
        flash('Task added successfully', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_task.html', form=form)


@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.due_date = form.due_date.data
        task.priority = form.priority.data
        db.session.commit()
        flash('Task updated successfully', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_task.html', form=form, task=task)


@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/complete_task/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    task = Task.query.get(task_id)
    if task.completed_at:
        return jsonify({'error': 'Task already completed'}), 400
    elif task.skipped_at:
        return jsonify({'error': 'Task already skipped'}), 400
    else:
        task.completed_at = datetime.utcnow()
        try:
            db.session.commit()
            return redirect(url_for('dashboard'))  # Redirect to dashboard after completing task
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'An error occurred while completing the task'}), 500


@app.route('/skip_task/<int:task_id>', methods=['POST'])
@login_required
def skip_task(task_id):
    task = Task.query.get(task_id)
    if task.completed_at:
        return jsonify({'error': 'Task already completed'}), 400
    elif task.skipped_at:
        return jsonify({'error': 'Task already skipped'}), 400
    else:
        task.skipped_at = datetime.utcnow()
        try:
            db.session.commit()
            return redirect(url_for('dashboard'))
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'An error occurred while skipping the task'}), 500


@app.route('/history')
@login_required
def task_history():
    completed_tasks = Task.query.filter(Task.user_id == current_user.id, Task.completed_at.isnot(None)).all()
    skipped_tasks = Task.query.filter(Task.user_id == current_user.id, Task.skipped_at.isnot(None)).all()
    return render_template('history.html', completed_tasks=completed_tasks, skipped_tasks=skipped_tasks)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.old_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Your password has been changed successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Old password is incorrect. Please try again.', 'danger')
    return render_template('profile.html', form=form)
