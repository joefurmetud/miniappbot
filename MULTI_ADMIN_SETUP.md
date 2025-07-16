# Multi-Admin Support

This bot now supports multiple primary administrators. This update allows you to have several users with full administrative privileges.

## Configuration

### Environment Variables

The bot now supports two ways to configure primary admins:

#### Option 1: Legacy Single Admin (Backwards Compatible)
```
ADMIN_ID=123456789
```

#### Option 2: Multiple Primary Admins (New Feature)
```
PRIMARY_ADMIN_IDS=123456789,987654321,456789123
```

#### Option 3: Mixed Configuration
You can use both variables together. If both are set, the `ADMIN_ID` will be automatically added to the `PRIMARY_ADMIN_IDS` list if it's not already included.

```
ADMIN_ID=123456789
PRIMARY_ADMIN_IDS=987654321,456789123
```

In this example, users `123456789`, `987654321`, and `456789123` will all be primary admins.

### Secondary Admins (Unchanged)
Secondary admins remain configured the same way:
```
SECONDARY_ADMIN_IDS=111111111,222222222
```

## Permissions

### Primary Admins
- Full access to all admin features
- Can manage products, users, discounts, etc.
- Can delete reviews
- Can perform destructive actions (clear reservations, etc.)
- Receive critical system notifications

### Secondary Admins  
- Limited admin access (viewer-only for most features)
- Can view sales analytics, stock, reviews
- Cannot perform destructive actions
- Cannot manage users or perform critical operations

## Technical Details

### Code Changes
- Added `PRIMARY_ADMIN_IDS` list to replace single `ADMIN_ID`
- Created helper functions: `is_primary_admin()`, `is_secondary_admin()`, `is_any_admin()`
- Updated authorization checks throughout the codebase
- Maintains backward compatibility with existing `ADMIN_ID` configuration

### Database Schema
No database changes required. The existing admin logging and user management systems work with the new multi-admin structure.

### Notifications
System notifications (payment issues, critical errors) are sent to the first primary admin in the list (`get_first_primary_admin_id()`).

## Migration Guide

### Existing Single Admin Setup
If you currently use `ADMIN_ID=123456789`, no changes are required. The bot will continue to work exactly as before.

### Adding Additional Primary Admins
1. Keep your existing `ADMIN_ID` configuration
2. Add `PRIMARY_ADMIN_IDS` with the new admin user IDs
3. Restart the bot

Example:
```bash
# Before
ADMIN_ID=123456789

# After (adding two more primary admins)
ADMIN_ID=123456789
PRIMARY_ADMIN_IDS=987654321,456789123
```

Now you have three primary admins total: `123456789`, `987654321`, and `456789123`.

### Moving to PRIMARY_ADMIN_IDS Only
If you prefer to use only the new variable:
```bash
# Before
ADMIN_ID=123456789

# After
PRIMARY_ADMIN_IDS=123456789,987654321,456789123
```

## Security Considerations

- Ensure all primary admin Telegram user IDs are correct
- Primary admins have full control over the bot and user data
- Consider using secondary admin roles for users who only need viewing access
- Regularly audit your admin user lists

## Troubleshooting

### No Primary Admins Configured
If neither `ADMIN_ID` nor `PRIMARY_ADMIN_IDS` is set, you'll see:
```
WARNING: No primary admin IDs configured. Primary admin features disabled.
```

### Invalid Admin IDs
Invalid user IDs in the configuration will be ignored with a warning:
```
WARNING: PRIMARY_ADMIN_IDS contains non-integer values. Ignoring.
```

### Checking Current Configuration
The bot logs the loaded admin configuration on startup:
```
INFO: Loaded 3 primary admin ID(s): [123456789, 987654321, 456789123]
INFO: Loaded 2 secondary admin ID(s): [111111111, 222222222]
``` 