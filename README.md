# Discord Task, Reminder & Countdown Bot

A feature-rich Discord bot built with **discord.py** that provides:

* 📝 Channel-based to-do lists with assignment
* ⏰ Personal and admin-managed reminders (with repeating options)
* ⌛ Countdown timers with milestone notifications
* 📜 Automated moderation logging (edits, deletes, attachments, commands)
* 🔐 Role-based permission system for administrators

This bot is designed for student societies, committees, or teams that need lightweight task management and scheduling directly inside Discord.

---

## Features

### ✅ To-Do Lists

* Per-channel task lists
* Assign/unassign tasks to members
* View and manage tasks with simple commands

### ⏰ Reminders

* Set reminders for yourself or others (admins)
* Optional repeating reminders (daily, weekly, monthly)
* Delivered in configurable channels

### ⌛ Countdowns

* Create countdowns to deadlines or events
* Automatic milestone alerts:

  * 7 days
  * 3 days
  * 24 hours
  * 12 hours
  * 1 hour
  * Deadline reached

### 📜 Logging & Moderation

* Logs message edits, deletions, attachments, and commands
* Automatically creates a private `#soc-logs` channel
* Restricted visibility to admins

### 🔐 Permissions

* Admin access controlled via a Discord role named:

  ```
  Systems Administrator
  ```

---

## Requirements

* Python **3.9+**
* A Discord bot application
* The following Python packages:

```bash
pip install discord.py python-dotenv
```

---

## Setup

### 1️⃣ Clone the repository

```bash
git clone https://github.com/yourusername/your-repo-name.git
cd your-repo-name
```

### 2️⃣ Create a `.env` file

```env
DISCORD_TOKEN=your_bot_token_here
```

> ⚠️ Never commit your `.env` file. It is already included in `.gitignore`.

### 3️⃣ Run the bot

```bash
python bot.py
```

---

## Commands

### 📝 To-Do

```
!todo view
!todo add <task>          (admin)
!todo remove <number>     (admin)
!todo clear               (admin)
!todo assign @user <num>  (admin)
!todo unassign <num>      (admin)
```

### ⏰ Reminders

```
!remind set <HHMM> <message>
!remind set <HHMM> day|week|month <message>
!remind list
!remind forget <number>
```

**Admin reminders:**

```
!remind set @user <HHMM> #channel [repeat] <message>
!remind set @role <HHMM> #channel [repeat] <message>
```

### ⌛ Countdowns

```
!countdown set <YYYY-MM-DD> <HHMM> <label>
!countdown list
!countdown forget <number>
```

**Admin countdowns:**

```
!countdown set @user <YYYY-MM-DD> <HHMM> #channel <label>
!countdown set @role <YYYY-MM-DD> <HHMM> #channel <label>
```

### 📖 Help

```
!commands
```

---

## Data Storage

The bot stores data locally using JSON files:

* `todo_data.json`
* `reminders_data.json`
* `countdowns.json`

These files are created automatically at runtime.

---

## Security Notes

* Ensure the bot has only the permissions it needs
* Do not expose logs or admin channels publicly
* The logging system captures message content and attachments

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Commit changes with clear messages
4. Open a pull request

---

## Author

**Nathan Kupracz**

Built as an open-source project for learning and practical Discord automation.
