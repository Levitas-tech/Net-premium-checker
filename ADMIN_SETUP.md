# 🔐 Admin User Management Setup

This document explains how to set up and use the admin user management feature in the Net Premium Checker application.

## 🚀 Quick Setup

### 1. Database Migration
The admin feature requires a new `is_admin` field in the `users` table. This field is automatically added when you restart the application.

### 2. Create Your First Admin User
Run the admin creation script:

```bash
python create_admin.py
```

**Important:** Update the `DATABASE_URL` in `create_admin.py` with your actual PostgreSQL credentials before running.

### 3. Access the Admin Panel
- Log in with your admin account
- Navigate to the Admin Panel from the sidebar (Shield icon)
- Only admin users will see this option

## 🛡️ Admin Features

### User Management
- **Create Users**: Add new users with optional admin privileges
- **List Users**: View all users in the system
- **Edit Users**: Modify user details, passwords, and admin status
- **Delete Users**: Remove users (admins cannot delete themselves)

### Security Features
- **Role-Based Access**: Only admin users can access the admin panel
- **Password Security**: Passwords are hashed using bcrypt
- **Self-Protection**: Admins cannot delete their own accounts

## 🔧 Backend API Endpoints

| Endpoint | Method | Description | Access |
|----------|--------|-------------|---------|
| `/admin/check` | GET | Check if current user is admin | All authenticated users |
| `/admin/users` | GET | List all users | Admin only |
| `/admin/users` | POST | Create new user | Admin only |
| `/admin/users/{id}` | GET | Get user details | Admin only |
| `/admin/users/{id}` | PUT | Update user | Admin only |
| `/admin/users/{id}` | DELETE | Delete user | Admin only |

## 🎯 Frontend Components

### AdminPanel Component
- **Location**: `frontend/src/components/AdminPanel.js`
- **Features**: 
  - User creation/editing forms
  - User management table
  - Role-based access control
  - Responsive design with Tailwind CSS

### Navigation Integration
- **Location**: `frontend/src/components/Layout.js`
- **Behavior**: Admin Panel link only appears for admin users
- **Icon**: Shield icon (🔒) to indicate admin functionality

## 🔒 Security Considerations

### Authentication
- All admin endpoints require valid JWT tokens
- Admin status is verified on each request
- Failed authentication returns 401 Unauthorized

### Authorization
- Admin endpoints check `is_admin` flag
- Non-admin users get 403 Forbidden
- User deletion prevents self-deletion

### Data Validation
- Input validation on all forms
- SQL injection protection via SQLAlchemy ORM
- Password strength requirements (minimum 6 characters)

## 🚨 Troubleshooting

### Common Issues

1. **"Access Denied" Error**
   - Ensure your user has `is_admin = true` in the database
   - Check if the admin check endpoint is working

2. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check database credentials in `create_admin.py`
   - Ensure the `users` table exists

3. **Admin Panel Not Visible**
   - Check if `user.is_admin` is true in the database
   - Verify the AuthContext is properly set
   - Check browser console for errors

### Database Queries

**Check if user is admin:**
```sql
SELECT username, is_admin FROM users WHERE username = 'your_username';
```

**Make existing user admin:**
```sql
UPDATE users SET is_admin = true WHERE username = 'your_username';
```

**List all admin users:**
```sql
SELECT username, email, is_admin FROM users WHERE is_admin = true;
```

## 📝 Usage Examples

### Creating a New User
1. Navigate to Admin Panel
2. Click "Create User"
3. Fill in username, email, and password
4. Check "Admin privileges" if needed
5. Click "Create User"

### Editing a User
1. Click the edit (pencil) icon next to a user
2. Modify the required fields
3. Leave password blank to keep current password
4. Click "Update User"

### Deleting a User
1. Click the delete (trash) icon next to a user
2. Confirm deletion in the popup
3. User will be permanently removed

## 🔄 Future Enhancements

Potential improvements for the admin system:
- User activity logging
- Bulk user operations
- Password reset functionality
- User role hierarchies
- Audit trails for admin actions

## 📞 Support

If you encounter issues:
1. Check the browser console for errors
2. Verify database connectivity
3. Ensure all dependencies are installed
4. Check the backend logs for detailed error messages

---

**Note**: This admin feature is designed for internal use only. Ensure proper security measures are in place before deploying to production environments.
