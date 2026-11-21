# AutoHub Showroom

A beginner-friendly car showroom web app built with Python, Flask, HTML, CSS, and SQLite. It has customer accounts, persistent service and selling requests, car search filters, photo listings, and an admin dashboard.

## Start it on Windows

Open this folder in VS Code, then choose **Terminal → New Terminal**. Run these commands one at a time:

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000** in your browser. Keep the terminal open while using the website. To stop it, click the terminal and press **Ctrl+C**.

If `python` is not recognized, install Python from [python.org/downloads](https://www.python.org/downloads/). In the installer, select **Add python.exe to PATH**, then close and reopen VS Code.

## Put a public demo online

`render.yaml` prepares this Flask project for a public Render web service. To deploy it, put the project files in a GitHub repository (keep `.env` private; `.gitignore` excludes it), then in Render choose **New → Blueprint**, connect that repository, and deploy. Render will give the app a public `onrender.com` link. The source repository can be private while the deployed website is public.

This quick setup uses Render's free web service and the app's local SQLite database. Free Render services have temporary storage and can lose the database when they restart, redeploy, or sleep. Use this link to demonstrate the mini project with sample data; do not rely on it to keep real customer accounts or booking records. For ongoing use, we need to move the data to a persistent hosted database and choose hosting that preserves it. Render's free service can also sleep after inactivity. See [Render's free service limits](https://render.com/docs/free) and [Flask deployment guide](https://render.com/docs/deploy-flask).

## Try the new features

- Choose **Sign in** in the top menu, then create a customer account. You need an account to submit service or sell requests.
- Choose **Buy a car** to search by make/model and filter by fuel, transmission, year, and maximum price.
- Choose **Book a service** or **Sell your car** to submit a request. Requests are saved in `autohub.db` in this project folder.
- Choose **Admin** in the footer or open **http://127.0.0.1:5000/admin**. The local demo admin password is `admin12345`. The dashboard can add or remove car listings, see customer requests, and update their statuses.
- Car photos are loaded from Unsplash, so those images need an internet connection. The site and its database run locally on your computer.

## Set up email and WhatsApp alerts

The app can notify the owner by email and WhatsApp when a customer registers, sends a service or selling request, or the admin adds/removes a car or changes a request status. Email and WhatsApp credentials belong in the private `.env` file and are not included in the sample settings.

1. I created a private `.env` file for this project with your email and WhatsApp destination already filled in. Open it in VS Code and add the missing credentials. Never share the `.env` file; it contains private access credentials.
2. For Gmail, turn on 2-Step Verification and create an App Password from your Google Account. Put the 16-character App Password in `AUTOHUB_SMTP_PASSWORD` in `.env`. Use your Gmail address for `AUTOHUB_SMTP_USER`. Google requires 2-Step Verification for App Passwords; see [Google's App Password help](https://support.google.com/mail/answer/185833?hl=en).
3. For WhatsApp, connect the business sender number in Meta's WhatsApp Business Platform, then copy its **Phone Number ID** and access token into `AUTOHUB_WHATSAPP_PHONE_NUMBER_ID` and `AUTOHUB_WHATSAPP_ACCESS_TOKEN`. The business phone number itself is not the Phone Number ID.
4. In Meta, create and get approval for a Utility message template named `autohub_notification` with this body: `AutoHub notification: {{1}}`. Set the template language to `English (US)` or change `AUTOHUB_WHATSAPP_LANGUAGE` to match it. The app sends notifications as template messages through Meta's Cloud API. See [Meta's WhatsApp Business Platform documentation](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview/).
5. Save `.env`, then restart the app. Install the added dependency if prompted by running `\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

For the Cloud API, Meta's configuration values are available in the WhatsApp Business Platform setup. Enter your business number as the sender and your own number as the destination. The starter project expects you to supply Meta's phone number ID and access token.

## Change the local admin password

In the VS Code terminal, stop the server with **Ctrl+C**, then set a new password for the current terminal and start the app again:

```powershell
$env:AUTOHUB_ADMIN_PASSWORD = "choose-a-new-password"
.\.venv\Scripts\python.exe app.py
```

For a real public website, also set a private `AUTOHUB_SECRET_KEY`, use HTTPS, and do not publish the local demo admin password. This project is a learning starter, not a production-ready customer data system.

## Useful files

- `app.py` — Flask pages, database setup, and form handling
- `autohub.db` — SQLite database, created automatically when the app starts
- `templates/` — HTML pages
- `static/style.css` — styling
- `requirements.txt` — Python packages
- `.env.example` — safe template for local mail and WhatsApp settings; copy to `.env` and fill in credentials

