from app.routes.staff import bp
from app.utils.decorators import staff_required
from flask_login import login_required, current_user
from flask import render_template, flash, redirect, url_for, request, abort
from app.models import CustomerOrder, User, Notification
from app.extensions import db



# DASHBOARD
@bp.route('/dashboard')
@login_required
@staff_required
def dashboard():
    return render_template('staff/dashboard.html')


# MARK TASK AS FAILED
@bp.route('/orders/<int:order_id>/task_failed', methods=['POST'])
@login_required
@staff_required
def mark_task_failed(order_id):
    order = CustomerOrder.query.get_or_404(order_id)

    if order.status != 'approved':
        flash('Only approved orders can be marked as failed.', 'warning')
        return redirect(url_for('staff.dashboard'))

    #  Get reason from form
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Please provide a reason for failure.', 'warning')
        return redirect(url_for('staff.dashboard'))

    # Mark the order as failed
    order.status = 'failed'
    order.notes = reason  #  Save reason to notes

    # Restock each device in the order
    for item in order.items:
        if item.device and item.device.status != 'available':
            item.device.status = 'available'

    db.session.commit()

    # Notify all admin users
    admin_users = User.query.filter_by(role='admin').all()
    for admin in admin_users:
        notif = Notification(
            user_id=admin.id,
            message=f"Order #{order.id} marked as failed by staff. Reason: {reason}"
        )
        db.session.add(notif)
        
   
      # Notify customer
    if order.customer:
        notif_link_customer = url_for('customers.order_detail', order_id=order.id)
        db.session.add(Notification(
            user_id=order.customer.id,
            message=f"Your order #{order.id} failed. Reason: {reason}",
            recipient_type='customer',
            link=notif_link_customer
        ))

    db.session.commit()

    flash('Order marked as failed and notifications sent.', 'danger')
    return redirect(url_for('staff.dashboard'))


# MARK TASK AS SUCCESSFUL
@bp.route('/orders/<int:order_id>/task_success', methods=['POST'])
@login_required
@staff_required
def mark_task_success(order_id):
    order = CustomerOrder.query.get_or_404(order_id)

    if order.status != 'approved':
        flash('Only approved orders can be marked as successful.', 'warning')
        return redirect(url_for('staff.dashboard'))

    # Mark each device in the order as sold
    for item in order.items:
        if item.device and item.device.status != 'sold':
            item.device.mark_as_sold()  # uses your model's mark_as_sold()

    # Optionally, update the order status if needed
    order.status = 'completed'
    db.session.commit()

    # Notify all admins
    admin_users = User.query.filter_by(role='admin').all()
    for admin in admin_users:
        db.session.add(Notification(
            user_id=admin.id,
            message=f"Order #{order.id} marked as successful by staff."
        ))

    # Notify the customer
    if order.customer:
        notif_link_customer = url_for('customers.order_detail', order_id=order.id)
        db.session.add(Notification(
            user_id=order.customer.id,
            message=f"Your order #{order.id} was completed successfully. Thank you for shopping with us!",
            recipient_type='customer',
            link=notif_link_customer
        ))

    db.session.commit()

    flash('Order marked as successful. Device(s) sold and notifications sent.', 'success')
    return redirect(url_for('staff.dashboard'))





# staff sold items
@bp.route('/staff/sold-items')
@login_required
@staff_required  # If you have a decorator to restrict to staff
def view_sold_items():
    sold_items = CustomerOrder.query.filter_by(
        assigned_staff_id=current_user.id,
        status='completed'
    ).all()
    return render_template('staff/sold_items.html', sold_items=sold_items)


# FAILED ORDERS
@bp.route('/staff/failed-orders')
@login_required
@staff_required
def view_failed_orders():
    failed_orders = CustomerOrder.query.filter_by(
        status='failed',
        assigned_staff_id=current_user.id
    ).all()
    return render_template('staff/failed_orders.html', failed_orders=failed_orders)

# DELETE NOTIFICATION
@bp.route('/notifications/delete/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    notif = Notification.query.get_or_404(notification_id)
    if notif.user_id != current_user.id:
        abort(403)
    db.session.delete(notif)
    db.session.commit()
    flash('Notification deleted.', 'success')
    return redirect(request.referrer or url_for('auth.view_notifications'))

# CLEAR NOTIFICATIONS
@bp.route('/notifications/clear', methods=['POST'])
@login_required
def clear_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('All notifications cleared.', 'info')
    return redirect(url_for('auth.notifications'))
