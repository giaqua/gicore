frappe.provide("frappe.ui");

frappe.ui.Notifications = class CustomNotifications extends frappe.ui.Notifications {
    constructor() {
        super();
        this.setup_custom_events();
    }

    setup_custom_events() {
        // Listen for real-time notifications
        frappe.realtime.on("notification", (data) => {
            this.on_new_notification(data);
        });
    }

    // Override the make method to customize the icon and badge
    make() {
        this.notifications_icon = this.parent.find(".notifications-icon");
        this.notifications_icon
            .attr("title", __("Notifications"))
            .tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

        this.createUnreadCountElement();
        this.applyUnreadCountStyles();

        this.setup_notification_listeners();
        this.get_notifications_list(this.max_length).then((r) => {
            if (!r.message) return;
            this.dropdown_items = r.message.notification_logs;
            frappe.update_user_info(r.message.user_info);
            this.render_notifications_dropdown();
            this.display_unread_count();
        });
    }

    createUnreadCountElement() {
        // Create a badge element for the notification count
        this.unreadCountElement = document.createElement('span');
        this.unreadCountElement.classList.add('unread-count');
        this.notifications_icon[0].appendChild(this.unreadCountElement);
    }

    applyUnreadCountStyles() {
        $(this.unreadCountElement).css({
            "position": "absolute",
            "top": "-10px",
            "right": "-10px",
            "background-color": "#ff5858",
            "color": "white",
            "border-radius": "50%",
            "padding": "2px 6px",
            "font-size": "11px",
            "font-weight": "bold",
            "display": "none",
            "min-width": "18px",
            "text-align": "center"
        });
    }

    on_new_notification(data) {
        // Custom logic when a new notification (mention/comment) arrives
        console.log("New notification received!", data);

        // Check if it's a mention in a comment
        if (data && data.notification_type === "Mention") {
            frappe.show_alert({
                message: __("You were mentioned in a comment"),
                indicator: "green"
            });
            
            // Play sound effect (optional)
            // new Audio('/assets/frappe/js/lib/sound/notification.mp3').play();
        }

        // Update the dropdown and badge count
        this.update_dropdown();
        this.display_unread_count();
    }

    display_unread_count() {
        let unreadCount = this.dropdown_items.filter(item => !item.read).length;
        if (unreadCount > 0) {
            $(this.unreadCountElement).text(unreadCount).css("display", "block");
        } else {
            $(this.unreadCountElement).css("display", "none");
        }
    }

    update_dropdown() {
        this.get_notifications_list(1).then((r) => {
            if (!r.message) return;
            let new_item = r.message.notification_logs[0];
            frappe.update_user_info(r.message.user_info);
            this.dropdown_items.unshift(new_item);
            if (this.dropdown_items.length > this.max_length) {
                this.container.find(".recent-notification").last().remove();
                this.dropdown_items.pop();
            }
            this.insert_into_dropdown();
            this.display_unread_count(); // Update badge count
        });
    }
};

// Add a custom navbar icon if you want a separate icon for comment notifications
$(document).on("app_ready", function() {
    // Method 1: Add a custom icon to the navbar
    if ($(".custom-notification-icon").length === 0) {
        $('header.navbar > .container > .navbar-collapse > ul.navbar-nav').append(`
            <li class="nav-item dropdown dropdown-notifications dropdown-mobile custom-notification-icon">
                <a class="nav-link notifications-icon" href="#" role="button" data-toggle="dropdown">
                    ${frappe.utils.icon('comment', 'md')}
                    <span class="badge" id="comment-notification-count" style="display: none;"></span>
                </a>
                <ul class="dropdown-menu notification-list" id="comment-notification-list">
                    <li class="dropdown-header">Comment Notifications</li>
                    <li class="text-center text-muted" style="padding: 15px;">No new comment mentions</li>
                </ul>
            </li>
        `);
    }

    // Method 2: Enhance the existing bell icon to show comment-specific counts
    // This filters notifications by type "Mention"
    function updateCommentBadgeCount() {
        frappe.call({
            method: "frappe.core.api.notifications.get_notifications",
            callback: function(r) {
                if (r.message && r.message.notification_logs) {
                    const commentNotifications = r.message.notification_logs.filter(
                        item => item.notification_type === "Mention"
                    );
                    const unreadComments = commentNotifications.filter(
                        item => !item.read
                    ).length;
                    
                    if (unreadComments > 0) {
                        $("#comment-notification-count").text(unreadComments).show();
                    } else {
                        $("#comment-notification-count").hide();
                    }
                }
            }
        });
    }

    // Update badge every 30 seconds
    setInterval(updateCommentBadgeCount, 30000);
    updateCommentBadgeCount();
});