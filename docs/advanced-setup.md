# Advanced Setup

This guide covers advanced topics for users who want more control over their installation.

**Note**: Most users don't need this. The basic installation from [Getting Started](getting-started.md) works great!

## Running the Server Continuously

By default, the server stops when you close your terminal window. If you want it to run continuously:

### Option 1: Keep Terminal Open (Easiest)

Simply keep the terminal window open while the server is running. Don't close it!

### Option 2: Run in Background (Mac/Linux)

```bash
# Start server in background
nohup degiro_portfolio start > server.log 2>&1 &

# Check if it's running
degiro_portfolio status

# Stop it later
degiro_portfolio stop
```

### Option 3: Windows Service

On Windows, you can create a scheduled task to start the server automatically when your computer boots:

1. Open Task Scheduler
2. Create a new task
3. Set trigger: "At startup"
4. Set action: Run `python -m degiro_portfolio start`
5. Set to run whether user is logged in or not

## Accessing from Other Devices

By default, the dashboard only works on the computer running it. To access from other devices on your network:

### Step 1: Find Your Computer's IP Address

**On Mac:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**On Windows:**
```bash
ipconfig
```

Look for something like `192.168.1.100`

### Step 2: Allow External Access

When starting the server, use:

```bash
# Linux/Mac
HOST=0.0.0.0 degiro_portfolio start

# Windows
set HOST=0.0.0.0 && degiro_portfolio start
```

### Step 3: Access from Other Devices

On another device (phone, tablet, another computer) on the same network:
```
http://192.168.1.100:8000
```

(Replace with your computer's IP address)

**Security Note**: Only do this on your home network! This makes your portfolio accessible to anyone on the same network.

## Changing the Port

If port 8000 is already in use, you can change it:

**Linux/Mac:**
```bash
PORT=8080 degiro_portfolio start
```

**Windows:**
```bash
set PORT=8080 && degiro_portfolio start
```

Then access at: `http://localhost:8080`

## Storing Data in a Different Location

By default, the database file is created in your current directory. To use a different location:

**Linux/Mac:**
```bash
DATABASE_URL=sqlite:////path/to/my/data/portfolio.db degiro_portfolio start
```

**Windows:**
```bash
set DATABASE_URL=sqlite:///C:/Users/YourName/Documents/portfolio.db && degiro_portfolio start
```

## Creating a Permanent Configuration

Instead of setting environment variables each time, create a configuration file:

### Step 1: Create .env File

In the folder where you installed the application, create a file named `.env` (yes, it starts with a dot):

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000

# Database Location
DATABASE_URL=sqlite:///degiro_portfolio.db

# Data Provider (optional)
PRICE_DATA_PROVIDER=yahoo
```

### Step 2: Save and Restart

Save the file and restart the server. It will automatically use these settings.

## Backing Up Your Data

Your portfolio data is stored in a single file: `degiro_portfolio.db`

### Simple Backup

Just copy this file to a safe location:

**Mac/Linux:**
```bash
cp degiro_portfolio.db ~/Backups/portfolio-backup-$(date +%Y%m%d).db
```

**Windows:**
```bash
copy degiro_portfolio.db C:\Backups\portfolio-backup.db
```

### Automatic Daily Backup (Mac/Linux)

Create a scheduled task to back up daily:

1. Open terminal
2. Run: `crontab -e`
3. Add this line:
   ```
   0 2 * * * cp /path/to/degiro_portfolio.db /path/to/backups/portfolio-$(date +\%Y\%m\%d).db
   ```

This backs up your database every day at 2 AM.

### Automatic Daily Backup (Windows)

1. Open Task Scheduler
2. Create a new task
3. Set trigger: Daily at 2:00 AM
4. Set action: Run a batch script that copies the file
5. Save the task

## Running Multiple Portfolios

You can run multiple instances for different portfolios:

```bash
# Portfolio 1 on port 8000
DATABASE_URL=sqlite:///portfolio1.db PORT=8000 degiro_portfolio start

# Portfolio 2 on port 8001 (in another terminal)
DATABASE_URL=sqlite:///portfolio2.db PORT=8001 degiro_portfolio start
```

Access them at:
- Portfolio 1: `http://localhost:8000`
- Portfolio 2: `http://localhost:8001`

## Troubleshooting Advanced Setup

### Server Won't Start with Custom Port

- Make sure the port isn't already in use
- Try a different port number (8080, 8888, 9000)
- Restart your computer and try again

### Can't Access from Other Devices

- Make sure both devices are on the same network
- Check your computer's firewall settings
- Verify the server is running with `HOST=0.0.0.0`
- Try turning off your firewall temporarily to test

### Database File Not Found

- Check the path in DATABASE_URL is correct
- Make sure the directory exists (create it if needed)
- Use absolute paths, not relative paths

### Configuration File Not Working

- Make sure the file is named exactly `.env` (with the dot)
- Check there are no spaces around the `=` signs
- Restart the server after changing the file
- Make sure the file is in the same directory where you run the server

## Need Help?

If you're stuck with advanced setup:

1. Try the basic setup first to make sure everything works
2. Check the [Troubleshooting section](getting-started.md#troubleshooting) in Getting Started
3. Look at server logs: `degiro_portfolio logs`
4. Ask for help on GitHub Issues

**Note for Programmers**: Technical documentation including API reference, development guide, testing, and deployment is available in the [Developer Appendix](developer-appendix.md).
