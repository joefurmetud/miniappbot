# 🚀 Telegram Mini App Bot - Deployment Guide

## 📋 Prerequisites
- GitHub account
- Render account
- Telegram Bot Token
- NOWPayments API key (optional)

## 🔧 Environment Variables Required

Set these in your Render environment:

```bash
# Required
TOKEN=your_telegram_bot_token_here
WEBHOOK_URL=https://your-app-name.onrender.com

# Admin Configuration
ADMIN_ID=your_telegram_user_id
PRIMARY_ADMIN_IDS=your_id,another_admin_id
SECONDARY_ADMIN_IDS=viewer_admin_id

# Optional - Payment Integration
NOWPAYMENTS_API_KEY=your_nowpayments_key
NOWPAYMENTS_IPN_SECRET=your_webhook_secret
```

## 🚀 Deploy to Render

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

### Step 2: Create Render App
1. Go to [render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Choose the repository with your bot code

### Step 3: Configure Render
- **Name**: `your-bot-name` (e.g., `bot-shop-miniapp`)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python render_start.py`
- **Plan**: Free (or paid if you need more resources)

### Step 4: Set Environment Variables
Add all the environment variables listed above in the Render dashboard.

### Step 5: Deploy
Click "Create Web Service" and wait for deployment.

## 🔗 After Deployment

### 1. Set Webhook URL
Your bot will automatically set the webhook to:
```
https://your-app-name.onrender.com/telegram/YOUR_BOT_TOKEN
```

### 2. Test the Bot
- Send `/start` to your bot
- Send `/miniapp` to access the Mini App
- Test admin functions with `/admin`

### 3. Mini App URL
Your Mini App will be available at:
```
https://your-app-name.onrender.com
```

## 🐛 Troubleshooting

### Common Issues:

1. **Bot not responding**: Check if webhook is set correctly
2. **Mini App not loading**: Verify WEBHOOK_URL environment variable
3. **Database errors**: Ensure the app has write permissions
4. **Payment issues**: Check NOWPayments configuration

### Logs:
Check Render logs in the dashboard for any errors.

## 📱 Mini App Features

- 🛒 **Shopping Interface**: Browse products by location
- 🛍️ **Basket Management**: Add/remove items
- 👤 **User Profile**: View balance and history
- 💳 **Payment Integration**: Ready for NOWPayments
- 🔧 **Admin Panel**: Full bot management via Telegram

## 🔒 Security Notes

- Keep your bot token secret
- Use HTTPS (Render provides this automatically)
- Monitor webhook access logs
- Regularly update dependencies

## 📞 Support

If you encounter issues:
1. Check Render logs
2. Verify environment variables
3. Test locally first
4. Check Telegram Bot API status

---

**🎉 Your Mini App Bot is now ready for production!**

